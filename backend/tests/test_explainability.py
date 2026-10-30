"""Test TreeSHAP explainability engine, mathematical exactness, and API endpoints."""

import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml.explainability import FEATURE_METADATA, SHAPExplainer
from app.services.query_engine import CatalogQueryEngine

client = TestClient(app)


@pytest.fixture(scope="module")
def query_engine():
    """Get singleton query engine."""
    return CatalogQueryEngine.get_instance()


@pytest.fixture(scope="module")
def explainer():
    """Get singleton SHAP explainer."""
    return SHAPExplainer.get_instance()


def test_shap_mathematical_exactness(explainer, query_engine):
    """
    Mathematical Exactness Invariant (Lundberg et al. 2020):
    Verify that sum(phi_i) + base_margin = predicted_margin holds to machine precision.
    """
    sample_targets = ["TOI-700 d", "TRAPPIST-1 e", "Kepler-186 f"]
    # Add first 5 planets from catalog
    catalog_sample = query_engine.query_planets(limit=5)
    for p in catalog_sample:
        if p["planet_name"] not in sample_targets:
            sample_targets.append(p["planet_name"])

    for name in sample_targets:
        row = query_engine.get_planet_by_name(name)
        if row is None:
            continue
        explanation = explainer.explain_planet(row)

        invariants = explanation["mathematical_invariants"]
        base_margin = invariants["base_margin"]
        sum_shap = invariants["sum_shap_margin"]
        pred_margin = invariants["predicted_margin"]
        rec_err = invariants["reconstruction_error"]

        # 1. Reconstruction error must be within numerical float precision (< 1e-4)
        assert rec_err < 1e-4, f"TreeSHAP conservation violated for {name}: error={rec_err}"
        assert abs((sum_shap + base_margin) - pred_margin) < 1e-4

        # 2. Score bounds
        assert 0.0 <= explanation["ml_priority_score"] <= 100.0
        assert 0.0 <= explanation["base_score"] <= 100.0


def test_shap_waterfall_structure(explainer, query_engine):
    """
    Verify structure and physical formatting of the single-planet waterfall explanation.
    """
    row = query_engine.get_planet_by_name("TOI-700 d")
    assert row is not None
    explanation = explainer.explain_planet(row)

    # Full waterfall must include all 21 model features
    waterfall = explanation["full_waterfall"]
    assert len(waterfall) == 21

    # Verify descending sort by absolute importance
    abs_vals = [item["abs_importance"] for item in waterfall]
    assert abs_vals == sorted(abs_vals, reverse=True)

    # Verify field completeness and formatting
    for item in waterfall:
        assert item["feature"] in FEATURE_METADATA
        assert len(item["display_name"]) > 0
        assert len(item["raw_value"]) > 0
        assert item["direction"] in ("positive", "negative")
        assert isinstance(item["score_impact"], float)

    # Positive drivers and negative barriers
    for pos in explanation["top_positive_drivers"]:
        assert pos["direction"] == "positive"
        assert pos["shap_value"] > 0
    assert len(explanation["top_positive_drivers"]) <= 5

    for neg in explanation["top_negative_barriers"]:
        assert neg["direction"] == "negative"
        assert neg["shap_value"] < 0
    assert len(explanation["top_negative_barriers"]) <= 5


def test_differential_attribution_comparison(explainer, query_engine):
    """
    Verify differential attribution Delta_phi = phi_A - phi_B between two distinct planets.
    """
    row_a = query_engine.get_planet_by_name("TOI-700 d")
    row_b = query_engine.get_planet_by_name("TRAPPIST-1 e")
    assert row_a is not None and row_b is not None

    diff_expl = explainer.explain_comparison(row_a, row_b)

    assert diff_expl["planet_a"] == "TOI-700 d"
    assert diff_expl["planet_b"] == "TRAPPIST-1 e"
    expected_delta = round(diff_expl["planet_a_score"] - diff_expl["planet_b_score"], 1)
    assert diff_expl["score_advantage"] == expected_delta

    diff_waterfall = diff_expl["differential_waterfall"]
    assert len(diff_waterfall) == 21

    for item in diff_waterfall:
        assert item["advantage"] in ("Planet A", "Planet B")
        if item["diff_shap"] > 0:
            assert item["advantage"] == "Planet A"
        else:
            assert item["advantage"] == "Planet B"


def test_differential_attribution_self_identity(explainer, query_engine):
    """
    Comparing a planet to itself must produce exact zero differential attributions.
    """
    row = query_engine.get_planet_by_name("TOI-700 d")
    assert row is not None

    diff_expl = explainer.explain_comparison(row, row)
    assert diff_expl["score_advantage"] == 0.0

    for item in diff_expl["differential_waterfall"]:
        assert abs(item["diff_shap"]) < 1e-6
        assert abs(item["diff_score_impact"]) < 1e-6


def test_api_explain_planet_endpoint():
    """Test GET /api/v1/planets/{planet_name}/explain endpoint."""
    resp = client.get("/api/v1/planets/TOI-700%20d/explain")
    assert resp.status_code == 200
    data = resp.json()
    assert data["planet_name"] == "TOI-700 d"
    assert "ml_priority_score" in data
    assert "mathematical_invariants" in data
    assert data["mathematical_invariants"]["reconstruction_error"] < 1e-4
    assert len(data["full_waterfall"]) == 21
    assert len(data["top_positive_drivers"]) <= 5


def test_api_explain_planet_not_found():
    """Test 404 behavior for non-existent target in explain endpoint."""
    resp = client.get("/api/v1/planets/NonExistentExoPlanet12345/explain")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_api_compare_explain_endpoint():
    """Test GET /api/v1/planets/compare-explain endpoint."""
    resp = client.get("/api/v1/planets/compare-explain?planet_a=TOI-700%20d&planet_b=TRAPPIST-1%20e")
    assert resp.status_code == 200
    data = resp.json()
    assert data["planet_a"] == "TOI-700 d"
    assert data["planet_b"] == "TRAPPIST-1 e"
    assert "score_advantage" in data
    assert "primary_drivers_for_advantage" in data
    assert len(data["differential_waterfall"]) == 21


def test_api_compare_explain_missing_planet():
    """Test 404 behavior when one of the compared planets does not exist."""
    resp = client.get("/api/v1/planets/compare-explain?planet_a=NonExistentPlanetXYZ&planet_b=TOI-700%20d")
    assert resp.status_code == 404
    assert "Planet A 'NonExistentPlanetXYZ' not found" in resp.json()["detail"]


def test_shap_inference_latency_benchmark(explainer, query_engine):
    """
    Latency benchmark: native C++ TreeSHAP (pred_contrib=True) must run in under 10ms per target.
    """
    row = query_engine.get_planet_by_name("TOI-700 d")
    assert row is not None
    planet_dict = row

    # Warmup
    explainer.explain_planet(planet_dict)

    latencies_ms = []
    for _ in range(50):
        t0 = time.perf_counter()
        explainer.explain_planet(planet_dict)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

    p50 = float(np.percentile(latencies_ms, 50))
    p95 = float(np.percentile(latencies_ms, 95))

    # Expect sub-35ms P95 latency for end-to-end Python Pandas + LightGBM C++ TreeSHAP
    assert p95 < 35.0, f"SHAP P95 latency exceeded 35ms: {p95:.2f}ms"
    assert p50 < 25.0, f"SHAP P50 latency exceeded 25ms: {p50:.2f}ms"
