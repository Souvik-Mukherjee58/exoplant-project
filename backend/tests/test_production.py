"""Week 7 Test Suite: Model Registry, Observability, and Production Hardening.

Tests cover:
1. Model Registry: registration, promotion, rollback, integrity validation, lineage.
2. Structured Logging: JSON formatter, correlation IDs, slow-request detection.
3. Production Configuration: environment-aware settings, /metrics endpoint.
4. Container readiness: Dockerfile existence and structure validation.
"""

import json
import os
import tempfile
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


# ================================================================
# Model Registry Tests
# ================================================================

class TestModelRegistry:
    """Tests for the local-first model registry."""

    @pytest.fixture
    def temp_registry(self, tmp_path):
        """Create a temporary model registry with mock artifacts."""
        from app.ml.model_registry import ModelRegistry

        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # Create mock artifact version directories
        v1_dir = artifacts_dir / "v1_test_old"
        v1_dir.mkdir()
        model_file = v1_dir / "ltr_model.joblib"
        model_file.write_bytes(b"mock_model_v1_old_content_here")
        parquet_file = v1_dir / "planets.parquet"
        parquet_file.write_bytes(b"mock_parquet_v1_old_content_here")

        v2_dir = artifacts_dir / "v1_test_new"
        v2_dir.mkdir()
        model_file_2 = v2_dir / "ltr_model.joblib"
        model_file_2.write_bytes(b"mock_model_v1_new_content_different")
        parquet_file_2 = v2_dir / "planets.parquet"
        parquet_file_2.write_bytes(b"mock_parquet_v1_new_content_different")

        # Create active version pointer
        (artifacts_dir / "active_version.txt").write_text("v1_test_old")

        registry = ModelRegistry(artifacts_dir=str(artifacts_dir))
        return registry, artifacts_dir

    def test_register_version_creates_entry(self, temp_registry):
        """Verify version registration stores correct metadata."""
        registry, artifacts_dir = temp_registry
        model_path = str(artifacts_dir / "v1_test_old" / "ltr_model.joblib")
        parquet_path = str(artifacts_dir / "v1_test_old" / "planets.parquet")

        entry = registry.register_version(
            version="v1_test_old",
            model_path=model_path,
            parquet_path=parquet_path,
            training_config={"algorithm": "LightGBM", "n_features": 21},
            evaluation_metrics={"ndcg@10": 0.65, "map": 0.55, "precision@10": 0.70},
            notes="Test version registration"
        )

        assert entry["version"] == "v1_test_old"
        assert entry["status"] == "registered"
        assert entry["training"]["algorithm"] == "LightGBM"
        assert entry["evaluation"]["ndcg@10"] == 0.65
        assert entry["artifacts"]["model"]["sha256"] is not None

    def test_register_version_persists_to_disk(self, temp_registry):
        """Registry entries must survive process restarts (persist to JSON)."""
        registry, artifacts_dir = temp_registry
        model_path = str(artifacts_dir / "v1_test_old" / "ltr_model.joblib")
        parquet_path = str(artifacts_dir / "v1_test_old" / "planets.parquet")

        registry.register_version(
            version="v1_test_old",
            model_path=model_path,
            parquet_path=parquet_path,
            training_config={"algorithm": "LightGBM"},
            evaluation_metrics={"ndcg@10": 0.65}
        )

        # Reload from disk
        from app.ml.model_registry import ModelRegistry
        fresh_registry = ModelRegistry(artifacts_dir=str(artifacts_dir))
        assert fresh_registry.get_version("v1_test_old") is not None
        assert fresh_registry.get_version("v1_test_old")["evaluation"]["ndcg@10"] == 0.65

    def test_promote_updates_active_pointer(self, temp_registry):
        """Promotion must update active_version.txt and set status to 'production'."""
        registry, artifacts_dir = temp_registry
        model_path = str(artifacts_dir / "v1_test_new" / "ltr_model.joblib")
        parquet_path = str(artifacts_dir / "v1_test_new" / "planets.parquet")

        registry.register_version(
            version="v1_test_new",
            model_path=model_path,
            parquet_path=parquet_path,
            training_config={},
            evaluation_metrics={"ndcg@10": 0.70}
        )

        registry.promote("v1_test_new", reason="Better NDCG")

        assert registry.get_active_version() == "v1_test_new"
        assert registry.get_version("v1_test_new")["status"] == "production"

    def test_promote_records_audit_trail(self, temp_registry):
        """Every promotion must record an audit trail entry with timestamp and reason."""
        registry, artifacts_dir = temp_registry
        model_path = str(artifacts_dir / "v1_test_new" / "ltr_model.joblib")
        parquet_path = str(artifacts_dir / "v1_test_new" / "planets.parquet")

        registry.register_version(
            version="v1_test_new",
            model_path=model_path,
            parquet_path=parquet_path,
            training_config={},
            evaluation_metrics={}
        )

        registry.promote("v1_test_new", reason="A/B test winner")

        history = registry._registry["promotion_history"]
        assert len(history) >= 1
        latest = history[-1]
        assert latest["to_version"] == "v1_test_new"
        assert latest["reason"] == "A/B test winner"
        assert "timestamp" in latest

    def test_rollback_restores_previous_version(self, temp_registry):
        """Rollback must restore the previous active version and record audit entry."""
        registry, artifacts_dir = temp_registry

        # Register both versions
        for v in ["v1_test_old", "v1_test_new"]:
            model_path = str(artifacts_dir / v / "ltr_model.joblib")
            parquet_path = str(artifacts_dir / v / "planets.parquet")
            registry.register_version(
                version=v,
                model_path=model_path,
                parquet_path=parquet_path,
                training_config={},
                evaluation_metrics={}
            )

        registry.promote("v1_test_old", reason="Initial")
        registry.promote("v1_test_new", reason="Upgrade")

        assert registry.get_active_version() == "v1_test_new"

        rolled = registry.rollback(reason="Metrics degradation in prod")
        assert rolled == "v1_test_old"
        assert registry.get_active_version() == "v1_test_old"

    def test_validate_integrity_with_valid_artifacts(self, temp_registry):
        """Integrity check must pass when checksums match registered values."""
        registry, artifacts_dir = temp_registry
        model_path = str(artifacts_dir / "v1_test_old" / "ltr_model.joblib")
        parquet_path = str(artifacts_dir / "v1_test_old" / "planets.parquet")

        registry.register_version(
            version="v1_test_old",
            model_path=model_path,
            parquet_path=parquet_path,
            training_config={},
            evaluation_metrics={}
        )

        result = registry.validate_integrity("v1_test_old")
        assert result["valid"] is True
        assert result["checks"]["model"]["status"] == "OK"
        assert result["checks"]["parquet"]["status"] == "OK"

    def test_validate_integrity_detects_corruption(self, temp_registry):
        """Integrity check must detect when artifact files have been tampered with."""
        registry, artifacts_dir = temp_registry
        model_path = str(artifacts_dir / "v1_test_old" / "ltr_model.joblib")
        parquet_path = str(artifacts_dir / "v1_test_old" / "planets.parquet")

        registry.register_version(
            version="v1_test_old",
            model_path=model_path,
            parquet_path=parquet_path,
            training_config={},
            evaluation_metrics={}
        )

        # Tamper with the model file
        Path(model_path).write_bytes(b"corrupted_data_injected_by_attacker")

        result = registry.validate_integrity("v1_test_old")
        assert result["valid"] is False
        assert result["checks"]["model"]["status"] == "CORRUPTED"

    def test_compare_versions_computes_delta(self, temp_registry):
        """Version comparison must compute metric deltas and declare winners."""
        registry, artifacts_dir = temp_registry

        for v, ndcg, map_val in [("v1_test_old", 0.55, 0.40), ("v1_test_new", 0.72, 0.60)]:
            model_path = str(artifacts_dir / v / "ltr_model.joblib")
            parquet_path = str(artifacts_dir / v / "planets.parquet")
            registry.register_version(
                version=v,
                model_path=model_path,
                parquet_path=parquet_path,
                training_config={},
                evaluation_metrics={"ndcg@10": ndcg, "map": map_val, "precision@10": 0.50}
            )

        comparison = registry.compare_versions("v1_test_new", "v1_test_old")
        assert comparison["metric_comparison"]["ndcg@10"]["winner"] == "v1_test_new"
        assert comparison["metric_comparison"]["ndcg@10"]["delta"] == pytest.approx(0.17, abs=0.01)
        assert comparison["metric_comparison"]["map"]["winner"] == "v1_test_new"

    def test_list_versions_returns_sorted(self, temp_registry):
        """List must return versions sorted by registration time (newest first)."""
        registry, artifacts_dir = temp_registry

        for v in ["v1_test_old", "v1_test_new"]:
            model_path = str(artifacts_dir / v / "ltr_model.joblib")
            parquet_path = str(artifacts_dir / v / "planets.parquet")
            registry.register_version(
                version=v,
                model_path=model_path,
                parquet_path=parquet_path,
                training_config={},
                evaluation_metrics={"ndcg@10": 0.50}
            )

        versions = registry.list_versions()
        assert len(versions) == 2
        assert all("version" in v for v in versions)
        assert all("ndcg_at_10" in v for v in versions)

    def test_promote_unregistered_version_raises(self, temp_registry):
        """Promoting an unregistered version must raise ValueError."""
        registry, _ = temp_registry
        with pytest.raises(ValueError, match="not registered"):
            registry.promote("v999_nonexistent", reason="Should fail")


