#!/usr/bin/env python3
"""
Forward-Test Benchmark Harness for JWST Cycle 4 Targets.

Trains the production model (Regularized Logistic Regression Variant A)
strictly on approved JWST Cycle 1-3 transmission spectroscopy targets,
then forward-evaluates how many newly approved Cycle 4 targets land in
the model's top 25, 50, and 100 candidate recommendations.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.ml.ltr_model import ExoSignalLTRModel
from app.ml.ground_truth import generate_ground_truth_labels, get_verified_jwst_targets
from app.services.data_processor import get_data_processor


def find_cycle4_csv() -> Path:
    candidates = [
        Path("backend/data/reference/jwst_cycle4_targets.csv"),
        Path("data/reference/jwst_cycle4_targets.csv"),
        Path(__file__).resolve().parent.parent / "backend" / "data" / "reference" / "jwst_cycle4_targets.csv",
        Path(__file__).resolve().parent.parent / "data" / "reference" / "jwst_cycle4_targets.csv",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def main():
    cycle4_csv = find_cycle4_csv()

    if not cycle4_csv.exists():
        print(f"[Cycle 4 Forward-Test] Reference file not found: {cycle4_csv}")
        print("Please create and populate backend/data/reference/jwst_cycle4_targets.csv with STScI Cycle 4 approved programs.")
        sys.exit(0)

    try:
        cycle4_df = pd.read_csv(cycle4_csv)
    except Exception as e:
        print(f"[Cycle 4 Forward-Test] Error reading {cycle4_csv}: {e}")
        sys.exit(0)

    if cycle4_df.empty or len(cycle4_df.dropna(how="all")) == 0 or "planet_name" not in cycle4_df.columns:
        print("\n========================================================")
        print("JWST Cycle 4 Forward-Test Harness")
        print("========================================================")
        print(f"Cycle 4 reference CSV ({cycle4_csv}) is empty (0 data rows).")
        print("Please populate it from the STScI Cycle 4 approved programs list to run forward testing.")
        print("Reference: https://www.stsci.edu/jwst/science-execution/approved-programs\n")
        sys.exit(0)

    # Filter verified non-empty targets
    cycle4_targets = set(cycle4_df["planet_name"].dropna().astype(str).str.strip())
    if not cycle4_targets:
        print("\n[Cycle 4 Forward-Test] No valid planet_name entries found in CSV.")
        sys.exit(0)

    print("\n========================================================")
    print("JWST Cycle 4 Forward-Test Benchmark")
    print(f"Loaded {len(cycle4_targets)} Cycle 4 target(s) from {cycle4_csv}")
    print("========================================================")

    # 1. Load catalog
    processor = get_data_processor()
    catalog = processor.get_processed_data()

    # 2. Filter eligible transmission candidates
    eligible_mask = catalog["eligible_for_transmission"] == True if "eligible_for_transmission" in catalog.columns else pd.Series(True, index=catalog.index)
    eligible_catalog = catalog[eligible_mask].copy().reset_index(drop=True)

    # 3. Formulate Cycle 1-3 ground truth labels (excluding Cycle 4)
    # Approved targets from Cycle 1-3 reference catalog
    c1_3_targets = get_verified_jwst_targets()
    gt_df = generate_ground_truth_labels(eligible_catalog)

    # Ensure Cycle 4 targets are NOT marked as training positives
    gt_df["ground_truth_binary"] = [
        1 if (str(name).strip() in c1_3_targets and str(name).strip() not in cycle4_targets) else 0
        for name in gt_df["planet_name"]
    ]

    n_train_pos = int(gt_df["ground_truth_binary"].sum())
    print(f"Training production model strictly on Cycle 1-3 labels ({n_train_pos} positives)...")

    # 4. Train production model (Logistic Regression Variant A)
    model = ExoSignalLTRModel(
        model_type="logistic",
        feature_variant="A",
        random_state=42
    )
    model.fit(gt_df)

    # 5. Score catalog and filter out Cycle 1-3 targets (recommendations for unobserved targets)
    scored = model.score_catalog(eligible_catalog)
    unobserved_scored = scored[~scored["planet_name"].isin(c1_3_targets)].copy().reset_index(drop=True)

    # Re-rank unobserved candidates 1..N
    unobserved_scored["recommendation_rank"] = np.arange(1, len(unobserved_scored) + 1)
    n_unobserved = len(unobserved_scored)

    # 6. Evaluate Cycle 4 targets against recommendation ranks
    matches = unobserved_scored[unobserved_scored["planet_name"].isin(cycle4_targets)].copy()
    matches = matches.sort_values("recommendation_rank", ascending=True)

    top_25_hits = matches[matches["recommendation_rank"] <= 25]
    top_50_hits = matches[matches["recommendation_rank"] <= 50]
    top_100_hits = matches[matches["recommendation_rank"] <= 100]

    n_c4 = len(cycle4_targets)
    n_found = len(matches)

    print(f"\nForward Validation Results ({n_c4} Cycle 4 targets, {n_found} matched in eligible catalog):")
    print(f"- Landed in Top 25:  {len(top_25_hits)} / {n_found} (Recall@25 = {len(top_25_hits) / max(1, n_found):.1%})")
    print(f"- Landed in Top 50:  {len(top_50_hits)} / {n_found} (Recall@50 = {len(top_50_hits) / max(1, n_found):.1%})")
    print(f"- Landed in Top 100: {len(top_100_hits)} / {n_found} (Recall@100 = {len(top_100_hits) / max(1, n_found):.1%})")

    if not matches.empty:
        median_rank = matches["recommendation_rank"].median()
        print(f"- Median Recommendation Rank: #{median_rank:.0f} out of {n_unobserved} candidates")

    print("\nDetailed Target Rankings:")
    print(f"{'Planet Name':<20} | {'Rec Rank':<10} | {'Priority Score':<15} | {'TSM':<10}")
    print("-" * 65)
    for _, row in matches.iterrows():
        p_name = row["planet_name"]
        rec_r = row["recommendation_rank"]
        score = row.get("priority_score", 0.0)
        tsm = row.get("tsm", np.nan)
        tsm_str = f"{tsm:.1f}" if pd.notna(tsm) else "N/A"
        print(f"{p_name:<20} | #{rec_r:<9} | {score:<15.2f} | {tsm_str:<10}")

    print("\n========================================================\n")


if __name__ == "__main__":
    main()
