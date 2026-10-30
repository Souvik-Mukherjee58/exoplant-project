"""Tests for ML ranking evaluation engine, ground truth formulation, and benchmark metrics."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedGroupKFold

from app.main import app
from app.ml.evaluation import (
    RankingBenchmarkSuite,
    compute_paired_comparison_vs_tsm,
    mean_average_precision,
    ndcg_at_k,
    pr_auc_score,
    precision_at_k,
    recall_at_k,
    split_temporal_dataset,
)
from app.ml.ground_truth import (
    calculate_tsm,
    estimate_planet_mass,
    generate_ground_truth_labels,
)
from app.services.data_processor import get_data_processor

# ---------------------------------------------------------------------------
# 1. Ranking Metric Unit Tests (Synthetic Invariants & Toy Examples)
# ---------------------------------------------------------------------------


def test_precision_at_k_synthetic():
    # 10 items, predictions ordered 0..9
    # Truth has positive labels at ranks 0, 1, 3
    y_true = np.array([1, 1, 0, 1, 0, 0, 0, 0, 0, 0])
    y_score = np.array([10, 9, 8, 7, 6, 5, 4, 3, 2, 1])

    # In top 2: 2 positives -> 2/2 = 1.0
    assert precision_at_k(y_true, y_score, k=2) == 1.0
    # In top 3: 2 positives -> 2/3 = 0.6667
    assert pytest.approx(precision_at_k(y_true, y_score, k=3), 0.01) == 0.6667
    # In top 5: 3 positives -> 3/5 = 0.60
    assert precision_at_k(y_true, y_score, k=5) == 0.60


def test_recall_at_k_synthetic():
    # Total relevant = 3
    y_true = np.array([1, 1, 0, 1, 0, 0, 0, 0, 0, 0])
    y_score = np.array([10, 9, 8, 7, 6, 5, 4, 3, 2, 1])

    # In top 2: 2 found out of 3 -> 2/3
    assert pytest.approx(recall_at_k(y_true, y_score, k=2), 0.01) == 0.6667
    # In top 4: 3 found out of 3 -> 3/3 = 1.0
    assert recall_at_k(y_true, y_score, k=4) == 1.0


def test_perfect_ranker_scores_one_and_reversed_scores_low():
    """Requirement 8: a perfect ranker scores 1.0 and a reversed ranker scores low."""
    y_true = np.array([1, 1, 0, 0, 0])
    y_graded = np.array([3, 2, 0, 0, 0])

    # Perfect ranker: perfect scores for all metrics
    perfect_score = np.array([10.0, 9.0, 3.0, 2.0, 1.0])
    assert precision_at_k(y_true, perfect_score, k=2) == 1.0
    assert recall_at_k(y_true, perfect_score, k=2) == 1.0
    assert ndcg_at_k(y_graded, perfect_score, k=2) == 1.0
    assert pr_auc_score(y_true, perfect_score) == 1.0
    assert mean_average_precision(y_true, perfect_score) == 1.0

    # Reversed ranker: worst possible scores
    reversed_score = np.array([1.0, 2.0, 8.0, 9.0, 10.0])
    assert precision_at_k(y_true, reversed_score, k=2) == 0.0
    assert recall_at_k(y_true, reversed_score, k=2) == 0.0
    assert ndcg_at_k(y_graded, reversed_score, k=2) < 0.2
    assert pr_auc_score(y_true, reversed_score) < 0.45
    assert mean_average_precision(y_true, reversed_score) < 0.45


def test_ap_matches_sklearn_on_toy_example():
    """Requirement 8: AP matches sklearn on a toy example."""
    # Toy example 1
    y_true_1 = np.array([1, 1, 0, 1, 0, 0])
    y_score_1 = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4])
    expected_1 = float(average_precision_score(y_true_1, y_score_1))

    assert pytest.approx(pr_auc_score(y_true_1, y_score_1), 1e-6) == expected_1
    assert pytest.approx(mean_average_precision(y_true_1, y_score_1), 1e-6) == expected_1

    # Toy example 2 (different permutation & values)
    y_true_2 = np.array([0, 1, 0, 0, 1, 1, 0])
    y_score_2 = np.array([0.1, 0.95, 0.2, 0.4, 0.85, 0.7, 0.3])
    expected_2 = float(average_precision_score(y_true_2, y_score_2))

    assert pytest.approx(pr_auc_score(y_true_2, y_score_2), 1e-6) == expected_2
    assert pytest.approx(mean_average_precision(y_true_2, y_score_2), 1e-6) == expected_2


def test_paired_comparison_bootstrap_ci():
    """Requirement 6: Per-fold difference with bootstrap CI states 'no significant difference' when CI includes 0."""
    # Two identical sets of model values -> difference = 0 -> CI spans 0
    vals_a = np.array([0.30, 0.32, 0.28, 0.35, 0.29] * 5)
    vals_b = np.array([0.30, 0.32, 0.28, 0.35, 0.29] * 5)
    res_identical = compute_paired_comparison_vs_tsm(vals_a, vals_b, n_resamples=1000, random_state=42)

    assert res_identical["diff_mean"] == 0.0
    assert res_identical["ci_includes_zero"] is True
    assert res_identical["statement"] == "no significant difference"

    # Clearly superior model -> CI strictly > 0
    vals_superior = vals_a + 0.50
    res_superior = compute_paired_comparison_vs_tsm(vals_superior, vals_b, n_resamples=1000, random_state=42)
    assert res_superior["ci_includes_zero"] is False
    assert res_superior["statement"] == "statistically significant improvement"


# ---------------------------------------------------------------------------
# 2. Ground Truth & Host Grouping Requirements
# ---------------------------------------------------------------------------


def test_mass_radius_empirical_fallback():
    # Earth (1.0 R_earth) -> ~0.97 M_earth
    m_earth = estimate_planet_mass(1.0)
    assert 0.8 <= m_earth <= 1.2

    # Sub-Neptune (2.0 R_earth) -> 2.69 * 2^0.93 ~ 5.1 M_earth
    m_subnep = estimate_planet_mass(2.0)
    assert 4.0 <= m_subnep <= 6.5


def test_kempton_tsm_calculation():
    # TRAPPIST-1 e parameters
    tsm = calculate_tsm(radius_earth=0.92, mass_earth=0.69, teq_k=251.0, r_star_solar=0.12, j_mag=11.35)
    assert pd.notna(tsm)
    assert tsm > 10.0, f"TRAPPIST-1 e must have strong TSM (got {tsm})"


def test_confirmed_jwst_targets_are_labeled():
    df = pd.DataFrame(
        {
            "planet_name": ["TRAPPIST-1 e", "LHS 1140 b", "FakePlanet-999 z"],
            "planet_radius": [0.92, 1.73, 50.0],
            "planet_mass": [0.69, 5.6, np.nan],
            "equilibrium_temperature": [251.0, 235.0, 50.0],
            "stellar_radius": [0.12, 0.21, 5.0],
            "stellar_effective_temperature": [2566.0, 3216.0, 2000.0],
            "j_magnitude": [11.35, 9.61, 22.0],
            "k_magnitude": [10.3, 8.8, 20.0],
            "hz_status": ["Inside HZ", "Inside HZ", "Outside HZ"],
        }
    )

    gt_df = generate_ground_truth_labels(df)
    t1e = gt_df[gt_df["planet_name"] == "TRAPPIST-1 e"].iloc[0]
    assert t1e["is_jwst_target"] == True
    assert t1e["ground_truth_binary"] == 1
    assert t1e["ground_truth_graded"] == 3


def test_folds_never_share_a_host():
    """Requirement 8: Folds never share a host across all 5 seeds."""
    processor = get_data_processor()
    catalog = processor.get_processed_data()

    suite = RankingBenchmarkSuite(seeds=[42, 43, 44, 45, 46], k_folds=5)
    eligible = suite._prepare_eligible_data(catalog)

    y_bin = eligible["ground_truth_binary"].to_numpy()
    groups = eligible["hostname"].to_numpy()

    for seed in [42, 43, 44, 45, 46]:
        sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        for train_idx, test_idx in sgkf.split(eligible, y_bin, groups):
            train_hosts = set(groups[train_idx])
            test_hosts = set(groups[test_idx])
            overlap = train_hosts.intersection(test_hosts)
            assert len(overlap) == 0, f"Seed {seed} leaked {len(overlap)} hosts across train and test folds!"


def test_every_fold_has_at_least_one_positive():
    """Requirement 8: Every fold has >=1 positive across all 5 seeds."""
    processor = get_data_processor()
    catalog = processor.get_processed_data()

    suite = RankingBenchmarkSuite(seeds=[42, 43, 44, 45, 46], k_folds=5)
    eligible = suite._prepare_eligible_data(catalog)

    y_bin = eligible["ground_truth_binary"].to_numpy()
    groups = eligible["hostname"].to_numpy()

    for seed in [42, 43, 44, 45, 46]:
        sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        for fold_idx, (_train_idx, test_idx) in enumerate(sgkf.split(eligible, y_bin, groups)):
            n_pos = int(np.sum(y_bin[test_idx] > 0))
            assert n_pos >= 1, f"Seed {seed} fold {fold_idx} has 0 positive targets!"


# ---------------------------------------------------------------------------
# 3. Temporal Split & Sanity Check Tests
# ---------------------------------------------------------------------------


def test_temporal_split_disjoint():
    processor = get_data_processor()
    catalog = processor.get_processed_data()

    train_df, val_df, test_df = split_temporal_dataset(catalog)

    assert not train_df.empty, "Train set must not be empty"
    assert not val_df.empty, "Validation set must not be empty"
    assert not test_df.empty, "Test set must not be empty"

    assert train_df["discovery_year"].max() <= 2017
    assert val_df["discovery_year"].min() >= 2018
    assert val_df["discovery_year"].max() <= 2021
    assert test_df["discovery_year"].min() >= 2022


# ---------------------------------------------------------------------------
# 4. End-to-End Evaluation Benchmark Tests
# ---------------------------------------------------------------------------


def test_benchmark_suite_execution():
    processor = get_data_processor()
    catalog = processor.get_processed_data()

    suite = RankingBenchmarkSuite(seeds=[42], k_folds=5)
    report = suite.run_benchmark(catalog, eval_split="test")

    assert report["evaluation_split"] == "test"
    assert report["models_evaluated"] >= 7
    assert "leaderboard" in report
    assert len(report["leaderboard"]) >= 7
    assert "primary_protocol" in report
    assert "secondary_protocol" in report
    assert "temporal_sanity_check" in report
    assert "limitations" in report
    assert len(report["limitations"]) == 3

    # Verify secondary protocol (Leave-One-Host-Out)
    loho = report["secondary_protocol"]
    assert loho["hosts_evaluated"] == 24
    assert len(loho["models"]) >= 7
    for m in loho["models"]:
        assert 1.0 <= m["median_rank"] <= loho["eligible_candidates_per_fold"]
        assert 0.0 <= m["pct_in_top_1_pct"] <= 100.0
        assert 0.0 <= m["pct_in_top_5_pct"] <= 100.0
        assert 0.0 <= m["pct_in_top_10_pct"] <= 100.0

    # Verify primary protocol metrics
    for model_res in report["leaderboard"]:
        for metric in ["precision@10", "precision@25", "recall@25", "recall@50", "recall@100", "ndcg@25", "ap"]:
            assert metric in model_res, f"Missing metric {metric} in {model_res['model_name']}"
            assert 0.0 <= model_res[metric] <= 1.0, f"Metric {metric} out of bounds in {model_res['model_name']}"
        assert "paired_vs_tsm_ap" in model_res


def test_production_top_50_has_no_ties():
    """Requirement 3: Verify the production top 50 ranking has no ties."""
    from app.ml.ltr_model import ExoSignalLTRModel

    processor = get_data_processor()
    catalog = processor.get_processed_data()

    # Load model and score entire catalog
    model = ExoSignalLTRModel.load()
    scored_catalog = model.score_catalog(catalog)

    top_50 = scored_catalog[scored_catalog["ml_rank"].between(1, 50)].sort_values("ml_rank")
    top_50_scores = top_50["priority_score"].to_numpy()

    # Check that in the top 50, all 50 scores are distinct
    n_distinct_top_50 = len(np.unique(top_50_scores))
    assert n_distinct_top_50 == 50, (
        f"Score collapse detected: expected 50 distinct scores in top 50, but found only {n_distinct_top_50}."
    )

    # Check deterministic tie-breaking produces strictly ascending integer ranks
    ranks = top_50["ml_rank"].to_numpy()
    assert np.array_equal(ranks, np.arange(1, 51)), f"Top 50 ranks must be contiguous 1..50, got {ranks}"


def test_api_benchmark_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/evaluation/benchmark?split=test")
    assert response.status_code == 200

    data = response.json()
    assert data["evaluation_split"] == "test"
    assert "leaderboard" in data
    assert len(data["leaderboard"]) >= 4


def test_labelled_planets_scored_out_of_fold():
    """
    Requirement 2: Scores shown for labelled planets must be out-of-fold (cross_val_predict with the same groups),
    so no planet is scored by a model trained on it.
    """
    processor = get_data_processor()
    catalog = processor.get_processed_data()

    # Confirm columns exist
    assert "already_observed_jwst" in catalog.columns
    assert "oof_priority_score" in catalog.columns
    assert "in_sample_priority_score" in catalog.columns

    labelled_mask = (catalog["already_observed_jwst"] == True) & (catalog["eligible_for_transmission"] == True)
    assert labelled_mask.sum() > 0, "Must have labelled transmission planets in catalog"

    # 1. Assert that in the catalog, priority_score for all labelled planets equals oof_priority_score
    labelled_planets = catalog[labelled_mask]
    np.testing.assert_array_almost_equal(
        labelled_planets["priority_score"].to_numpy(),
        labelled_planets["oof_priority_score"].to_numpy(),
        decimal=4,
        err_msg="Labelled planets must be scored with their out-of-fold prediction",
    )

    # 2. Verify that out-of-fold score differs from naive in-sample score for positives
    diffs = np.abs(
        labelled_planets["in_sample_priority_score"].to_numpy() - labelled_planets["oof_priority_score"].to_numpy()
    )
    assert np.mean(diffs) > 0.0, "OOF scores must reflect generalization and not match in-sample overfitting"

    # 3. Verify cross-validation grouping: for each labelled planet, verify its score matches OOF predictions
    from app.ml.ltr_model import compute_out_of_fold_predictions

    eligible_df = catalog[catalog["eligible_for_transmission"] == True].copy()
    oof_map = compute_out_of_fold_predictions(eligible_df)

    for p_name in labelled_planets["planet_name"].head(10):
        expected_oof = round(oof_map[p_name] * 100.0, 4)
        catalog_score = float(catalog.loc[catalog["planet_name"] == p_name, "priority_score"].iloc[0])
        assert abs(catalog_score - expected_oof) < 1e-3, (
            f"Score mismatch on {p_name}: catalog={catalog_score}, oof={expected_oof}"
        )


def test_recommendations_and_reasons_api():
    """Requirement 5: Test GET /api/v1/recommendations with exclude_observed, size_class, and plain English reasons."""
    client = TestClient(app)

    # Unobserved recommendations (default exclude_observed=True)
    resp = client.get("/api/v1/recommendations?limit=25")
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) == 25

    for r in recs:
        # Must NOT be an already observed planet
        assert r["already_observed_jwst"] is False
        assert "rank" in r and r["rank"] >= 1
        assert "percentile_rank_string" in r and r["percentile_rank_string"] is not None
        assert "Top " in r["percentile_rank_string"]
        assert "reasons" in r
        assert len(r["reasons"]) >= 1, f"Planet {r['planet_name']} must have plain English reasons"
        # Each reason must be a descriptive sentence
        for reason in r["reasons"]:
            assert isinstance(reason, str) and len(reason) > 15

    # Filter by size class
    resp_terrestrial = client.get("/api/v1/recommendations?size_class=terrestrial&limit=10")
    assert resp_terrestrial.status_code == 200
    data_terr = resp_terrestrial.json()
    for r in data_terr:
        assert r["kempton_size_class"] == "Terrestrial"
        assert r["planet_radius"] < 1.5

    # Validation known targets endpoint
    val_resp = client.get("/api/v1/validation/known-targets")
    assert val_resp.status_code == 200
    val_targets = val_resp.json()
    assert len(val_targets) >= 10
    for vt in val_targets:
        assert vt["already_observed_jwst"] is True
        assert vt["oof_ml_rank"] is not None
        assert vt["oof_priority_score"] is not None
