"""Offline data and ML artifact build pipeline for ExoSignal.

Usage:
    python -m app.pipeline build [--version VERSION] [--raw-path PATH]
    python -m app.pipeline inspect [--version VERSION]
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from app.config import settings
from app.services.data_ingestion import DataIngestion
from app.services.data_cleaning import DataCleaning
from app.services.feature_engineering import FeatureEngineering
from app.ml.anomaly_detection import AnomalyDetector
from app.ml.evaluation import RankingBenchmarkSuite, split_temporal_dataset
from app.ml.ground_truth import generate_ground_truth_labels
from app.ml.ltr_model import ExoSignalLTRModel
from app.scoring.priority_scorer import TargetPriorityScorer


ARTIFACTS_ROOT = Path("artifacts")


def compute_sha256(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_artifacts(
    version: Optional[str] = None,
    raw_path: Optional[str] = None,
    artifacts_dir: Optional[Path] = None
) -> Path:
    """
    Execute offline build pipeline to generate immutable versioned artifacts:
    - planets.parquet
    - model.joblib
    - precomputed_pca.json
    - precomputed_stats.json
    - manifest.json
    """
    artifacts_dir = artifacts_dir or ARTIFACTS_ROOT
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # 1. Determine artifact version tag
    if not version:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        version = f"v1_{today_str}"

    version_dir = artifacts_dir / version
    version_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n========================================================")
    print(f"Building ExoSignal Artifacts: {version}")
    print(f"Destination: {version_dir.resolve()}")
    print(f"========================================================\n")

    # 2. Locate and load raw data
    raw_file = Path(raw_path) if raw_path else Path(settings.RAW_DATA_DIR) / "nasa_exoplanet_archive.csv"
    if not raw_file.exists():
        # Fallback to any CSV in raw directory
        candidates = list(Path(settings.RAW_DATA_DIR).glob("*.csv"))
        if not candidates:
            raise FileNotFoundError(f"No raw exoplanet CSV found at {raw_file} or in {settings.RAW_DATA_DIR}")
        raw_file = candidates[0]

    print(f"[1/7] Ingesting raw archive snapshot: {raw_file.name}")
    raw_hash = compute_sha256(raw_file)
    raw_df = pd.read_csv(raw_file)
    print(f"      Loaded {len(raw_df)} rows. SHA256: {raw_hash[:16]}...")

    # 3. Data cleaning and standardization
    print(f"[2/7] Cleaning, normalizing, and deduplicating...")
    cleaner = DataCleaning()
    cleaned_df = cleaner.clean(raw_df)
    print(f"      Cleaned catalog contains {len(cleaned_df)} unique verified planets.")

    # 4. Feature engineering (Kopparapu HZ, Schulze-Makuch ESI, Infrared Accessibility)
    print(f"[3/7] Computing published physical metrics (Kopparapu HZ & Schulze-Makuch ESI)...")
    fe = FeatureEngineering()
    featured_df = fe.transform(cleaned_df)

    # 5. ML Anomaly Detection (LOF in-sample & Isolation Forest)
    print(f"[4/7] Fitting anomaly detection ensemble...")
    detector = AnomalyDetector(
        contamination=settings.ANOMALY_CONTAMINATION,
        random_state=settings.RANDOM_STATE
    )
    detector.fit(featured_df)
    anom_df = detector.predict_anomaly_scores(featured_df)
    model_path = version_dir / "model.joblib"
    detector.save_model(str(model_path))
    print(f"      Saved fitted anomaly model: {model_path.name}")

    # 6. Target Priority Scoring (Heuristic Baseline)
    print(f"[5/8] Evaluating heuristic target prioritization...")
    scorer = TargetPriorityScorer()
    scored_df = scorer.score(anom_df)

    # 7. Supervised LightGBM Ranking Models (Model A & Model B)
    print(f"[6/8] Fitting Supervised LightGBM Ranking Models (Model A & Model B)...")
    eligible_df = scored_df[scored_df["eligible_for_transmission"]].copy() if "eligible_for_transmission" in scored_df.columns else scored_df
    gt_df = generate_ground_truth_labels(eligible_df)
    train_split, val_split, test_split = split_temporal_dataset(gt_df)

    # Model A: All features (including proxy interaction features)
    ltr_model_a = ExoSignalLTRModel(feature_variant="A", random_state=settings.RANDOM_STATE)
    ltr_model_a.fit(train_split, val_split)
    ltr_model_a_path = version_dir / "ltr_model_a.joblib"
    ltr_model_a.save(str(ltr_model_a_path))
    # Also save as default ltr_model.joblib for system compatibility
    ltr_model_path = version_dir / "ltr_model.joblib"
    ltr_model_a.save(str(ltr_model_path))

    # Model B: Raw features only (proxy leakage features removed)
    ltr_model_b = ExoSignalLTRModel(feature_variant="B", random_state=settings.RANDOM_STATE)
    ltr_model_b.fit(train_split, val_split)
    ltr_model_b_path = version_dir / "ltr_model_b.joblib"
    ltr_model_b.save(str(ltr_model_b_path))

    # Save feature importance breakdowns
    feat_imp_path = version_dir / "ltr_feature_importance.json"
    with open(feat_imp_path, "w") as f:
        json.dump(ltr_model_a.feature_importances, f, indent=2)

    feat_imp_b_path = version_dir / "ltr_feature_importance_b.json"
    with open(feat_imp_b_path, "w") as f:
        json.dump(ltr_model_b.feature_importances, f, indent=2)

    # Score full catalog with LTR Model A and append rank delta (ranking eligible planets only)
    scored_df = ltr_model_a.score_catalog(scored_df)
    if "eligible_for_transmission" in scored_df.columns:
        scored_df = pd.concat([
            scored_df[scored_df["eligible_for_transmission"]].sort_values("target_priority_score", ascending=False),
            scored_df[~scored_df["eligible_for_transmission"]].sort_values("target_priority_score", ascending=False)
        ]).reset_index(drop=True)
    print(f"      Saved fitted LTR Model A: {ltr_model_a_path.name}")
    print(f"      Saved fitted LTR Model B: {ltr_model_b_path.name}")
    print(f"      Top ranking feature (Model A): {ltr_model_a.feature_importances['top_features'][0]['feature']} ({ltr_model_a.feature_importances['top_features'][0]['gain_percentage']}%)")
    print(f"      Top ranking feature (Model B): {ltr_model_b.feature_importances['top_features'][0]['feature']} ({ltr_model_b.feature_importances['top_features'][0]['gain_percentage']}%)")

    # 8. Precompute 2D PCA feature projection
    print(f"[7/8] Precomputing PCA feature projections...")
    pca_features = [
        "planet_radius", "planet_mass", "equilibrium_temperature",
        "orbital_period", "semi_major_axis", "eccentricity",
        "earth_similarity", "observational_accessibility"
    ]
    available_pca_cols = [c for c in pca_features if c in scored_df.columns]

    # Precompute representative PCA points for fluid rendering
    if len(scored_df) > 500:
        top_sample = scored_df.head(200)
        anom_sample = scored_df.nlargest(150, "anomaly_score")
        rand_sample = scored_df.sample(n=150, random_state=42)
        pca_sample_df = pd.concat([top_sample, anom_sample, rand_sample]).drop_duplicates(subset=["planet_name"]).reset_index(drop=True)
    else:
        pca_sample_df = scored_df.reset_index(drop=True)

    X_pca_in = pca_sample_df[available_pca_cols].copy()
    for col in available_pca_cols:
        X_pca_in[col] = pd.to_numeric(X_pca_in[col], errors="coerce")
    X_pca_in = X_pca_in.fillna(X_pca_in.median()).fillna(0.0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_pca_in)
    pca = PCA(n_components=2, random_state=42)
    X_pca_out = pca.fit_transform(X_scaled)

    precomputed_pca = {
        "planets": pca_sample_df["planet_name"].tolist(),
        "pca_x": [round(float(v), 3) for v in X_pca_out[:, 0]],
        "pca_y": [round(float(v), 3) for v in X_pca_out[:, 1]],
        "anomaly_score": [round(float(v), 3) for v in pca_sample_df["anomaly_score"]],
        "priority_score": [round(float(v), 1) for v in pca_sample_df["priority_score"]],
        "target_priority_score": [round(float(v), 1) for v in pca_sample_df["target_priority_score"]],
        "hz_status": pca_sample_df["hz_status"].tolist(),
        "explained_variance": [round(float(v), 4) for v in pca.explained_variance_ratio_],
        "feature_names": available_pca_cols
    }
    with open(version_dir / "precomputed_pca.json", "w") as f:
        json.dump(precomputed_pca, f, indent=2)

    # 8. Precompute system statistics & empirical score histogram
    print(f"[7/8] Precomputing population statistics and saving artifacts...")
    scores = scored_df["priority_score"].dropna()
    counts, bin_edges = np.histogram(scores, bins=[0, 20, 40, 60, 80, 100])
    priority_histogram = [
        {"range": f"{int(bin_edges[i])}-{int(bin_edges[i+1])}", "count": int(counts[i])}
        for i in range(len(counts))
    ]

    precomputed_stats = {
        "total_planets": len(scored_df),
        "score_distribution": {
            "min": round(float(scored_df["priority_score"].min()), 1),
            "max": round(float(scored_df["priority_score"].max()), 1),
            "mean": round(float(scored_df["priority_score"].mean()), 1),
            "median": round(float(scored_df["priority_score"].median()), 1),
            "std": round(float(scored_df["priority_score"].std()), 1)
        },
        "heuristic_score_distribution": {
            "min": round(float(scored_df["target_priority_score"].min()), 1),
            "max": round(float(scored_df["target_priority_score"].max()), 1),
            "mean": round(float(scored_df["target_priority_score"].mean()), 1),
            "median": round(float(scored_df["target_priority_score"].median()), 1),
            "std": round(float(scored_df["target_priority_score"].std()), 1)
        },
        "priority_histogram": priority_histogram,
        "anomaly_distribution": {
            "min": round(float(scored_df["anomaly_score"].min()), 3),
            "max": round(float(scored_df["anomaly_score"].max()), 3),
            "mean": round(float(scored_df["anomaly_score"].mean()), 3),
            "median": round(float(scored_df["anomaly_score"].median()), 3)
        },
        "hz_distribution": scored_df["hz_status"].value_counts().to_dict(),
        "discovery_method_distribution": scored_df["discovery_method"].value_counts().to_dict(),
    }
    with open(version_dir / "precomputed_stats.json", "w") as f:
        json.dump(precomputed_stats, f, indent=2)

    # 9. Execute ML Ranking Evaluation Benchmark
    print(f"[8/8] Running ML Ranking Evaluation Benchmark against ground truth...")
    bench_suite = RankingBenchmarkSuite()
    eval_input_df = scored_df[scored_df["eligible_for_transmission"]].copy() if "eligible_for_transmission" in scored_df.columns else scored_df
    bench_report = bench_suite.run_benchmark(eval_input_df, eval_split="test")
    json_bench, md_bench = bench_suite.save_report(bench_report, version_dir)
    # Also save copy in root artifacts directory for quick access
    bench_suite.save_report(bench_report, artifacts_dir)
    print(f"      Benchmark evaluated {bench_report['models_evaluated']} models. Test set: {bench_report['test_set_size']} planets.")

    # Save immutable Parquet catalog
    parquet_path = version_dir / "planets.parquet"
    scored_df.to_parquet(parquet_path, index=False)

    # Also keep a legacy CSV in processed dir for backward compatibility
    legacy_processed_path = Path(settings.PROCESSED_DATA_DIR) / "processed_exoplanets.csv"
    legacy_processed_path.parent.mkdir(parents=True, exist_ok=True)
    scored_df.to_csv(legacy_processed_path, index=False)

    # Build manifest
    manifest = {
        "artifact_version": version,
        "build_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "raw_data": {
            "file": raw_file.name,
            "sha256": raw_hash,
            "raw_rows": len(raw_df)
        },
        "catalog": {
            "total_planets": len(scored_df),
            "parquet_file": parquet_path.name,
            "parquet_size_bytes": parquet_path.stat().st_size
        },
        "models": {
            "anomaly_detector": model_path.name,
            "anomaly_algorithm": "IsolationForest + LocalOutlierFactor (in-sample)",
            "ltr_model_a": ltr_model_a_path.name,
            "ltr_model_b": ltr_model_b_path.name,
            "ltr_algorithm": "LightGBM Supervised Classifier Ranking",
            "ltr_top_features_a": ltr_model_a.feature_importances["top_features"][:5],
            "ltr_top_features_b": ltr_model_b.feature_importances["top_features"][:5]
        },
        "benchmark": {
            "evaluation_split": bench_report["evaluation_split"],
            "primary_metric": bench_report["primary_metric"],
            "leaderboard": bench_report["leaderboard"]
        },
        "scoring_weights": scorer.scoring_config,
        "hz_counts": scored_df["hz_status"].value_counts().to_dict()
    }
    with open(version_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # Also write a copy of ltr_feature_importance to root artifacts dir
    with open(artifacts_dir / "ltr_feature_importance.json", "w") as f:
        json.dump(ltr_model_a.feature_importances, f, indent=2)
    with open(artifacts_dir / "ltr_feature_importance_b.json", "w") as f:
        json.dump(ltr_model_b.feature_importances, f, indent=2)

    # Update active pointer
    with open(artifacts_dir / "active_version.txt", "w") as f:
        f.write(version)

    # 10. Auto-register in Model Registry
    print(f"\n[Registry] Registering artifact version in model registry...")
    try:
        from app.ml.model_registry import ModelRegistry
        registry = ModelRegistry(artifacts_dir=str(artifacts_dir))

        # Extract Model A metrics from benchmark
        gbdt_entry = next(
            (m for m in bench_report["leaderboard"]
             if "Model A" in m["model_name"] or "GBDT" in m["model_name"] or "Supervised" in m["model_name"]),
            {}
        )

        registry.register_version(
            version=version,
            model_path=str(ltr_model_path),
            parquet_path=str(parquet_path),
            training_config={
                "algorithm": "LightGBM Supervised Classifier Ranking",
                "n_features": len(ltr_model_a.feature_importances.get("top_features", [])),
                "top_features": [f["feature"] for f in ltr_model_a.feature_importances.get("top_features", [])[:5]],
                "random_state": settings.RANDOM_STATE,
                "temporal_split": {
                    "train": f"<= 2017 ({len(train_split)} planets)",
                    "val": f"2018-2021 ({len(val_split)} planets)",
                    "test": f">= 2022 ({len(test_split)} planets)"
                }
            },
            evaluation_metrics={
                "ndcg@10": gbdt_entry.get("ndcg@10"),
                "map": gbdt_entry.get("map"),
                "precision@10": gbdt_entry.get("precision@10"),
                "pr_auc": gbdt_entry.get("pr_auc"),
                "eval_split": bench_report["evaluation_split"]
            },
            dataset_stats={
                "total_planets": len(scored_df),
                "raw_rows": len(raw_df),
                "raw_sha256": raw_hash[:16] + "..."
            },
            notes=f"Auto-registered by pipeline build on {datetime.datetime.now(datetime.timezone.utc).isoformat()}"
        )

        registry.promote(version, reason="Pipeline auto-promotion after successful build")
        print(f"      [OK] Registered and promoted {version} in model registry")
    except Exception as e:
        print(f"      [WARNING] Registry registration failed (non-fatal): {e}")

    print(f"\nBuild complete!")
    print(f"Artifact Version: {version}")
    print(f"Planets in Parquet: {len(scored_df)}")
    print(f"Active version pointer set in {artifacts_dir / 'active_version.txt'}")
    return version_dir


def inspect_artifacts(version: Optional[str] = None, artifacts_dir: Optional[Path] = None) -> None:
    """Inspect active or specified artifact version."""
    artifacts_dir = artifacts_dir or ARTIFACTS_ROOT
    if not version:
        active_ptr = artifacts_dir / "active_version.txt"
        if not active_ptr.exists():
            print("No active artifact version found.")
            return
        version = active_ptr.read_text().strip()

    v_dir = artifacts_dir / version
    manifest_file = v_dir / "manifest.json"
    if not manifest_file.exists():
        print(f"Manifest not found for version {version} at {manifest_file}")
        return

    with open(manifest_file, "r") as f:
        manifest = json.load(f)

    print(f"\n========================================================")
    print(f"ExoSignal Artifact Manifest: {version}")
    print(f"========================================================")
    print(json.dumps(manifest, indent=2))


def inspect_ltr(version: Optional[str] = None, artifacts_dir: Optional[Path] = None) -> None:
    """Inspect Learning-to-Rank (LTR) model feature importances and metadata."""
    artifacts_dir = artifacts_dir or ARTIFACTS_ROOT
    if not version:
        active_ptr = artifacts_dir / "active_version.txt"
        if not active_ptr.exists():
            print("No active artifact version found.")
            return
        version = active_ptr.read_text().strip()

    v_dir = artifacts_dir / version
    feat_file = v_dir / "ltr_feature_importance.json"
    if not feat_file.exists():
        feat_file = artifacts_dir / "ltr_feature_importance.json"

    if not feat_file.exists():
        print(f"LTR feature importance not found for version {version}")
        return

    with open(feat_file, "r") as f:
        feat_data = json.load(f)

    print(f"\n========================================================")
    print(f"ExoSignal Learning-to-Rank Feature Importance ({version})")
    print(f"========================================================")
    for f in feat_data.get("top_features", []):
        print(f"Feature: {f['feature']:<26} | Gain: {f['gain']:<9.1f} | Attribution: {f['gain_percentage']:>5.2f}% | Splits: {f['split_count']}")


def main():
    parser = argparse.ArgumentParser(description="ExoSignal Offline Build Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build versioned artifacts from raw data")
    build_parser.add_argument("--version", type=str, help="Artifact version tag (default: v1_YYYY-MM-DD)")
    build_parser.add_argument("--raw-path", type=str, help="Path to raw exoplanet CSV")
    build_parser.add_argument("--artifacts-dir", type=str, default="artifacts", help="Root artifacts directory")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect an artifact version manifest")
    inspect_parser.add_argument("--version", type=str, help="Artifact version tag to inspect")
    inspect_parser.add_argument("--artifacts-dir", type=str, default="artifacts", help="Root artifacts directory")

    eval_parser = subparsers.add_parser("evaluate", help="Run ML ranking evaluation benchmark")
    eval_parser.add_argument("--split", type=str, default="test", choices=["test", "val"], help="Split to evaluate on")
    eval_parser.add_argument("--artifacts-dir", type=str, default="artifacts", help="Root artifacts directory")

    ltr_parser = subparsers.add_parser("ltr", help="Inspect Learning-to-Rank (LTR) model feature importances")
    ltr_parser.add_argument("--version", type=str, help="Artifact version tag to inspect")
    ltr_parser.add_argument("--artifacts-dir", type=str, default="artifacts", help="Root artifacts directory")

    # Model Registry CLI
    reg_parser = subparsers.add_parser("registry", help="Model registry management")
    reg_parser.add_argument("action", choices=["list", "validate", "compare", "rollback"],
                            help="Registry action to perform")
    reg_parser.add_argument("--version", type=str, help="Version tag for validate action")
    reg_parser.add_argument("--version-a", type=str, help="First version for compare")
    reg_parser.add_argument("--version-b", type=str, help="Second version for compare")
    reg_parser.add_argument("--reason", type=str, default="", help="Reason for rollback")
    reg_parser.add_argument("--artifacts-dir", type=str, default="artifacts", help="Root artifacts directory")

    args = parser.parse_args()

    if args.command == "build":
        build_artifacts(
            version=args.version,
            raw_path=args.raw_path,
            artifacts_dir=Path(args.artifacts_dir)
        )
    elif args.command == "inspect":
        inspect_artifacts(
            version=args.version,
            artifacts_dir=Path(args.artifacts_dir)
        )
    elif args.command == "evaluate":
        from app.services.data_processor import get_data_processor
        processor = get_data_processor()
        df = processor.get_processed_data()
        suite = RankingBenchmarkSuite()
        report = suite.run_benchmark(df, eval_split=args.split)
        suite.save_report(report, Path(args.artifacts_dir))
        print(f"\n========================================================")
        print(f"ExoSignal ML Ranking Leaderboard ({report['evaluation_split'].upper()} Split)")
        print(f"========================================================")
        for m in report["leaderboard"]:
            print(f"Model: {m['model_name']:<24} | P@10: {m['precision@10']:.4f} | NDCG@10: {m['ndcg@10']:.4f} | MAP: {m['map']:.4f} | PR-AUC: {m['pr_auc']:.4f}")
    elif args.command == "ltr":
        inspect_ltr(
            version=args.version,
            artifacts_dir=Path(args.artifacts_dir)
        )
    elif args.command == "registry":
        from app.ml.model_registry import ModelRegistry
        registry = ModelRegistry(artifacts_dir=args.artifacts_dir)

        if args.action == "list":
            versions = registry.list_versions()
            if not versions:
                print("No versions registered in the model registry.")
            else:
                print(f"\n{'Version':<20} {'Status':<14} {'NDCG@10':<10} {'MAP':<10} {'Registered':<22}")
                print("-" * 80)
                for v in versions:
                    ndcg = f"{v['ndcg_at_10']:.4f}" if v['ndcg_at_10'] else "N/A"
                    m = f"{v['map']:.4f}" if v['map'] else "N/A"
                    print(f"{v['version']:<20} {v['status']:<14} {ndcg:<10} {m:<10} {v['registered_at']:<22}")

        elif args.action == "validate":
            version = args.version or registry.get_active_version()
            if not version:
                print("No version specified and no active version found.")
                return
            result = registry.validate_integrity(version)
            print(json.dumps(result, indent=2))

        elif args.action == "compare":
            if not args.version_a or not args.version_b:
                print("Both --version-a and --version-b are required for compare.")
                return
            result = registry.compare_versions(args.version_a, args.version_b)
            print(json.dumps(result, indent=2))

        elif args.action == "rollback":
            rolled = registry.rollback(reason=args.reason)
            if rolled:
                print(f"✅ Rolled back to version: {rolled}")
            else:
                print("No previous version available for rollback.")


if __name__ == "__main__":
    main()
