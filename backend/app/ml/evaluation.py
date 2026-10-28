"""ML Ranking Evaluation Engine for ExoSignal.

Implements rigorous evaluation methodologies:
1. Temporal Train/Val/Test Split (Kepler <=2017, TESS 2018-2021, JWST 2022-2026) to prevent data leakage.
2. Ranking Metrics: Precision@K, Recall@K, NDCG@K, MAP, PR-AUC.
3. Model Baselines:
   - Random Ranker
   - Distance-Only Ranker (faintest/nearest heuristic)
   - ESI-Only Ranker (Schulze-Makuch 2011)
   - ExoSignal v1 Heuristic Composite Ranker
   - Supervised Gradient-Boosted Ranker (trained on historical train set, evaluated out-of-time)
4. Comprehensive Benchmark Suite and Report Generator.
"""

from typing import Dict, List, Optional, Tuple, Any
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import precision_recall_curve, auc

from app.ml.ground_truth import generate_ground_truth_labels


# ---------------------------------------------------------------------------
# Ranking Evaluation Metrics
# ---------------------------------------------------------------------------

def precision_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int = 10) -> float:
    """
    Compute Precision@K for binary relevance.

    Precision@K = (# relevant items in top K) / K
    """
    if len(y_true) == 0 or k <= 0:
        return 0.0
    k = min(k, len(y_true))
    order = np.argsort(y_score)[::-1]
    top_k_true = y_true[order[:k]]
    return float(np.sum(top_k_true > 0) / k)


def recall_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int = 10) -> float:
    """
    Compute Recall@K for binary relevance.

    Recall@K = (# relevant items in top K) / (total relevant items in candidate pool)
    """
    total_relevant = np.sum(y_true > 0)
    if total_relevant == 0:
        return 0.0
    k = min(k, len(y_true))
    order = np.argsort(y_score)[::-1]
    top_k_true = y_true[order[:k]]
    return float(np.sum(top_k_true > 0) / total_relevant)


def dcg_at_k(y_graded: np.ndarray, order: np.ndarray, k: int) -> float:
    """Compute Discounted Cumulative Gain at K."""
    k = min(k, len(y_graded))
    ranks = np.arange(1, k + 1)
    gains = 2.0 ** y_graded[order[:k]] - 1.0
    discounts = np.log2(ranks + 1.0)
    return float(np.sum(gains / discounts))


def ndcg_at_k(y_true_graded: np.ndarray, y_score: np.ndarray, k: int = 10) -> float:
    """
    Compute Normalized Discounted Cumulative Gain at K (NDCG@K) for graded relevance.

    NDCG@K = DCG@K / IDCG@K
    """
    if len(y_true_graded) == 0 or k <= 0:
        return 0.0
    k = min(k, len(y_true_graded))

    # Actual ranking order
    actual_order = np.argsort(y_score)[::-1]
    actual_dcg = dcg_at_k(y_true_graded, actual_order, k)

    # Ideal ranking order
    ideal_order = np.argsort(y_true_graded)[::-1]
    ideal_dcg = dcg_at_k(y_true_graded, ideal_order, k)

    if ideal_dcg <= 0.0:
        return 0.0
    return float(np.clip(actual_dcg / ideal_dcg, 0.0, 1.0))


def mean_average_precision(y_true: np.ndarray, y_score: np.ndarray, max_k: Optional[int] = None) -> float:
    """
    Compute Average Precision (AP) for a ranking query.
    """
    total_relevant = np.sum(y_true > 0)
    if total_relevant == 0:
        return 0.0

    order = np.argsort(y_score)[::-1]
    if max_k is not None:
        order = order[:min(max_k, len(order))]

    y_ordered = (y_true[order] > 0).astype(int)
    cumulative_hits = np.cumsum(y_ordered)
    ranks = np.arange(1, len(y_ordered) + 1)

    precision_at_ranks = cumulative_hits / ranks
    # Sum precision only at ranks where item is relevant
    average_precision = np.sum(precision_at_ranks * y_ordered) / min(total_relevant, len(y_ordered))
    return float(average_precision)


