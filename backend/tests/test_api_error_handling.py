"""Test API error handling and validation."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_planets_empty_filter():
    """Test planets endpoint with empty result (filter too restrictive)."""
    response = client.get("/api/v1/planets?min_priority=95&max_priority=100")
    assert response.status_code == 200
    # May return empty list or planets in that range
    data = response.json()
    assert isinstance(data, list)


def test_planets_invalid_priority_range():
    """Test planets endpoint with invalid priority range."""
    response = client.get("/api/v1/planets?min_priority=50&max_priority=30")
    # Must return 400 Bad Request for min_priority > max_priority
    assert response.status_code == 400
    assert "cannot be greater than" in response.json()["detail"]


def test_planet_exact_match_no_substring():
    """Verify that substring planet queries do NOT mistakenly match partial names (C6)."""
    # Kepler-1 is not a full planet name (e.g. Kepler-15 b), should return 404
    response = client.get("/api/v1/planets/Kepler-1")
    assert response.status_code == 404

    # Single character query 'b' should not match Kepler-6 b
    response_b = client.get("/api/v1/planets/b")
    assert response_b.status_code == 404


def test_planet_not_found():
    """Test planet detail endpoint with non-existent planet."""
    response = client.get("/api/v1/planets/NonExistentPlanet")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_planet_empty_name():
    """Test planet detail endpoint with invalid name pattern."""
    # Use a name that won't match anything
    response = client.get("/api/v1/planets/ThisPlanetDoesNotExist12345")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_top_targets_empty():
    """Test top targets with very high minimum priority."""
    response = client.get("/api/v1/top-targets?min_priority=95")
    assert response.status_code == 200
    # May return empty list or planets in that range
    data = response.json()
    assert isinstance(data, list)


def test_analysis_endpoint():
    """Test analysis endpoint returns valid structure."""
    response = client.get("/api/v1/analysis")
    assert response.status_code == 200
    data = response.json()
    assert "total_planets" in data
    assert "score_distribution" in data
    assert "top_targets" in data
    assert "anomaly_distribution" in data
    assert "hz_distribution" in data
    assert "discovery_method_distribution" in data


def test_planets_pagination():
    """Test planets endpoint pagination."""
    response = client.get("/api/v1/planets?limit=5&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 5


def test_planets_limit_validation():
    """Test planets endpoint limit validation."""
    # Test max limit
    response = client.get("/api/v1/planets?limit=1000")
    # Should respect max limit of 500
    assert response.status_code in [200, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
