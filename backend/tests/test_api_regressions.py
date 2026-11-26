"""Regression tests for API defects found in the 2026-11-24 repository review. Most of them failed before the fix; the
others protect behaviour that must not change."""

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import observability
from app.api import v1
from app.main import app
from app.ml.model_registry import ModelRegistry
from app.observability import ETagCacheMiddleware
from app.services import query_engine
from app.services.query_engine import CatalogQueryEngine


@pytest.fixture
def client():
    before = getattr(app.state, "rate_limit_per_minute", None)
    app.state.rate_limit_per_minute = 0
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.state.rate_limit_per_minute = before


# --- recommendations -------------------------------------------------------------------------------------------


def test_size_class_filter_does_not_bypass_other_filters(client):
    """An unparenthesised OR returned already-observed and ineligible planets (and then a 500)."""
    resp = client.get("/api/v1/recommendations?size_class=gas_giant&limit=100")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 100
    assert not any(r["already_observed_jwst"] for r in rows)
    assert {r["kempton_size_class"] for r in rows} == {"Sub-Jovian / Gas Giant"}
    engine = CatalogQueryEngine.get_instance()
    total = engine.query_planets(
        limit=5000, sort_by="priority", eligible_only=True, exclude_observed=True, size_class="gas_giant"
    )
    expected = (
        engine.get_cursor()
        .execute(
            "SELECT count(*) FROM planets WHERE eligible_for_transmission AND NOT coalesce(already_observed_jwst, false)"
            " AND kempton_size_class = 'Sub-Jovian / Gas Giant'"
        )
        .fetchone()[0]
    )
    assert len(total) == expected > 0


def test_recommendations_including_observed_targets(client):
    """Observed targets have no unobserved_rank (NaN); int(NaN) was a 500."""
    resp = client.get("/api/v1/recommendations?exclude_observed=false&limit=100")
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["already_observed_jwst"] for r in rows)
    assert all(r["rank"] >= 1 for r in rows)


# --- catalogue queries -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("q", ["%", "_", "%25", "a%b"])
def test_search_text_is_literal(client, q):
    rows = client.get("/api/v1/planets", params={"q": q, "limit": 500}).json()
    assert all(q.lower() in r["planet_name"].lower() for r in rows)
    assert len(rows) < 500


def test_hyphen_search_matches_only_hyphenated_names(client):
    rows = client.get("/api/v1/planets", params={"q": "-", "limit": 500}).json()
    assert rows and all("-" in r["planet_name"] for r in rows)


@pytest.mark.parametrize("q", ["TOI-700 d", "toi 700 d", "toi700d"])
def test_search_still_ignores_hyphens_and_spaces(client, q):
    assert [r["planet_name"] for r in client.get("/api/v1/planets", params={"q": q}).json()] == ["TOI-700 d"]


def test_oversized_inputs_are_rejected_not_500(client):
    assert client.get("/api/v1/planets?offset=99999999999999999999").status_code == 422
    assert client.get("/api/v1/recommendations?offset=99999999999999999999").status_code == 422
    assert client.get("/api/v1/planets", params={"q": "x" * 101}).status_code == 422


def test_ineligible_planet_has_no_priority_score(client):
    """The heuristic score must never stand in for a missing priority score."""
    engine = CatalogQueryEngine.get_instance()
    name = (
        engine.get_cursor()
        .execute("SELECT planet_name FROM planets WHERE NOT eligible_for_transmission ORDER BY planet_name LIMIT 1")
        .fetchone()[0]
    )
    body = client.get(f"/api/v1/planets/{name}").json()
    assert body["priority_score"] is None and body["ml_priority_score"] is None


def test_detail_has_semi_major_axis_and_stellar_temperature(client):
    body = client.get("/api/v1/planets/TRAPPIST-1 e").json()
    assert body["semi_major_axis"] > 0
    assert body["stellar_effective_temperature"] > 0


# --- benchmark report ------------------------------------------------------------------------------------------


def test_benchmark_never_substitutes_another_split(client):
    assert client.get("/api/v1/evaluation/benchmark?split=test").json()["evaluation_split"] == "test"
    assert client.get("/api/v1/evaluation/benchmark?split=val").status_code == 404


def test_latency_benchmark_promises_nothing(client):
    body = client.get("/api/v1/system/latency-benchmark?iterations=10").json()
    assert not any("guarantee" in k for k in body)


def test_unknown_algorithm_is_not_invented(monkeypatch):
    engine = CatalogQueryEngine.get_instance()
    monkeypatch.setattr(engine, "manifest", {})
    assert engine.get_ltr_info()["algorithm"].startswith("unknown")


