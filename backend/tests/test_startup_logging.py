"""The last startup log line states what /ready answers.

It once always said "all subsystems online", even when the catalog had failed to load or the explanation model
did not match the catalog. It now comes from the same check as /ready: success, degraded (an optional part
failed; still ready) or NOT READY (/ready answers 503).
"""

import logging
from typing import Any, List, Tuple

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml import explainability
from app.ml.explainability import SHAPExplainer
from app.ml.ltr_model import ExoSignalLTRModel
from app.ml.model_consistency import check_model_matches_catalog
from app.services.query_engine import CatalogQueryEngine

SUCCESS = "ExoSignal startup complete — all subsystems online"


def _start(caplog: pytest.LogCaptureFixture) -> Tuple[List[logging.LogRecord], Any]:
    """Run the application's startup and one /ready request; return the startup's final line and the response."""
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.main"):
        with TestClient(app) as client:
            startup = [r for r in caplog.records if r.name == "app.main" and "ExoSignal st" in r.getMessage()]
            ready = client.get("/ready")
    final = [r for r in startup if "starting" not in r.getMessage()]
    assert len(final) == 1, [r.getMessage() for r in startup]
    return final, ready


def test_all_subsystems_up_logs_success_and_is_ready(caplog: pytest.LogCaptureFixture) -> None:
    (final,), ready = _start(caplog)
    assert final.getMessage() == SUCCESS and final.levelno == logging.INFO
    assert ready.status_code == 200


def test_a_catalog_that_fails_to_load_is_not_reported_as_online(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(cls: Any, *a: Any, **k: Any) -> Any:
        raise RuntimeError("parquet unreadable")

    monkeypatch.setattr(CatalogQueryEngine, "get_instance", classmethod(broken))
    (final,), ready = _start(caplog)
    assert final.levelno == logging.ERROR
    assert final.getMessage() == "ExoSignal started but is NOT READY: query engine unavailable (/ready answers 503)"
    assert SUCCESS not in caplog.text
    assert ready.status_code == 503 and ready.json()["error"] == "query engine unavailable"


class _EmptyCatalog:
    active_version = "v_empty"
    conn = object()

    def count_records(self) -> int:
        return 0


def test_an_empty_catalog_is_not_ready(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CatalogQueryEngine, "get_instance", classmethod(lambda cls, *a, **k: _EmptyCatalog()))
    (final,), ready = _start(caplog)
    assert "NOT READY: Catalog contains zero records" in final.getMessage()
    assert ready.status_code == 503 and ready.json()["error"] == "Catalog contains zero records"


def test_a_model_that_does_not_match_the_catalog_is_not_ready(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = CatalogQueryEngine.get_instance()
    version_dir = engine.artifacts_dir / str(engine.active_version)
    other = version_dir / "ltr_model_b.joblib"  # the same build's feature-ablation model
    catalog = engine.get_cursor().execute("SELECT * FROM planets").df()
    report = check_model_matches_catalog(
        ExoSignalLTRModel.load(str(other)), other, engine.active_version, engine.artifacts_dir, catalog
    )
    monkeypatch.setattr(explainability, "check_model_matches_catalog", lambda *a, **k: report)
    monkeypatch.setattr(SHAPExplainer, "_instance", None)
    monkeypatch.setattr(SHAPExplainer, "_unavailable", None)
    (final,), ready = _start(caplog)
    assert final.levelno == logging.ERROR
    assert "NOT READY: explanation model does not match the served catalog" in final.getMessage()
    assert SUCCESS not in caplog.text
    assert ready.status_code == 503 and ready.json()["problems"] == list(report.problems)


def test_an_optional_failure_is_reported_as_degraded_and_the_service_is_ready(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_explainer(cls: Any, *a: Any, **k: Any) -> Any:
        raise OSError("model file unreadable")  # not a mismatch: the catalog is served, explanations are not

    monkeypatch.setattr(SHAPExplainer, "get_instance", classmethod(no_explainer))
    (final,), ready = _start(caplog)
    assert final.levelno == logging.WARNING
    assert final.getMessage() == "ExoSignal startup complete and ready, degraded: explanations unavailable"
    assert ready.status_code == 200


def test_a_failed_warm_up_is_reported_as_degraded(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    explainer = SHAPExplainer.get_instance()

    def broken(catalog: Any) -> int:
        raise MemoryError("no room for the cache")

    monkeypatch.setattr(explainer, "warm_feature_cache", broken)
    (final,), ready = _start(caplog)
    assert final.getMessage() == "ExoSignal startup complete and ready, degraded: explanation features not precomputed"
    assert ready.status_code == 200


@pytest.mark.parametrize("scenario", ["ok", "no catalog", "empty catalog", "degraded"])
def test_the_startup_log_and_ready_never_disagree(
    scenario: str, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    if scenario == "no catalog":
        monkeypatch.setattr(
            CatalogQueryEngine, "get_instance", classmethod(lambda cls, *a, **k: (_ for _ in ()).throw(OSError()))
        )
    elif scenario == "empty catalog":
        monkeypatch.setattr(CatalogQueryEngine, "get_instance", classmethod(lambda cls, *a, **k: _EmptyCatalog()))
    elif scenario == "degraded":
        monkeypatch.setattr(
            SHAPExplainer, "get_instance", classmethod(lambda cls, *a, **k: (_ for _ in ()).throw(OSError()))
        )
    (final,), ready = _start(caplog)
    says_ready = "NOT READY" not in final.getMessage()
    assert says_ready == (ready.status_code == 200), (final.getMessage(), ready.status_code)
