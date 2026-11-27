"""Model promotion is by deployment (audit finding F-02).

The API runs several worker processes. A promotion over HTTP reaches one of them, so the processes could serve
different models; the HTTP endpoints were removed. The pipeline CLI changes active_version.txt, all or nothing,
and the processes serve the new version after a restart. /models/registry/active reports both versions.
"""

import json
import threading
from pathlib import Path
from typing import Tuple

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml.model_registry import ModelRegistry
from app.services.query_engine import CatalogQueryEngine

client = TestClient(app)


@pytest.fixture
def registry(tmp_path: Path) -> Tuple[ModelRegistry, Path]:
    artifacts = tmp_path / "artifacts"
    for version in ("v1_test_old", "v1_test_new"):
        (artifacts / version).mkdir(parents=True)
        (artifacts / version / "ltr_model.joblib").write_bytes(f"model {version}".encode())
        (artifacts / version / "planets.parquet").write_bytes(f"parquet {version}".encode())
    (artifacts / "active_version.txt").write_text("v1_test_old")
    reg = ModelRegistry(artifacts_dir=str(artifacts))
    for version in ("v1_test_old", "v1_test_new"):
        reg.register_version(
            version=version,
            model_path=str(artifacts / version / "ltr_model.joblib"),
            parquet_path=str(artifacts / version / "planets.parquet"),
            training_config={},
            evaluation_metrics={},
        )
    return reg, artifacts


def _pointer(artifacts: Path) -> str:
    return (artifacts / "active_version.txt").read_text().strip()


def _saved(artifacts: Path) -> dict:
    return json.loads((artifacts / "registry.json").read_text())


def test_promotion_switches_the_pointer_and_leaves_no_temporary_file(registry):
    reg, artifacts = registry
    reg.promote("v1_test_new", reason="better")
    assert _pointer(artifacts) == "v1_test_new"
    assert _saved(artifacts)["versions"]["v1_test_new"]["status"] == "production"
    assert not list(artifacts.glob("*.tmp"))


def test_a_failed_registry_save_changes_nothing(registry, monkeypatch):
    reg, artifacts = registry
    before = _saved(artifacts)

    def broken_save() -> None:
        raise OSError("disk full")

    monkeypatch.setattr(reg, "_save_registry", broken_save)
    with pytest.raises(OSError):
        reg.promote("v1_test_new", reason="will fail")
    assert _pointer(artifacts) == "v1_test_old"
    assert _saved(artifacts) == before
    assert reg.get_version("v1_test_new")["status"] != "production"
    assert len(reg._registry["promotion_history"]) == len(before["promotion_history"])
    assert not list(artifacts.glob("*.tmp"))


def test_a_failed_pointer_switch_restores_the_saved_registry(registry, monkeypatch):
    reg, artifacts = registry
    before = _saved(artifacts)
    real_replace = Path.replace

    def broken_replace(self: Path, target):  # only the pointer switch fails
        if self.name == "active_version.txt.tmp":
            raise OSError("rename failed")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", broken_replace)
    with pytest.raises(OSError):
        reg.promote("v1_test_new", reason="will fail")
    monkeypatch.undo()
    assert _pointer(artifacts) == "v1_test_old"
    assert _saved(artifacts)["versions"] == before["versions"]
    assert _saved(artifacts)["promotion_history"] == before["promotion_history"]
    assert not list(artifacts.glob("*.tmp"))


def test_an_unregistered_version_is_refused_before_anything_changes(registry):
    reg, artifacts = registry
    with pytest.raises(ValueError):
        reg.promote("v9_missing")
    assert _pointer(artifacts) == "v1_test_old"


def test_rollback_restores_the_previous_version(registry):
    reg, artifacts = registry
    reg.promote("v1_test_new", reason="upgrade")
    assert reg.rollback(reason="regression") == "v1_test_old"
    assert _pointer(artifacts) == "v1_test_old"


def test_concurrent_promotions_always_leave_a_valid_pointer(registry):
    reg, artifacts = registry
    errors = []

    def promote(version: str) -> None:
        try:
            ModelRegistry(artifacts_dir=str(artifacts)).promote(version, reason="race")
        except OSError as exc:  # a concurrent rename on Windows may refuse; the pointer must stay valid
            errors.append(exc)

    threads = [threading.Thread(target=promote, args=(v,)) for v in ("v1_test_new", "v1_test_old") * 5]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert _pointer(artifacts) in {"v1_test_old", "v1_test_new"}
    assert json.loads((artifacts / "registry.json").read_text())["versions"]  # still valid JSON


def test_the_api_has_no_endpoint_that_changes_the_live_model():
    mutating = [
        (route.path, sorted(route.methods - {"GET", "HEAD"}))
        for route in app.routes
        if getattr(route, "methods", None) and route.methods - {"GET", "HEAD", "OPTIONS"}
    ]
    assert mutating == []
    assert client.post("/api/v1/models/registry/promote/v1_2026-10-29").status_code in (404, 405)
    assert client.post("/api/v1/models/registry/rollback").status_code in (404, 405)


def test_active_endpoint_reports_the_served_version():
    body = client.get("/api/v1/models/registry/active").json()
    served = CatalogQueryEngine.get_instance().active_version
    assert body["served_version"] == served
    assert body["active_version"] == served
    assert body["serving_matches_pointer"] is True


def test_active_endpoint_does_not_present_an_unloaded_pointer_as_live(monkeypatch):
    real_get_version = ModelRegistry.get_version
    served = CatalogQueryEngine.get_instance().active_version
    monkeypatch.setattr(ModelRegistry, "get_active_version", lambda self: "v1_promoted_not_loaded")
    monkeypatch.setattr(
        ModelRegistry,
        "get_version",
        lambda self, v: {"status": "production"} if v != served else real_get_version(self, v),
    )
    body = client.get("/api/v1/models/registry/active").json()
    assert body["active_version"] == "v1_promoted_not_loaded"
    assert body["served_version"] == served
    assert body["serving_matches_pointer"] is False


def test_a_restart_loads_the_pointer_version(tmp_path):
    """The engine reads active_version.txt when it starts; reload_instance stands in for a restart."""
    real = Path(CatalogQueryEngine.get_instance().artifacts_dir)
    version = (real / "active_version.txt").read_text().strip()
    copy_dir = tmp_path / "artifacts"
    (copy_dir / version).mkdir(parents=True)
    (copy_dir / version / "planets.parquet").write_bytes((real / version / "planets.parquet").read_bytes())
    (copy_dir / "active_version.txt").write_text(version)
    try:
        engine = CatalogQueryEngine.reload_instance(artifacts_dir=str(copy_dir))
        assert engine.active_version == version
        assert engine.get_cursor().execute("SELECT COUNT(*) FROM planets").fetchone()[0] > 0
    finally:
        CatalogQueryEngine.reload_instance()