# --- errors, headers, caching ----------------------------------------------------------------------------------


def test_internal_error_text_is_not_returned(client, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("secret-internal-path /srv/x")

    monkeypatch.setattr(CatalogQueryEngine, "get_instance", boom)
    for path in ("/health", "/ready", "/metrics", "/api/v1/models/ltr/info", "/api/v1/evaluation/benchmark"):
        assert "secret-internal-path" not in client.get(path).text, path


@pytest.mark.parametrize("bad", ["a" * 65, "a b", "a\tb", "<script>", "x:y"])
def test_malformed_request_id_is_replaced(client, bad):
    resp = client.get("/health", headers={"X-Request-ID": bad})
    assert resp.headers["X-Request-ID"] != bad
    assert len(resp.headers["X-Request-ID"]) <= 64


@pytest.mark.parametrize("path", ["/api/v1/models/registry/active", "/api/v1/system/latency-benchmark?iterations=10"])
def test_changing_responses_are_not_cached(client, path):
    resp = client.get(path)
    assert resp.headers["Cache-Control"] == "no-store"
    assert "ETag" not in resp.headers


def test_etag_follows_the_served_version(monkeypatch):
    """The version was cached forever, so an artifact reload kept the old ETag."""
    middleware = ETagCacheMiddleware(app)
    engine = CatalogQueryEngine.get_instance()
    before = middleware._get_active_version()
    monkeypatch.setattr(engine, "active_version", "v_other")
    assert middleware._get_active_version() == "v_other" != before


def test_etag_changes_with_the_response_revision(client, monkeypatch):
    """Otherwise a 304 would keep answers of older code alive for the same artifact."""
    before = client.get("/api/v1/planets?limit=1").headers["ETag"]
    monkeypatch.setattr(observability, "RESPONSE_REVISION", "other")
    assert client.get("/api/v1/planets?limit=1").headers["ETag"] != before


def test_rate_limited_response_is_traced_and_readable_by_browsers(client):
    app.state.rate_limit_per_minute = 1
    try:
        headers = {"Origin": "https://example.org"}
        client.get("/api/v1/planets?limit=1", headers=headers)
        resp = client.get("/api/v1/planets?limit=1", headers=headers)
        assert resp.status_code == 429
        assert resp.headers["X-Request-ID"] == resp.json()["error"]["request_id"]
        assert "X-Process-Time" in resp.headers
        assert "access-control-allow-origin" in resp.headers
    finally:
        app.state.rate_limit_per_minute = 0


def test_health_is_reachable_under_the_api_prefix(client):
    """The frontend only proxies /api, so its status light called a path that did not exist."""
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/api/v1/metrics").status_code == 200


# --- model registry on a clean clone ----------------------------------------------------------------------------


@pytest.fixture
def clean_clone(tmp_path):
    """Only the committed per-version entry exists, written on Windows."""
    version = tmp_path / "v1"
    version.mkdir()
    (version / "ltr_model.joblib").write_bytes(b"model")
    (version / "planets.parquet").write_bytes(b"parquet")
    sha = ModelRegistry._compute_checksum
    artifacts = {
        "model": {"path": "artifacts\\v1\\ltr_model.joblib", "sha256": sha(version / "ltr_model.joblib")},
        "parquet": {"path": "artifacts\\v1\\planets.parquet", "sha256": sha(version / "planets.parquet")},
    }
    entry = {"version": "v1", "artifacts": artifacts, "registered_at": "2026-01-01"}
    (version / "registry_entry.json").write_text(json.dumps(entry), encoding="utf-8")
    return tmp_path


def test_integrity_check_works_without_the_local_index(clean_clone):
    registry = ModelRegistry(artifacts_dir=str(clean_clone))
    assert [v["version"] for v in registry.list_versions()] == ["v1"]
    assert registry.validate_integrity("v1")["valid"] is True
    (clean_clone / "v1" / "planets.parquet").write_bytes(b"changed")
    assert registry.validate_integrity("v1")["valid"] is False


def test_missing_checksum_is_not_integrity(clean_clone):
    path = clean_clone / "v1" / "registry_entry.json"
    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["artifacts"]["model"]["sha256"] = None
    path.write_text(json.dumps(entry), encoding="utf-8")
    assert ModelRegistry(artifacts_dir=str(clean_clone)).validate_integrity("v1")["valid"] is False


@pytest.mark.parametrize("version", ["..", "../v1", "..\\v1", "", "/etc"])
def test_version_names_cannot_leave_the_artifacts_directory(clean_clone, version):
    nested = ModelRegistry(artifacts_dir=str(clean_clone / "v1"))
    assert nested.get_version(version) is None


def test_new_registry_entries_do_not_record_the_host_name(tmp_path):
    entry = ModelRegistry(artifacts_dir=str(tmp_path)).register_version("v9", "m", "p", {}, {})
    assert "hostname" not in entry["environment"]


def test_registry_reports_the_inputs_of_the_served_model(client):
    """The committed entry records 10 (the length of a top-10 list)."""
    from app.ml.explainability import SHAPExplainer

    body = client.get("/api/v1/models/registry/active").json()
    assert body["served_model_features"] == len(SHAPExplainer.get_instance().feature_names) == 21


def test_registry_works_without_the_served_model(client, monkeypatch):
    from app.ml.explainability import SHAPExplainer

    def unavailable(*_args, **_kwargs):
        raise FileNotFoundError("no model")

    monkeypatch.setattr(SHAPExplainer, "get_instance", unavailable)
    response = client.get("/api/v1/models/registry/active")
    assert response.status_code == 200 and response.json()["served_model_features"] is None


def test_public_registry_endpoint_hides_the_build_environment(client):
    assert "environment" not in client.get("/api/v1/models/registry/active").json()


def test_comparing_unknown_versions_is_404(client):
    assert client.get("/api/v1/models/registry/compare?version_a=nope1&version_b=nope2").status_code == 404


# --- planets the model does not rank ------------------------------------------------------------------------------

NON_TRANSITING = "Proxima Cen b"  # stored model output in artifact v1_2026-10-29: 99.99999996


def test_stored_scores_of_ineligible_planets_are_never_served(client):
    body = client.get(f"/api/v1/planets/{NON_TRANSITING}").json()
    assert body["eligible_for_transmission"] is False
    for field in ("priority_score", "ml_priority_score", "priority_rank", "ml_rank", "percentile_rank"):
        assert body[field] is None, field
    rows = client.get("/api/v1/planets?limit=500&offset=4600").json()
    unranked = [r for r in rows if r["eligible_for_transmission"] is False]
    assert unranked and all(r["priority_score"] is None and r["ml_priority_score"] is None for r in unranked)


@pytest.mark.parametrize("sort_by", ["priority", "ml"])
def test_score_range_and_order_ignore_ineligible_planets(client, sort_by):
    rows = client.get(f"/api/v1/planets?sort_by={sort_by}&limit=500").json()
    assert all(r["eligible_for_transmission"] for r in rows)
    rows = client.get(f"/api/v1/planets?sort_by={sort_by}&min_priority=99&limit=500").json()
    assert rows and all(r["eligible_for_transmission"] for r in rows)


def test_ineligible_planets_stay_visible_in_the_catalogue(client):
    assert client.get("/api/v1/planets", params={"q": NON_TRANSITING}).json()[0]["planet_name"] == NON_TRANSITING


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/planets/{NON_TRANSITING}/explain",
        f"/api/v1/planets/compare-explain?planet_a={NON_TRANSITING}&planet_b=TRAPPIST-1 e",
        f"/api/v1/planets/compare-explain?planet_a=TRAPPIST-1 e&planet_b={NON_TRANSITING}",
    ],
)
def test_a_score_of_an_unranked_planet_is_not_explained(client, path):
    resp = client.get(path)
    assert resp.status_code == 422
    assert "not eligible" in resp.json()["detail"]


# --- missing values stay missing (R9) --------------------------------------------------------------------------------


@pytest.mark.parametrize("missing", [None, float("nan")])
def test_a_missing_heuristic_score_is_none_and_zero_stays_zero(missing):
    row = {"planet_name": "SYN-1 b", "target_priority_score": missing, "heuristic_habitability_score": missing}
    assert v1._row_to_planet_response(row).target_priority_score is None
    assert v1._row_to_planet_response({**row, "target_priority_score": 0.0}).target_priority_score == 0.0


def test_out_of_range_heuristic_scores_are_still_rejected():
    for bad in (-0.1, 100.1):
        with pytest.raises(ValueError):
            v1._row_to_planet_response(
                {"planet_name": "SYN-1 b", "target_priority_score": bad, "heuristic_habitability_score": 50.0}
            )


def test_pca_has_no_invented_zeros():
    frame = pd.DataFrame({"anomaly_score": [0.0, float("nan"), 0.1234]})
    assert query_engine._rounded_or_none(frame, "anomaly_score", 3) == [0.0, None, 0.123]
    assert query_engine._rounded_or_none(frame, "target_priority_score", 1) == [None, None, None]