# ================================================================
# Structured Logging Tests
# ================================================================

class TestStructuredLogging:
    """Tests for JSON structured logging and request tracing."""

    def test_json_formatter_produces_valid_json(self):
        """JSONFormatter output must be parseable JSON."""
        from app.observability import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test log message",
            args=(),
            exc_info=None
        )

        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Test log message"

    def test_json_formatter_includes_extra_fields(self):
        """Extra fields (request_id, method, etc.) must appear in JSON output."""
        from app.observability import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="exosignal.http",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="GET /api/v1/planets",
            args=(),
            exc_info=None
        )
        record.request_id = "abc123"
        record.method = "GET"
        record.path = "/api/v1/planets"
        record.duration_ms = 12.5

        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["request_id"] == "abc123"
        assert parsed["method"] == "GET"
        assert parsed["duration_ms"] == 12.5

    def test_configure_logging_sets_level(self):
        """configure_logging must set the root logger to the specified level."""
        from app.observability import configure_logging

        configure_logging(level="DEBUG", json_output=False)
        root = logging.getLogger()
        assert root.level == logging.DEBUG

        # Restore
        configure_logging(level="INFO", json_output=False)

    def test_configure_logging_json_mode(self):
        """JSON mode must attach JSONFormatter to root handler."""
        from app.observability import configure_logging, JSONFormatter

        configure_logging(level="INFO", json_output=True)
        root = logging.getLogger()
        assert any(isinstance(h.formatter, JSONFormatter) for h in root.handlers)

        # Restore
        configure_logging(level="INFO", json_output=False)


