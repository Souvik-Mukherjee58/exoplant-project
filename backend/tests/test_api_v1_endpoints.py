"""Comprehensive FastAPI TestClient API tests for all ExoSignal endpoints.

Covers:
- Every endpoint happy path
- 404 for unknown planet
- 422 for bad params
- Pagination limits and bounds
- Response schema validation against Pydantic models
"""

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import (
    AnalysisResponse,
    AnomalyPCAResponse,
    ComparisonExplanationResponse,
    PlanetDetailResponse,
    PlanetExplanationResponse,
    PlanetResponse,
    RecommendationResponse,
)
from app.main import app


@pytest.fixture(scope="module")
def client():
    """Create FastAPI TestClient within lifespan context."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def sample_planet_names(client):
    """Retrieve 2 real planet names from the active catalog for detail queries."""
    resp = client.get("/api/v1/planets?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2, "Catalog must have at least 2 planets"
    return data[0]["planet_name"], data[1]["planet_name"]


# ---------------------------------------------------------------------------
# 1. Root & Health Endpoints
# ---------------------------------------------------------------------------


def test_root_endpoint(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "message" in body
    assert "version" in body
    assert "engine" in body


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "query_engine" in body
    assert "catalog_records" in body
    assert body["catalog_records"] > 0


def test_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert "service" in body
    assert "subsystems" in body


# ---------------------------------------------------------------------------
# 2. /api/v1/planets Endpoint
# ---------------------------------------------------------------------------


class TestPlanetsEndpoint:
    def test_planets_happy_path(self, client):
        resp = client.get("/api/v1/planets?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) <= 10
        # Validate schema on all returned items
        for item in data:
            validated = PlanetResponse(**item)
            assert validated.planet_name is not None
            assert 0.0 <= validated.target_priority_score <= 100.0

    def test_planets_pagination_limits(self, client):
        # Limit 5
        resp_5 = client.get("/api/v1/planets?limit=5&offset=0")
        assert resp_5.status_code == 200
        data_5 = resp_5.json()
        assert len(data_5) == 5

        # Offset 5
        resp_next = client.get("/api/v1/planets?limit=5&offset=5")
        assert resp_next.status_code == 200
        data_next = resp_next.json()
        assert len(data_next) == 5

        # Disjoint pages
        names_1 = {p["planet_name"] for p in data_5}
        names_2 = {p["planet_name"] for p in data_next}
        assert names_1.isdisjoint(names_2)

    def test_planets_bad_params_422(self, client):
        # limit < 1
        resp = client.get("/api/v1/planets?limit=0")
        assert resp.status_code == 422

        # limit > 500
        resp = client.get("/api/v1/planets?limit=501")
        assert resp.status_code == 422

        # negative offset
        resp = client.get("/api/v1/planets?offset=-1")
        assert resp.status_code == 422

        # invalid min_priority (< 0)
        resp = client.get("/api/v1/planets?min_priority=-5.0")
        assert resp.status_code == 422

        # invalid max_priority (> 100)
        resp = client.get("/api/v1/planets?max_priority=150.0")
        assert resp.status_code == 422

        # invalid sort_by
        resp = client.get("/api/v1/planets?sort_by=invalid_ranking_method")
        assert resp.status_code == 422

    def test_planets_inverted_priority_range_400(self, client):
        # min_priority > max_priority triggers 400 Bad Request
        resp = client.get("/api/v1/planets?min_priority=80.0&max_priority=20.0")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 3. /api/v1/planets/{planet_name} Endpoint
# ---------------------------------------------------------------------------


class TestPlanetDetailEndpoint:
    def test_planet_detail_happy_path(self, client, sample_planet_names):
        p1, _ = sample_planet_names
        resp = client.get(f"/api/v1/planets/{p1}")
        assert resp.status_code == 200
        body = resp.json()
        validated = PlanetDetailResponse(**body)
        assert validated.planet_name == p1
        assert "final_score" in validated.priority_components

    def test_planet_detail_unknown_planet_404(self, client):
        resp = client.get("/api/v1/planets/NonExistentPlanet_XYZ999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. /api/v1/planets/{planet_name}/explain Endpoint
# ---------------------------------------------------------------------------


class TestPlanetExplainEndpoint:
    def test_explain_happy_path(self, client, sample_planet_names):
        p1, _ = sample_planet_names
        resp = client.get(f"/api/v1/planets/{p1}/explain")
        assert resp.status_code == 200
        body = resp.json()
        validated = PlanetExplanationResponse(**body)
        assert validated.planet_name == p1
        assert len(validated.full_waterfall) > 0
        assert len(validated.top_positive_drivers) > 0

    def test_explain_unknown_planet_404(self, client):
        resp = client.get("/api/v1/planets/NonExistentPlanet_XYZ999/explain")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. /api/v1/planets/compare-explain Endpoint
# ---------------------------------------------------------------------------


class TestCompareExplainEndpoint:
    def test_compare_explain_happy_path(self, client, sample_planet_names):
        p1, p2 = sample_planet_names
        resp = client.get(f"/api/v1/planets/compare-explain?planet_a={p1}&planet_b={p2}")
        assert resp.status_code == 200
        body = resp.json()
        validated = ComparisonExplanationResponse(**body)
        assert validated.planet_a == p1
        assert validated.planet_b == p2
        assert len(validated.differential_waterfall) > 0

    def test_compare_explain_unknown_planet_404(self, client, sample_planet_names):
        p1, _ = sample_planet_names
        resp = client.get(f"/api/v1/planets/compare-explain?planet_a={p1}&planet_b=NonExistentPlanet_XYZ999")
        assert resp.status_code == 404

    def test_compare_explain_missing_param_422(self, client, sample_planet_names):
        p1, _ = sample_planet_names
        resp = client.get(f"/api/v1/planets/compare-explain?planet_a={p1}")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 6. Priority & Recommendations Endpoints
# ---------------------------------------------------------------------------


class TestRecommendationsAndTopTargets:
    def test_top_targets_happy_path(self, client):
        resp = client.get("/api/v1/top-targets?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for item in data:
            PlanetResponse(**item)

    def test_top_targets_bad_param_422(self, client):
        resp = client.get("/api/v1/top-targets?limit=0")
        assert resp.status_code == 422

    def test_known_targets_happy_path(self, client):
        resp = client.get("/api/v1/validation/known-targets")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for item in data:
            PlanetResponse(**item)

    def test_recommendations_happy_path(self, client):
        resp = client.get("/api/v1/recommendations?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for item in data:
            RecommendationResponse(**item)

    def test_recommendations_bad_param_422(self, client):
        resp = client.get("/api/v1/recommendations?limit=-1")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 7. Analytics & ML Registry Endpoints
# ---------------------------------------------------------------------------


class TestAnalyticsAndRegistry:
    def test_analysis_endpoint_happy_path(self, client):
        resp = client.get("/api/v1/analysis")
        assert resp.status_code == 200
        body = resp.json()
        validated = AnalysisResponse(**body)
        assert validated.total_planets > 0
        assert "mean" in validated.score_distribution
        assert len(validated.top_targets) > 0

    def test_anomaly_pca_endpoint_happy_path(self, client):
        resp = client.get("/api/v1/anomaly-pca")
        assert resp.status_code == 200
        body = resp.json()
        validated = AnomalyPCAResponse(**body)
        assert len(validated.planets) > 0
        assert len(validated.pca_x) > 0
        assert len(validated.pca_y) > 0

    def test_ltr_info_endpoint(self, client):
        resp = client.get("/api/v1/models/ltr/info")
        assert resp.status_code == 200
        body = resp.json()
        assert "algorithm" in body or "model_name" in body

    def test_ltr_feature_importance_endpoint(self, client):
        resp = client.get("/api/v1/models/ltr/feature-importance")
        assert resp.status_code == 200
        body = resp.json()
        assert "all_features" in body or "features" in body or "error" in body

    def test_registry_versions_endpoint(self, client):
        resp = client.get("/api/v1/models/registry/versions")
        assert resp.status_code == 200
        body = resp.json()
        assert "versions" in body

    def test_registry_active_endpoint(self, client):
        resp = client.get("/api/v1/models/registry/active")
        assert resp.status_code == 200
        body = resp.json()
        assert "version" in body or "artifacts" in body

    def test_registry_validate_unknown_version(self, client):
        resp = client.get("/api/v1/models/registry/validate/v_nonexistent_9999")
        assert resp.status_code in [200, 404]
        if resp.status_code == 200:
            assert resp.json().get("valid") is False