def pr_auc_score(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Compute Area Under the Precision-Recall Curve (PR-AUC)."""
    if len(np.unique(y_true > 0)) < 2:
        return 0.0
    precision, recall, _ = precision_recall_curve(y_true > 0, y_score)
    return float(auc(recall, precision))


# ---------------------------------------------------------------------------
# Temporal Split Management
# ---------------------------------------------------------------------------

def split_temporal_dataset(
    df: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split exoplanet dataset into temporal discovery eras:
    - Train split: Discovery Year <= 2017 (Kepler & early ground-based era)
    - Validation split: Discovery Year 2018 - 2021 (TESS primary mission)
    - Test split: Discovery Year >= 2022 (JWST era)

    Ensures zero temporal leakage from future observation technologies.
    """
    df = df.copy()
    if "eligible_for_transmission" in df.columns:
        df = df[df["eligible_for_transmission"] == True].copy()

    if "discovery_year" not in df.columns:
        raise ValueError("Dataset missing 'discovery_year' column for temporal splitting")

    years = pd.to_numeric(df["discovery_year"], errors="coerce")
    train_df = df[years <= 2017].copy().reset_index(drop=True)
    val_df = df[(years >= 2018) & (years <= 2021)].copy().reset_index(drop=True)
    test_df = df[years >= 2022].copy().reset_index(drop=True)

    return train_df, val_df, test_df


# ---------------------------------------------------------------------------
# Baseline Rankers & Models (7 Benchmark Models)
# ---------------------------------------------------------------------------

class RandomRanker:
    """Random baseline ranker (deterministic seed=42)."""
    name = "Random Baseline"

    def __init__(self, random_state: int = 42):
        self.random_state = random_state

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        rng = np.random.default_rng(self.random_state)
        return rng.uniform(0.0, 1.0, size=len(df))


class DistanceRanker:
    """Distance-only baseline: rank by proximity (nearest stars first)."""
    name = "Distance-Only Baseline"

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        dist = pd.to_numeric(df.get("distance", pd.Series(np.nan, index=df.index)), errors="coerce")
        # Inverted distance: closer stars yield higher score; missing distance yields 0
        return np.where(dist.notna() & (dist > 0), 1.0 / (1.0 + dist / 50.0), 0.0)


class TSMRanker:
    """TSM-only baseline: rank by Transmission Spectroscopy Metric (Kempton et al. 2018) descending."""
    name = "TSM-Only Baseline"

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        tsm = pd.to_numeric(
            df.get("transmission_spectroscopy_metric", pd.Series(np.nan, index=df.index)),
            errors="coerce"
        ).fillna(0.0)
        return tsm.to_numpy()


class ESMRanker:
    """ESM-only baseline: rank by Emission Spectroscopy Metric (Kempton et al. 2018) descending."""
    name = "ESM-Only Baseline"

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        esm = pd.to_numeric(
            df.get("emission_spectroscopy_metric", pd.Series(np.nan, index=df.index)),
            errors="coerce"
        ).fillna(0.0)
        return esm.to_numpy()


class HeuristicCompositeRanker:
    """ExoSignal composite heuristic baseline (target_priority_score)."""
    name = "Heuristic Composite (ExoSignal)"

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        scores = pd.to_numeric(
            df.get("target_priority_score", pd.Series(0.0, index=df.index)),
            errors="coerce"
        ).fillna(0.0)
        return scores.to_numpy()


# Alias for backward compatibility
ExoSignalV1Ranker = HeuristicCompositeRanker


class ESIRanker:
    """Earth Similarity Index alone (Schulze-Makuch et al. 2011)."""
    name = "ESI Heuristic Ranker"

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        esi = pd.to_numeric(df.get("earth_similarity", pd.Series(0.0, index=df.index)), errors="coerce").fillna(0.0)
        return esi.to_numpy()


class ModelARanker:
    """
    Model A: Supervised LightGBM Ranker with all features (including proxies).
    Trained strictly on historical train era (<= 2017), evaluated on out-of-time test set (2022-2026).
    """
    name = "Model A (LightGBM - All Features)"

    def __init__(self, random_state: int = 42):
        from app.ml.ltr_model import ExoSignalLTRModel
        self.ltr_model = ExoSignalLTRModel(feature_variant="A", random_state=random_state)
        self.is_fitted = False

    def fit(self, train_df: pd.DataFrame, val_df: Optional[pd.DataFrame] = None) -> "ModelARanker":
        self.ltr_model.fit(train_df, val_df)
        self.is_fitted = True
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("ModelARanker must be fitted before predict")
        return self.ltr_model.predict_raw_scores(df)


# Backward compatibility alias
SupervisedMLRanker = ModelARanker


class ModelBRanker:
    """
    Model B: Supervised LightGBM Ranker with raw physical features only (no proxy leakage).
    Trained strictly on historical train era (<= 2017), evaluated on out-of-time test set (2022-2026).
    """
    name = "Model B (LightGBM - Raw Features Only)"

    def __init__(self, random_state: int = 42):
        from app.ml.ltr_model import ExoSignalLTRModel
        self.ltr_model = ExoSignalLTRModel(feature_variant="B", random_state=random_state)
        self.is_fitted = False

    def fit(self, train_df: pd.DataFrame, val_df: Optional[pd.DataFrame] = None) -> "ModelBRanker":
        self.ltr_model.fit(train_df, val_df)
        self.is_fitted = True
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("ModelBRanker must be fitted before predict")
        return self.ltr_model.predict_raw_scores(df)


# ---------------------------------------------------------------------------
# Benchmark Suite Runner
# ---------------------------------------------------------------------------

class RankingBenchmarkSuite:
    """Orchestrates comparative model evaluation against ground truth across 7 benchmark baselines."""

    def __init__(self, k_list: Optional[List[int]] = None):
        self.k_list = k_list or [5, 10, 20]

    def evaluate_model(
        self,
        name: str,
        y_true_binary: np.ndarray,
        y_true_graded: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict[str, Any]:
        """Compute all ranking metrics for a specific model's predictions."""
        results: Dict[str, Any] = {"model_name": name}

        # Precision@5, 10, 20
        for k in [5, 10, 20]:
            results[f"precision@{k}"] = round(precision_at_k(y_true_binary, y_pred, k=k), 4)

        # Recall@10, 25, 50
        for k in [10, 25, 50]:
            results[f"recall@{k}"] = round(recall_at_k(y_true_binary, y_pred, k=k), 4)

        # NDCG@10
        results["ndcg@10"] = round(ndcg_at_k(y_true_graded, y_pred, k=10), 4)

        # Global ranking metrics
        results["map"] = round(mean_average_precision(y_true_binary, y_pred), 4)
        results["pr_auc"] = round(pr_auc_score(y_true_binary, y_pred), 4)

        return results

    def run_benchmark(
        self,
        full_df: pd.DataFrame,
        eval_split: str = "test"
    ) -> Dict[str, Any]:
        """
        Run full benchmark on temporal split across 7 rankers.

        Args:
            full_df: Complete processed exoplanet catalog
            eval_split: 'test' (2022-2026 out-of-time) or 'val' (2018-2021)
        """
        # 1. Generate ground truth labels
        df_with_gt = generate_ground_truth_labels(full_df)

        # 2. Split temporally (only transmission-eligible planets)
        train_df, val_df, test_df = split_temporal_dataset(df_with_gt)
        target_eval_df = test_df if eval_split == "test" else val_df

        y_true_binary = target_eval_df["ground_truth_binary"].to_numpy()
        y_true_graded = target_eval_df["ground_truth_graded"].to_numpy()

        # 3. Fit supervised rankers strictly on train set with validation early stopping
        model_a = ModelARanker(random_state=42)
        model_a.fit(train_df, val_df)

        model_b = ModelBRanker(random_state=42)
        model_b.fit(train_df, val_df)

        # 4. Instantiate all 7 models
        models = [
            RandomRanker(random_state=42),
            DistanceRanker(),
            TSMRanker(),
            ESMRanker(),
            HeuristicCompositeRanker(),
            model_a,
            model_b
        ]

        leaderboard = []
        for model in models:
            preds = model.predict(target_eval_df)
            metrics = self.evaluate_model(
                name=model.name,
                y_true_binary=y_true_binary,
                y_true_graded=y_true_graded,
                y_pred=preds
            )
            leaderboard.append(metrics)

        # Sort leaderboard by primary telescope objective: Precision@10, then MAP
        leaderboard.sort(key=lambda m: (m["precision@10"], m["map"]), reverse=True)

        benchmark_report = {
            "evaluation_split": eval_split,
            "train_set_size": len(train_df),
            "val_set_size": len(val_df),
            "test_set_size": len(test_df),
            "eval_set_size": len(target_eval_df),
            "eval_positive_rate": round(float(np.mean(y_true_binary)), 4),
            "primary_metric": "precision@10",
            "primary_metric_justification": (
                "Observing time on flagship space observatories (JWST/HST) is strictly capacity-constrained. "
                "Precision@10 measures the fraction of top-10 proposed targets that yield viable spectroscopic data, "
                "directly minimizing wasted multimillion-dollar observing proposals."
            ),
            "models_evaluated": len(leaderboard),
            "leaderboard": leaderboard
        }

        return benchmark_report

    def save_report(
        self,
        report: Dict[str, Any],
        output_dir: Path
    ) -> Tuple[Path, Path]:
        """Save JSON benchmark results and formatted Markdown summary."""
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "benchmark_report.json"
        md_path = output_dir / "benchmark_report.md"
        legacy_md_path = output_dir / "BENCHMARK_EVALUATION.md"

        # Write JSON
        with open(json_path, "w") as f:
            json.dump(report, f, indent=2)

        # Write Markdown Table
        headers = [
            "Model", "Precision@5", "Precision@10", "Precision@20",
            "Recall@10", "Recall@25", "Recall@50", "NDCG@10", "MAP", "PR-AUC"
        ]
        rows = []
        for m in report["leaderboard"]:
            rows.append(
                f"| **{m['model_name']}** | {m['precision@5']:.4f} | {m['precision@10']:.4f} | {m['precision@20']:.4f} | "
                f"{m['recall@10']:.4f} | {m['recall@25']:.4f} | {m['recall@50']:.4f} | "
                f"{m['ndcg@10']:.4f} | {m['map']:.4f} | {m['pr_auc']:.4f} |"
            )

        md_content = f"""# ExoSignal Model Evaluation Benchmark Report

## Operational Evaluation Summary
- **Evaluation Era**: Out-of-Time Test Set (Discovery Years >= 2022)
- **Train Set Size**: {report['train_set_size']} planets (Discovery Years <= 2017)
- **Validation Set Size**: {report['val_set_size']} planets (2018 - 2021)
- **Test Set Size**: {report['test_set_size']} planets (2022 - 2026)
- **Evaluation Positive Rate**: {report['eval_positive_rate'] * 100:.2f}%
- **Primary Optimization Metric**: `{report['primary_metric']}`

### Metric Justification
> {report['primary_metric_justification']}

## Leaderboard Comparison (7 Models)

| {' | '.join(headers)} |
| {' | '.join(['---'] * len(headers))} |
{chr(10).join(rows)}

## Scientific Ground Truth Formulation
Ground truth targets are determined by:
1. **NASA / STScI Approved JWST Atmospheric Transmission Spectroscopy Programs** (Cycles 1, 2, 3, and GTO accepted transmission spectroscopic follow-up targets).
2. Evaluated strictly on transmission-eligible planets to ensure physical observation feasibility.
"""
        with open(md_path, "w") as f:
            f.write(md_content)

        # Also write legacy path for compatibility
        with open(legacy_md_path, "w") as f:
            f.write(md_content)

        return json_path, md_path
