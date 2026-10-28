"""Tests for ML ranking evaluation engine, ground truth formulation, and benchmark metrics."""

import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.ml.ground_truth import (
    calculate_tsm,
    calculate_esm,
    estimate_planet_mass,
    generate_ground_truth_labels,
    CONFIRMED_JWST_ATMOSPHERIC_TARGETS
)
from app.ml.evaluation import (
    precision_at_k,
    recall_at_k,
    ndcg_at_k,
    mean_average_precision,
    pr_auc_score,
    split_temporal_dataset,
    RankingBenchmarkSuite
)
from app.services.data_processor import get_data_processor


# ---------------------------------------------------------------------------
# 1. Ranking Metric Unit Tests (Synthetic Invariants)
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


def test_ndcg_at_k_synthetic():
    # Ideal order: scores match graded relevance exactly
    y_graded = np.array([3, 2, 1, 0])
    y_ideal_score = np.array([4, 3, 2, 1])
    assert ndcg_at_k(y_graded, y_ideal_score, k=4) == 1.0

    # Reversed order: worst possible ranking -> NDCG strictly < 1.0
    y_reversed_score = np.array([1, 2, 3, 4])
    ndcg_rev = ndcg_at_k(y_graded, y_reversed_score, k=4)
    assert 0.0 <= ndcg_rev < 1.0


def test_mean_average_precision_synthetic():
    # Perfect ranking
    y_true = np.array([1, 1, 0, 0])
    y_score = np.array([4, 3, 2, 1])
    assert mean_average_precision(y_true, y_score) == 1.0

    # Inverse ranking (all irrelevants first)
    y_score_bad = np.array([1, 2, 3, 4])
    ap_bad = mean_average_precision(y_true, y_score_bad)
    assert ap_bad < 0.5


# ---------------------------------------------------------------------------
# 2. Ground Truth & Astrophysical Formulation Tests
# ---------------------------------------------------------------------------

def test_mass_radius_empirical_fallback():
    # Earth (1.0 R_earth) -> ~0.97 M_earth
    m_earth = estimate_planet_mass(1.0)
    assert 0.8 <= m_earth <= 1.2

    # Sub-Neptune (2.0 R_earth) -> 2.69 * 2^0.93 ~ 5.1 M_earth
    m_subnep = estimate_planet_mass(2.0)
    assert 4.0 <= m_subnep <= 6.5


def test_kempton_tsm_calculation():
    # Test typical TRAPPIST-1 e parameters:
    # R ~ 0.92 R_earth, M ~ 0.69 M_earth, Teq ~ 251 K, R_* ~ 0.12 R_sun, J ~ 11.35
    tsm = calculate_tsm(
        radius_earth=0.92,
        mass_earth=0.69,
        teq_k=251.0,
        r_star_solar=0.12,
        j_mag=11.35
    )
    assert pd.notna(tsm)
    assert tsm > 10.0, f"TRAPPIST-1 e must have strong TSM (got {tsm})"


def test_confirmed_jwst_targets_are_labeled():
    df = pd.DataFrame({
        "planet_name": ["TRAPPIST-1 e", "LHS 1140 b", "FakePlanet-999 z"],
        "planet_radius": [0.92, 1.73, 50.0],
        "planet_mass": [0.69, 5.6, np.nan],
        "equilibrium_temperature": [251.0, 235.0, 50.0],
        "stellar_radius": [0.12, 0.21, 5.0],
        "stellar_effective_temperature": [2566.0, 3216.0, 2000.0],
        "j_magnitude": [11.35, 9.61, 22.0],
        "k_magnitude": [10.3, 8.8, 20.0],
        "hz_status": ["Inside HZ", "Inside HZ", "Outside HZ"]
    })

    gt_df = generate_ground_truth_labels(df)

    t1e = gt_df[gt_df["planet_name"] == "TRAPPIST-1 e"].iloc[0]
    assert t1e["is_jwst_target"] == True
    assert t1e["ground_truth_binary"] == 1
    assert t1e["ground_truth_graded"] == 3

    fake = gt_df[gt_df["planet_name"] == "FakePlanet-999 z"].iloc[0]
    assert fake["is_jwst_target"] == False
    assert fake["ground_truth_binary"] == 0
    assert fake["ground_truth_graded"] == 0


# ---------------------------------------------------------------------------
# 3. Temporal Split & Leakage Prevention Tests
# ---------------------------------------------------------------------------

def test_temporal_split_disjoint():
    processor = get_data_processor()
    catalog = processor.get_processed_data()

    train_df, val_df, test_df = split_temporal_dataset(catalog)

    assert not train_df.empty, "Train set must not be empty"
    assert not val_df.empty, "Validation set must not be empty"
    assert not test_df.empty, "Test set must not be empty"

    # Verify strict temporal cutoff
    assert train_df["discovery_year"].max() <= 2017, "Train set cannot contain planets discovered after 2017"
    assert val_df["discovery_year"].min() >= 2018, "Validation set cannot contain planets discovered before 2018"
    assert val_df["discovery_year"].max() <= 2021, "Validation set cannot contain planets discovered after 2021"
    assert test_df["discovery_year"].min() >= 2022, "Test set cannot contain planets discovered before 2022"

    # Verify zero planet name leakage across splits
    train_names = set(train_df["planet_name"])
    val_names = set(val_df["planet_name"])
    test_names = set(test_df["planet_name"])

    assert len(train_names.intersection(val_names)) == 0, "Train and Validation sets must have zero overlap"
    assert len(train_names.intersection(test_names)) == 0, "Train and Test sets must have zero overlap"
    assert len(val_names.intersection(test_names)) == 0, "Validation and Test sets must have zero overlap"


# ---------------------------------------------------------------------------
# 4. End-to-End Evaluation Benchmark Tests
# ---------------------------------------------------------------------------

def test_benchmark_suite_execution():
    processor = get_data_processor()
    catalog = processor.get_processed_data()

    suite = RankingBenchmarkSuite()
    report = suite.run_benchmark(catalog, eval_split="test")

    assert report["evaluation_split"] == "test"
    assert report["models_evaluated"] == 7
    assert "leaderboard" in report
    assert len(report["leaderboard"]) == 7

    model_names = [m["model_name"] for m in report["leaderboard"]]
    expected_models = [
        "Random Baseline",
        "Distance-Only Baseline",
        "TSM-Only Baseline",
        "ESM-Only Baseline",
        "Heuristic Composite (ExoSignal)",
        "Model A (LightGBM - All Features)",
        "Model B (LightGBM - Raw Features Only)"
    ]
    for expected in expected_models:
        assert expected in model_names, f"Expected {expected} in benchmark leaderboard"

    # Verify each model has valid metrics within [0, 1]
    for model_res in report["leaderboard"]:
        for metric in ["precision@5", "precision@10", "precision@20", "recall@10", "recall@25", "recall@50", "ndcg@10", "map", "pr_auc"]:
            assert metric in model_res, f"Missing metric {metric} in {model_res['model_name']}"
            assert 0.0 <= model_res[metric] <= 1.0, f"Metric {metric} out of bounds in {model_res['model_name']}"


def test_api_benchmark_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/evaluation/benchmark?split=test")
    assert response.status_code == 200

    data = response.json()
    assert data["evaluation_split"] == "test"
    assert "leaderboard" in data
    assert len(data["leaderboard"]) >= 4
    assert data["primary_metric"] == "precision@10"
