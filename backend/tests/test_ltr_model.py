"""Tests for Supervised Learning-to-Rank (LTR) LightGBM model, feature importances, and endpoints."""

import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml.evaluation import split_temporal_dataset
from app.ml.ground_truth import generate_ground_truth_labels
from app.ml.ltr_model import (
    ExoSignalClassifierRanker,
    ExoSignalLTRModel,
    LTRFeatureExtractor,
)
from app.services.data_processor import get_data_processor


@pytest.fixture(scope="module")
def processed_df():
    """Load catalog with ground truth labels."""
    processor = get_data_processor()
    catalog = processor.get_processed_data()
    return generate_ground_truth_labels(catalog)


# ---------------------------------------------------------------------------
# 1. Feature Extractor Unit Tests
# ---------------------------------------------------------------------------


def test_ltr_feature_extractor_dimensions_and_imputation(processed_df):
    # Test Variant A (Full feature set)
    extractor_a = LTRFeatureExtractor(feature_variant="A")
    extractor_a.fit(processed_df)

    assert extractor_a.is_fitted
    assert len(extractor_a.feature_names) == 21
    assert "transmission_snr_proxy" in extractor_a.feature_names
    assert "transit_depth_proxy" in extractor_a.feature_names
    assert "scale_height_proxy" in extractor_a.feature_names

    X_a = extractor_a.transform(processed_df)
    assert X_a.shape == (len(processed_df), 21)
    assert not np.isnan(X_a).any(), "Variant A features must have zero NaNs"

    # Test Variant B (No proxy leakage)
    extractor_b = LTRFeatureExtractor(feature_variant="B")
    extractor_b.fit(processed_df)

    assert extractor_b.is_fitted
    assert len(extractor_b.feature_names) == 18
    assert "transmission_snr_proxy" not in extractor_b.feature_names
    assert "transit_depth_proxy" not in extractor_b.feature_names
    assert "scale_height_proxy" not in extractor_b.feature_names

    X_b = extractor_b.transform(processed_df)
    assert X_b.shape == (len(processed_df), 18)
    assert not np.isnan(X_b).any(), "Variant B features must have zero NaNs"


def test_mass_radius_imputation_in_extractor():
    """Verify that rows missing mass get positive physical masses, not 0 or NaN."""
    extractor = LTRFeatureExtractor()
    raw = pd.DataFrame(
        {
            "planet_radius": [1.0, 2.0],
            "planet_mass": [np.nan, np.nan],
            "equilibrium_temperature": [288.0, 400.0],
            "stellar_effective_temperature": [5780.0, 4500.0],
            "stellar_radius": [1.0, 0.7],
            "semi_major_axis": [1.0, 0.2],
            "distance": [10.0, 25.0],
            "j_magnitude": [8.0, 10.0],
            "k_magnitude": [7.5, 9.2],
        }
    )
    extractor.fit(raw)
    raw_feats = extractor._extract_raw_features(raw)

    assert raw_feats.loc[0, "planet_mass"] > 0.5, "Mass for 1.0 R_earth must be imputed positive"
    assert raw_feats.loc[1, "planet_mass"] > 3.0, "Mass for 2.0 R_earth must be larger"
    assert raw_feats.loc[0, "bulk_density_proxy"] > 0.1


# ---------------------------------------------------------------------------
# 2. LTR Model Training, Invariants & Monotonicity Tests
# ---------------------------------------------------------------------------


def test_ltr_model_training_and_convergence(processed_df):
    train_df, val_df, test_df = split_temporal_dataset(processed_df)

    # Test Model A
    model_a = ExoSignalLTRModel(feature_variant="A", n_estimators=50, learning_rate=0.08, random_state=42)
    model_a.fit(train_df, val_df)

    assert model_a.is_fitted
    assert model_a.training_metadata["train_samples"] == len(train_df)
    assert len(model_a.feature_importances["top_features"]) == 10

    scores_a = model_a.predict_priority_scores(test_df)
    assert len(scores_a) == len(test_df)
    assert np.all((scores_a >= 0.0) & (scores_a <= 100.0))

    metrics_a = model_a.evaluate(test_df)
    for k in [
        "precision@5",
        "precision@10",
        "precision@20",
        "recall@10",
        "recall@25",
        "recall@50",
        "ndcg@10",
        "map",
        "pr_auc",
    ]:
        assert k in metrics_a, f"Missing metric {k}"
        assert 0.0 <= metrics_a[k] <= 1.0, f"Metric {k} must be in [0, 1], got {metrics_a[k]}"

    # Test Model B (raw features)
    model_b = ExoSignalClassifierRanker(feature_variant="B", n_estimators=50, learning_rate=0.08, random_state=42)
    model_b.fit(train_df, val_df)
    assert model_b.is_fitted
    metrics_b = model_b.evaluate(test_df)
    for k in [
        "precision@5",
        "precision@10",
        "precision@20",
        "recall@10",
        "recall@25",
        "recall@50",
        "ndcg@10",
        "map",
        "pr_auc",
    ]:
        assert k in metrics_b
        assert 0.0 <= metrics_b[k] <= 1.0