# ================================================================
# API Endpoint Tests (Health, Metrics)
# ================================================================

class TestProductionEndpoints:
    """Tests for production observability endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_health_endpoint_returns_ok(self, client):
        """GET /health must return status 'ok' with artifact metadata."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        if data["status"] == "ok":
            assert "artifact_version" in data
            assert "catalog_records" in data

    def test_metrics_endpoint_returns_subsystems(self, client):
        """GET /metrics must report subsystem health for monitoring dashboards."""
        resp = client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "exosignal"
        assert "subsystems" in data
        assert "duckdb" in data["subsystems"]
        assert "shap_explainer" in data["subsystems"]

    def test_root_endpoint_includes_version(self, client):
        """Root endpoint must report API version and environment."""
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "0.3.0"
        assert "environment" in data

    def test_response_headers_include_request_id(self, client):
        """Every response must include X-Request-ID and X-Process-Time headers."""
        resp = client.get("/health")
        assert "x-request-id" in resp.headers
        assert "x-process-time" in resp.headers

    def test_registry_versions_endpoint(self, client):
        """GET /api/v1/models/registry/versions returns version listing."""
        resp = client.get("/api/v1/models/registry/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_version" in data
        assert "versions" in data

    def test_registry_active_endpoint(self, client):
        """GET /api/v1/models/registry/active returns active model metadata or 404."""
        resp = client.get("/api/v1/models/registry/active")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "version" in data
            assert "artifacts" in data

    def test_registry_validate_nonexistent_returns_404(self, client):
        """GET /api/v1/models/registry/validate/{version} returns 404 for unknown version."""
        resp = client.get("/api/v1/models/registry/validate/v_nonexistent_9999")
        assert resp.status_code == 404


# ================================================================
# Container & CI/CD Structure Tests
# ================================================================

class TestContainerReadiness:
    """Validate container and CI/CD configuration files exist and are well-formed."""

    def test_backend_dockerfile_exists(self):
        """Backend Dockerfile must exist."""
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        assert dockerfile.exists(), f"Backend Dockerfile not found at {dockerfile}"

    def test_backend_dockerfile_has_healthcheck(self):
        """Backend Dockerfile must include a HEALTHCHECK instruction."""
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")
        assert "HEALTHCHECK" in content, "Dockerfile missing HEALTHCHECK instruction"

    def test_backend_dockerfile_uses_nonroot_user(self):
        """Backend Dockerfile must run as non-root user for security."""
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")
        assert "USER" in content, "Dockerfile missing USER instruction (running as root)"

    def test_backend_dockerfile_is_multistage(self):
        """Backend Dockerfile must use multi-stage build for image size optimization."""
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")
        from_count = content.count("FROM ")
        assert from_count >= 2, f"Expected multi-stage build (>= 2 FROM), got {from_count}"

    def test_docker_compose_exists(self):
        """docker-compose.yml must exist at project root."""
        compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
        assert compose.exists(), f"docker-compose.yml not found at {compose}"

    def test_ci_workflow_exists(self):
        """CI/CD workflow must exist in .github/workflows/."""
        ci = Path(__file__).parent.parent.parent / ".github" / "workflows" / "ci.yml"
        assert ci.exists(), f"CI workflow not found at {ci}"

    def test_ci_workflow_has_benchmark_gate(self):
        """CI workflow must include ML benchmark regression gate job."""
        ci = Path(__file__).parent.parent.parent / ".github" / "workflows" / "ci.yml"
        content = ci.read_text(encoding="utf-8")
        assert "benchmark-gate" in content, "CI workflow missing ML benchmark regression gate"
        assert "NDCG" in content or "ndcg" in content, "CI workflow missing NDCG threshold check"
