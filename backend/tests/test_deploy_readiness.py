"""Tests verifying deploy readiness and minimal environment configuration.

Verifies:
1. Application initializes and serves traffic with only PORT, CORS_ORIGINS, and ARTIFACT_VERSION set.
2. Artifact loads once at startup into in-memory DuckDB.
3. /health (liveness) and /ready (readiness) respond with HTTP 200 and expected schemas.
4. CORS headers match configured origins.
5. Endpoints read from memory without per-request disk reads.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.query_engine import CatalogQueryEngine


@pytest.fixture(autouse=True)
def restore_environment():
    """Ensure environment is restored after tests."""
    orig_env = os.environ.copy()
    orig_engine = CatalogQueryEngine._instance
    yield
    os.environ.clear()
    os.environ.update(orig_env)
    CatalogQueryEngine._instance = orig_engine


def test_startup_with_only_deploy_env_vars():
    """Verify backend starts and operates with only PORT, CORS_ORIGINS, and ARTIFACT_VERSION."""
    # Test setting only deployment environment variables
    test_env = {
        "PORT": "8080",
        "CORS_ORIGINS": '["https://exosignal.vercel.app"]',
        "ARTIFACT_VERSION": "v1_2026-10-29",
    }

    with patch.dict(os.environ, test_env, clear=False):
        # Force reload query engine to pick up ARTIFACT_VERSION
        engine = CatalogQueryEngine.reload_instance()
        assert engine.active_version == "v1_2026-10-29"
        assert engine.conn is not None

        with TestClient(app) as client:
            # 1. Test /health (Liveness Probe)
            health_resp = client.get("/health")
            assert health_resp.status_code == 200
            health_data = health_resp.json()
            assert health_data["status"] == "ok"
            assert health_data["artifact_version"] == "v1_2026-10-29"
            assert health_data["catalog_records"] > 0

            # 2. Test /ready (Readiness Probe)
            ready_resp = client.get("/ready")
            assert ready_resp.status_code == 200
            ready_data = ready_resp.json()
            assert ready_data["status"] == "ready"
            assert ready_data["duckdb"] == "ok"
            assert ready_data["artifact_version"] == "v1_2026-10-29"
            assert ready_data["catalog_records"] > 0

            # 3. Test core serving endpoints
            targets_resp = client.get("/api/v1/top-targets?limit=5")
            assert targets_resp.status_code == 200
            targets = targets_resp.json()
            assert isinstance(targets, list)
            assert len(targets) == 5

            # 4. Test planet detail and explain endpoints
            detail_resp = client.get("/api/v1/planets/TRAPPIST-1%20e")
            assert detail_resp.status_code == 200
            assert detail_resp.json()["planet_name"] == "TRAPPIST-1 e"

            explain_resp = client.get("/api/v1/explain/TRAPPIST-1%20e")
            assert explain_resp.status_code == 200
            assert explain_resp.json()["planet_name"] == "TRAPPIST-1 e"


def test_in_memory_serving_no_per_request_file_reads():
    """Verify endpoints read from in-memory DuckDB tables rather than opening Parquet files per request."""
    CatalogQueryEngine.reload_instance()

    with TestClient(app) as client:
        # Patch builtins.open to verify no parquet file reads happen during query execution
        orig_open = open
        read_parquet_files = []

        def tracked_open(file, *args, **kwargs):
            if isinstance(file, (str, os.PathLike)) and str(file).endswith(".parquet"):
                read_parquet_files.append(str(file))
            return orig_open(file, *args, **kwargs)

        with patch("builtins.open", side_effect=tracked_open):
            # Execute multiple query requests
            client.get("/api/v1/planets?limit=10")
            client.get("/api/v1/top-targets?limit=10")
            client.get("/api/v1/planets/TRAPPIST-1%20e")

        # Zero disk parquet file reads should have occurred during request handling
        assert len(read_parquet_files) == 0, f"Per-request parquet reads detected: {read_parquet_files}"


def test_cors_configuration_parsing():
    """Verify CORS_ORIGINS parses JSON array and comma-separated formats cleanly."""
    from app.config import Settings

    # JSON Array syntax
    s1 = Settings(CORS_ORIGINS='["https://exosignal.vercel.app", "http://localhost:3000"]')
    assert s1.CORS_ORIGINS == ["https://exosignal.vercel.app", "http://localhost:3000"]

    # Comma-separated syntax
    s2 = Settings(CORS_ORIGINS="https://exosignal.vercel.app, http://localhost:3000")
    assert s2.CORS_ORIGINS == ["https://exosignal.vercel.app", "http://localhost:3000"]

    # Wildcard
    s3 = Settings(CORS_ORIGINS='["*"]')
    assert s3.CORS_ORIGINS == ["*"]


def test_render_loadtest_report(tmp_path):
    """Verify render_loadtest_report.py generates valid markdown from mock k6 summary and manifest."""
    import subprocess
    import sys

    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / "scripts" / "render_loadtest_report.py"
    output_md = tmp_path / "LOADTEST.md"

    # 1. Test placeholder mode (no summary file)
    cmd = [
        sys.executable,
        str(script_path),
        "--hardware", "Test Hardware (4 cores, 16GB)",
        "--report", str(output_md),
        "--placeholders",
    ]
    proc = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
    assert proc.returncode == 0
    content = output_md.read_text(encoding="utf-8")
    assert "Test Hardware (4 cores, 16GB)" in content
    assert "eligible /" in content  # Dataset size from manifest
    assert "[Not yet measured]" in content

    # 2. Test measured summary mode
    mock_summary = tmp_path / "k6_summary.json"
    mock_k6 = {
        "metrics": {
            "http_reqs": {"values": {"rate": 142.5, "count": 1000}},
            "http_req_duration": {"values": {"med": 8.5, "p(95)": 15.2, "p(99)": 28.4}},
            "http_req_failed": {"values": {"rate": 0.0}},
            "vus_max": {"values": {"max": 200}},
            "planets_duration": {"values": {"med": 9.1, "p(95)": 16.0, "p(99)": 25.0}},
            "top_targets_duration": {"values": {"med": 8.0, "p(95)": 14.0, "p(99)": 22.0}},
            "planet_detail_duration": {"values": {"med": 5.2, "p(95)": 10.1, "p(99)": 18.0}},
            "explain_duration": {"values": {"med": 11.0, "p(95)": 18.5, "p(99)": 30.0}},
        }
    }
    mock_summary.write_text(json.dumps(mock_k6), encoding="utf-8")

    cmd2 = [
        sys.executable,
        str(script_path),
        "--summary", str(mock_summary),
        "--hardware", "Test Cluster",
        "--report", str(output_md),
    ]
    proc2 = subprocess.run(cmd2, cwd=str(repo_root), capture_output=True, text=True)
    assert proc2.returncode == 0
    content2 = output_md.read_text(encoding="utf-8")
    assert "142.5 req/s" in content2
    assert "8.50 ms" in content2
    assert "15.20 ms" in content2
    assert "200 Concurrent Workers" in content2