def test_ltr_model_serialization(tmp_path, processed_df):
    train_df, _, _ = split_temporal_dataset(processed_df)
    model = ExoSignalLTRModel(n_estimators=20, random_state=42)
    model.fit(train_df.head(200))

    save_path = tmp_path / "test_ltr.joblib"
    model.save(str(save_path))
    assert save_path.exists()

    loaded = ExoSignalLTRModel.load(str(save_path))
    assert loaded.is_fitted

    preds_orig = model.predict_priority_scores(train_df.head(20))
    preds_loaded = loaded.predict_priority_scores(train_df.head(20))
    np.testing.assert_array_almost_equal(preds_orig, preds_loaded)


def test_ltr_model_monotonicity(processed_df):
    """
    Test astrophysical monotonicity:
    A target that is brighter (lower magnitude) and closer with identical physical parameters
    must receive a score greater than or equal to the fainter target.
    """
    train_df, _, _ = split_temporal_dataset(processed_df)
    model = ExoSignalLTRModel(n_estimators=40, random_state=42)
    model.fit(train_df.head(400))

    bright_target = pd.DataFrame(
        [
            {
                "planet_name": "Bright Target",
                "planet_radius": 1.2,
                "planet_mass": 2.0,
                "orbital_period": 10.0,
                "semi_major_axis": 0.08,
                "equilibrium_temperature": 300.0,
                "stellar_effective_temperature": 3500.0,
                "stellar_radius": 0.35,
                "stellar_mass": 0.35,
                "stellar_metallicity": 0.1,
                "distance": 8.0,  # Very close
                "j_magnitude": 6.5,  # Very bright infrared
                "k_magnitude": 5.8,
                "earth_similarity": 0.88,
                "hz_status": "Inside HZ",
            }
        ]
    )

    faint_target = pd.DataFrame(
        [
            {
                "planet_name": "Faint Target",
                "planet_radius": 1.2,
                "planet_mass": 2.0,
                "orbital_period": 10.0,
                "semi_major_axis": 0.08,
                "equilibrium_temperature": 300.0,
                "stellar_effective_temperature": 3500.0,
                "stellar_radius": 0.35,
                "stellar_mass": 0.35,
                "stellar_metallicity": 0.1,
                "distance": 150.0,  # Far away
                "j_magnitude": 16.5,  # Extremely faint
                "k_magnitude": 15.8,
                "earth_similarity": 0.88,
                "hz_status": "Inside HZ",
            }
        ]
    )

    score_bright = model.predict_priority_scores(bright_target)[0]
    score_faint = model.predict_priority_scores(faint_target)[0]

    assert score_bright >= score_faint, f"Bright target ({score_bright}) must score >= faint target ({score_faint})"


def test_catalog_scoring_and_rank_deltas(processed_df):
    train_df, _, _ = split_temporal_dataset(processed_df)
    model = ExoSignalLTRModel(n_estimators=30, random_state=42)
    model.fit(train_df.head(300))

    scored = model.score_catalog(processed_df.head(50))
    assert "ml_priority_score" in scored.columns
    assert "ml_rank" in scored.columns
    assert "heuristic_rank" in scored.columns
    assert "rank_delta" in scored.columns

    # Verify rank ranges
    assert scored["ml_rank"].min() == 1
    assert scored["ml_rank"].max() <= 50
    # Delta should be difference between heuristic and ML
    delta_check = scored["heuristic_rank"] - scored["ml_rank"]
    pd.testing.assert_series_equal(scored["rank_delta"], delta_check, check_names=False)


# ---------------------------------------------------------------------------
# 3. API Endpoints & Latency Tests
# ---------------------------------------------------------------------------


def test_api_ltr_endpoints():
    client = TestClient(app)

    # 1. Model Info Endpoint
    info_resp = client.get("/api/v1/models/ltr/info")
    assert info_resp.status_code == 200
    info_data = info_resp.json()
    assert "algorithm" in info_data
    assert any(term in info_data["algorithm"] for term in ("LightGBM", "Logistic Regression", "Regularized"))

    # 2. Feature Importance Endpoint
    feat_resp = client.get("/api/v1/models/ltr/feature-importance")
    assert feat_resp.status_code == 200

    # 3. Planets list with sort_by=ml
    planets_resp = client.get("/api/v1/planets?limit=10&sort_by=ml")
    assert planets_resp.status_code == 200
    planets = planets_resp.json()
    assert len(planets) == 10
    assert "planet_name" in planets[0]
    assert "target_priority_score" in planets[0]


def test_ltr_inference_latency(processed_df):
    """Ensure inference latency is suitable for real-time API queries (< 50ms for 100 planets)."""
    train_df, _, _ = split_temporal_dataset(processed_df)
    model = ExoSignalLTRModel(n_estimators=50, random_state=42)
    model.fit(train_df.head(300))

    sample_100 = processed_df.head(100)

    start = time.perf_counter()
    _ = model.predict_priority_scores(sample_100)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert elapsed_ms < 100.0, f"Inference took {elapsed_ms:.2f}ms, expected < 100ms"
