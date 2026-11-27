"""The explanation model must be the model that scored the served catalog (checked once, at startup).

The catalog (query engine) and the model (explainer) are loaded separately. If they come from different
artifacts, explanations would describe scores the API does not serve, so the explainer refuses to start:
explanation endpoints answer 503, /ready fails (a deployment health check), the catalog is still served.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml import explainability
from app.ml.explainability import SHAPExplainer
from app.ml.ltr_model import ExoSignalLTRModel
from app.ml.model_consistency import (
    ExplanationsUnavailable,
    ModelConsistencyReport,
    check_model_matches_catalog,
    recorded_model_sha256,
)
from app.services.query_engine import CatalogQueryEngine


@pytest.fixture(scope="module")
def served() -> Any:
    engine = CatalogQueryEngine.get_instance()
    catalog = engine.get_cursor().execute("SELECT * FROM planets").df()
    version_dir = Path(engine.artifacts_dir) / str(engine.active_version)
    return engine, catalog, version_dir


def _check(model_path: Path, served: Any, artifacts_dir: Any = None, catalog: Any = None) -> ModelConsistencyReport:
    engine, full_catalog, _ = served
    return check_model_matches_catalog(
        ExoSignalLTRModel.load(str(model_path)),
        model_path,
        engine.active_version,
        Path(artifacts_dir or engine.artifacts_dir),
        full_catalog if catalog is None else catalog,
    )


def test_the_served_model_is_verified_by_checksum_and_by_its_scores(served: Any) -> None:
    engine, catalog, version_dir = served
    report = _check(version_dir / "ltr_model.joblib", served)
    assert report.ok, report.problems
    assert report.model_version == report.served_version == engine.active_version
    assert report.model_sha256 == report.recorded_sha256 == recorded_model_sha256(version_dir)
    assert report.planets_compared == int(catalog["eligible_for_transmission"].sum())  # every eligible planet
    assert report.max_score_difference is not None and report.max_score_difference < 1e-9


def test_a_different_model_under_the_same_version_label_is_found(served: Any) -> None:
    """The check compares the actual model (bytes and scores), not only the version name."""
    _, _, version_dir = served
    report = _check(version_dir / "ltr_model_b.joblib", served)  # the feature-ablation model of the same build
    assert not report.ok
    assert report.model_version == report.served_version  # same label...
    assert any("SHA-256" in p for p in report.problems)  # ...different file
    assert any("score differently" in p for p in report.problems)  # ...different scores


def test_the_right_model_under_another_version_is_found(served: Any, tmp_path: Path) -> None:
    _, _, version_dir = served
    other = tmp_path / "v_other"
    other.mkdir()
    shutil.copy(version_dir / "ltr_model.joblib", other / "ltr_model.joblib")
    report = _check(other / "ltr_model.joblib", served)
    assert report.problems == (f"the model comes from artifact 'v_other', the catalog from '{report.served_version}'",)


def test_no_recorded_checksum_means_the_model_cannot_be_verified(served: Any, tmp_path: Path) -> None:
    engine, _, version_dir = served
    copy = tmp_path / str(engine.active_version)
    copy.mkdir()
    shutil.copy(version_dir / "ltr_model.joblib", copy / "ltr_model.joblib")  # no registry_entry.json
    report = _check(copy / "ltr_model.joblib", served, artifacts_dir=tmp_path)
    assert report.problems == (f"artifact '{engine.active_version}' records no model checksum (registry_entry.json)",)
    (copy / "registry_entry.json").write_text(json.dumps({"artifacts": {"model": {"sha256": "not a checksum"}}}))
    assert not _check(copy / "ltr_model.joblib", served, artifacts_dir=tmp_path).ok


def test_a_catalog_without_scores_means_the_model_cannot_be_verified(served: Any) -> None:
    _, catalog, version_dir = served
    no_scores = catalog.drop(columns=["in_sample_priority_score", "priority_score"])
    report = _check(version_dir / "ltr_model.joblib", served, catalog=no_scores)
    assert report.problems == ("the catalog has no model scores to compare the explanation model with",)


def test_an_older_catalog_is_compared_on_the_unlabelled_planets(served: Any) -> None:
    """Without in-sample scores, labelled planets are skipped: they are served out-of-fold scores."""
    _, catalog, version_dir = served
    report = _check(
        version_dir / "ltr_model.joblib", served, catalog=catalog.drop(columns=["in_sample_priority_score"])
    )
    assert report.ok, report.problems
    eligible = catalog[catalog["eligible_for_transmission"].eq(True)]
    assert report.planets_compared == int(eligible["already_observed_jwst"].ne(True).sum())


def test_no_served_version_means_the_model_cannot_be_verified(served: Any) -> None:
    engine, catalog, version_dir = served
    path = version_dir / "ltr_model.joblib"
    report = check_model_matches_catalog(ExoSignalLTRModel.load(str(path)), path, None, engine.artifacts_dir, catalog)
    assert "the query engine reports no served artifact version" in report.problems


# ----------------------------------------------------------------------------------------------------------------
# The explainer and the API when the model does not match
# ----------------------------------------------------------------------------------------------------------------


@pytest.fixture
def mismatch(served: Any, monkeypatch: pytest.MonkeyPatch) -> ModelConsistencyReport:
    """A fresh explainer start whose check fails (the real check, run on the feature-ablation model)."""
    _, _, version_dir = served
    report = _check(version_dir / "ltr_model_b.joblib", served)
    assert not report.ok
    monkeypatch.setattr(explainability, "check_model_matches_catalog", lambda *a, **k: report)
    monkeypatch.setattr(SHAPExplainer, "_instance", None)
    monkeypatch.setattr(SHAPExplainer, "_unavailable", None)
    return report


def test_the_explainer_verifies_itself_when_it_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SHAPExplainer, "_instance", None)
    monkeypatch.setattr(SHAPExplainer, "_unavailable", None)
    explainer = SHAPExplainer.get_instance()
    assert explainer.consistency is not None and explainer.consistency.ok


def test_a_mismatch_keeps_no_explainer_and_is_remembered(
    mismatch: ModelConsistencyReport, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = []
    original_init = SHAPExplainer.__init__

    def counting_init(self: SHAPExplainer, *a: Any, **k: Any) -> None:
        created.append(1)
        original_init(self, *a, **k)

    monkeypatch.setattr(SHAPExplainer, "__init__", counting_init)
    with pytest.raises(ExplanationsUnavailable) as first:
        SHAPExplainer.get_instance()
    assert SHAPExplainer._instance is None  # no partially initialised shared state
    with pytest.raises(ExplanationsUnavailable) as second:
        SHAPExplainer.get_instance()
    assert second.value is first.value and len(created) == 1  # the model is not loaded again
    assert first.value.report is mismatch


def test_explanations_answer_503_and_the_catalog_is_still_served(mismatch: ModelConsistencyReport) -> None:
    client = TestClient(app)
    for path, params in [
        ("/api/v1/planets/TOI-700 d/explain", None),
        ("/api/v1/explain/TOI-700 d", None),
        ("/api/v1/planets/compare-explain", {"planet_a": "TOI-700 d", "planet_b": "K2-18 b"}),
    ]:
        response = client.get(path, params=params)
        assert response.status_code == 503, path
        body = response.json()["error"]
        assert body["code"] == "SERVICE_UNAVAILABLE" and "does not match the served catalog" in body["message"]
        assert body["request_id"] == response.headers["X-Request-ID"]

    assert client.get("/api/v1/planets", params={"limit": 3}).status_code == 200
    recommendations = client.get("/api/v1/recommendations", params={"limit": 3})
    assert recommendations.status_code == 200 and all(r["reasons"] == [] for r in recommendations.json())


def test_readiness_fails_with_a_clear_diagnostic(mismatch: ModelConsistencyReport) -> None:
    client = TestClient(app)
    ready = client.get("/ready")
    assert ready.status_code == 503
    assert ready.json()["error"] == "explanation model does not match the served catalog"
    assert ready.json()["problems"] == list(mismatch.problems)
    metrics = client.get("/metrics").json()["subsystems"]["shap_explainer"]
    assert metrics["status"] == "model_mismatch" and metrics["model_check"]["verified"] is False
    assert client.get("/health").json()["status"] == "ok"  # the process is alive, just not ready


def test_startup_with_a_mismatch_logs_it_and_warms_nothing(
    mismatch: ModelConsistencyReport, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        with TestClient(app) as client:
            assert client.get("/api/v1/planets", params={"limit": 1}).status_code == 200
    assert "Explanations disabled" in caplog.text and "does not match the served catalog" in caplog.text
    assert SHAPExplainer._instance is None


def test_readiness_and_metrics_report_a_verified_model() -> None:
    client = TestClient(app)
    assert client.get("/ready").status_code == 200
    check = client.get("/metrics").json()["subsystems"]["shap_explainer"]["model_check"]
    assert check["verified"] is True and check["problems"] == []


def test_the_report_is_plain_data() -> None:
    report = ModelConsistencyReport("v1", "m.joblib", "v1", "a" * 64, "a" * 64, 3, 0.0)
    assert report.ok and json.loads(json.dumps(report.as_dict()))["verified"] is True
