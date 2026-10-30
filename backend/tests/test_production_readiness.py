"""Tests for production hardening: readiness probe, consistent error schemas,

rate limiting, ETag caching, gzip compression, and zero per-request disk reads.
"""

import builtins
import json
import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability import JSONFormatter


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. /ready Endpoint (Readiness Probe) & /health (Liveness Probe)
# ---------------------------------------------------------------------------


def test_ready_endpoint_happy_path(client):
    """Readiness probe must return 200, status 'ready', DuckDB OK, and catalog count."""
    resp = client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["duckdb"] == "ok"
    assert "artifact_version" in data
    assert data["catalog_records"] > 0


def test_health_endpoint_liveness(client):
    """Liveness probe must return 200, status 'ok'."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# 2. Structured JSON Logging and Request ID
# ---------------------------------------------------------------------------


def test_request_id_header_propagation(client):
    """API must propagate client-provided X-Request-ID or generate a unique one."""
    custom_id = "test-custom-req-id-12345"
    resp = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == custom_id

    # Auto-generated ID
    resp2 = client.get("/health")
    assert "X-Request-ID" in resp2.headers
    assert len(resp2.headers["X-Request-ID"]) > 0


def test_json_formatter_structure():
    """JSONFormatter must produce valid machine-parseable JSON with standard keys."""
    formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    record = logging.LogRecord(
        name="exosignal.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message with param: %s",
        args=("value1",),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert "timestamp" in parsed
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "exosignal.test"
    assert parsed["message"] == "Test message with param: value1"


# ---------------------------------------------------------------------------
# 3. Consistent Error Response Schema
# ---------------------------------------------------------------------------


def test_consistent_error_schema_404(client):
    """404 Not Found must adhere to the unified consistent error response schema."""
    resp = client.get("/api/v1/planets/NonExistentPlanet_XYZ_9999")
    assert resp.status_code == 404
    data = resp.json()

    # Backwards-compatible detail
    assert "detail" in data
    assert "not found" in data["detail"].lower()

    # Unified structured error block
    assert "error" in data
    err = data["error"]
    assert err["code"] == "NOT_FOUND"
    assert err["status_code"] == 404
    assert "not found" in err["message"].lower()
    assert "request_id" in err


def test_consistent_error_schema_400(client):
    """400 Bad Request must adhere to the unified consistent error response schema."""
    resp = client.get("/api/v1/planets?min_priority=90.0&max_priority=20.0")
    assert resp.status_code == 400
    data = resp.json()

    assert "detail" in data
    assert "error" in data
    err = data["error"]
    assert err["code"] == "BAD_REQUEST"
    assert err["status_code"] == 400
    assert "cannot be greater than" in err["message"]


def test_consistent_error_schema_422(client):
    """422 Validation Error must adhere to the unified consistent error response schema."""
    resp = client.get("/api/v1/planets?limit=0")
    assert resp.status_code == 422
    data = resp.json()

    assert "detail" in data
    assert "error" in data
    err = data["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert err["status_code"] == 422
    assert "validation" in err["message"].lower()
    assert isinstance(err["details"], list)


# ---------------------------------------------------------------------------
# 4. ETag and Cache-Control on Read-Only Endpoints
# ---------------------------------------------------------------------------


def test_etag_and_cache_control_headers(client):
    """Read-only endpoints must return ETag and Cache-Control headers."""
    resp = client.get("/api/v1/planets?limit=5")
    assert resp.status_code == 200
    assert "ETag" in resp.headers
    assert "Cache-Control" in resp.headers
    assert "public" in resp.headers["Cache-Control"]
    assert "must-revalidate" in resp.headers["Cache-Control"]


def test_etag_304_not_modified(client):
    """Sending matching If-None-Match header must return 304 Not Modified."""
    resp = client.get("/api/v1/planets?limit=5")
    assert resp.status_code == 200
    etag = resp.headers["ETag"]

    # Request with If-None-Match
    resp_cached = client.get("/api/v1/planets?limit=5", headers={"If-None-Match": etag})
    assert resp_cached.status_code == 304
    assert resp_cached.text == ""
    assert resp_cached.headers.get("ETag") == etag


# ---------------------------------------------------------------------------
# 5. Gzip Compression
# ---------------------------------------------------------------------------


def test_gzip_compression(client):
    """Large responses must be gzip-compressed when client sends Accept-Encoding: gzip."""
    resp = client.get("/api/v1/planets?limit=100", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("Content-Encoding") == "gzip"


# ---------------------------------------------------------------------------
# 6. Simple Rate Limiting
# ---------------------------------------------------------------------------


def test_rate_limiting_headers(client):
    """Every request must include X-RateLimit-Limit and X-RateLimit-Remaining headers."""
    resp = client.get("/api/v1/planets?limit=2")
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers


def test_rate_limiting_exceeded():
    """Exceeding the rate limit must return 429 Too Many Requests with consistent schema."""
    from starlette.testclient import TestClient

    from app.main import app

    # Set temporary low limit on app.state
    app.state.rate_limit_per_minute = 3
    try:
        with TestClient(app) as test_client:
            # Send 5 requests from same IP
            responses = [test_client.get("/api/v1/planets?limit=1") for _ in range(5)]
            statuses = [r.status_code for r in responses]

            # At least one request must have been rate-limited
            assert 429 in statuses, f"Expected 429 status in {statuses}"
            rate_limited_resp = next(r for r in responses if r.status_code == 429)
            assert "Retry-After" in rate_limited_resp.headers
            data = rate_limited_resp.json()
            assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            assert data["error"]["status_code"] == 429
    finally:
        app.state.rate_limit_per_minute = None


# ---------------------------------------------------------------------------
# 7. Requirement 2: Zero Per-Request Disk Reads
# ---------------------------------------------------------------------------


def test_zero_disk_reads_per_request(client):
    """
    Requirement 2:
    Load artifact once at startup; endpoints read from memory/DuckDB;
    NO per-request file reads.
    """
    # Warm up queries
    client.get("/api/v1/planets?limit=5")

    opened_files = []
    original_open = builtins.open

    def tracked_open(file, *args, **kwargs):
        opened_files.append(str(file))
        return original_open(file, *args, **kwargs)

    with patch("builtins.open", side_effect=tracked_open):
        with patch("pandas.read_parquet", side_effect=AssertionError("read_parquet called during request!")):
            with patch("pandas.read_csv", side_effect=AssertionError("read_csv called during request!")):
                # Execute core endpoints
                r_planets = client.get("/api/v1/planets?limit=10")
                assert r_planets.status_code == 200

                r_top = client.get("/api/v1/top-targets?limit=5")
                assert r_top.status_code == 200

                r_detail = client.get("/api/v1/planets/TOI-700%20d")
                assert r_detail.status_code == 200

                r_explain = client.get("/api/v1/planets/TOI-700%20d/explain")
                assert r_explain.status_code == 200

                r_explain_alias = client.get("/api/v1/explain/TOI-700%20d")
                assert r_explain_alias.status_code == 200

                r_analysis = client.get("/api/v1/analysis")
                assert r_analysis.status_code == 200

                r_pca = client.get("/api/v1/anomaly-pca")
                assert r_pca.status_code == 200

                r_rec = client.get("/api/v1/recommendations?limit=5")
                assert r_rec.status_code == 200

                r_ltr = client.get("/api/v1/models/ltr/info")
                assert r_ltr.status_code == 200

                r_feat = client.get("/api/v1/models/ltr/feature-importance")
                assert r_feat.status_code == 200

    # Verify no parquet, csv, joblib, or artifact json files were opened on disk
    artifact_data_opens = [
        f
        for f in opened_files
        if any(f.endswith(ext) for ext in (".parquet", ".csv", ".joblib", ".json"))
        and ("artifacts" in f or "data" in f)
    ]
    assert artifact_data_opens == [], f"Per-request disk file reads detected: {artifact_data_opens}"
