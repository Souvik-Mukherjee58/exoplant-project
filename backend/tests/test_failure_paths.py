"""Failures are handled visibly (audit finding F-07): narrowed to the expected errors, logged, never silent."""

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import requests
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.ml import explainability
from app.services.data_ingestion import DataIngestion
from app.services.query_engine import CatalogQueryEngine

CSV = b"pl_name,hostname,pl_rade\nPlanet b,Star,1.5\nPlanet c,Star,2.0\n"


class _Response:
    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content, self.status_code, self.text = content, status, content.decode()

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture
def ingestion(tmp_path: Path) -> DataIngestion:
    return DataIngestion(raw_dir=str(tmp_path / "raw"), processed_dir=str(tmp_path / "processed"))


def test_download_saves_the_exact_bytes_and_a_manifest(ingestion: DataIngestion, monkeypatch: Any) -> None:
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Response(CSV))
    df = ingestion.download_from_api(timeout=1)
    assert df is not None and len(df) == 2
    assert (ingestion.raw_dir / "nasa_exoplanet_archive.csv").read_bytes() == CSV
    manifest = json.loads((ingestion.raw_dir / "manifest.json").read_text())
    import hashlib

    assert manifest["sha256"] == hashlib.sha256(CSV).hexdigest()
    assert manifest["row_count"] == 2


@pytest.mark.parametrize(
    "failure",
    [requests.ConnectionError("offline"), requests.Timeout("slow"), requests.HTTPError("HTTP 500")],
)
def test_a_failed_download_is_logged_and_writes_nothing(
    ingestion: DataIngestion, monkeypatch: Any, caplog: Any, failure: Exception
) -> None:
    def fail(*a: Any, **k: Any) -> Any:
        raise failure

    monkeypatch.setattr(requests, "get", fail)
    with caplog.at_level(logging.WARNING, logger="app.services.data_ingestion"):
        assert ingestion.download_from_api(timeout=1) is None
    assert "Failed to download" in caplog.text
    assert not (ingestion.raw_dir / "nasa_exoplanet_archive.csv").exists()


def test_an_http_error_status_is_a_failed_download(ingestion: DataIngestion, monkeypatch: Any) -> None:
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Response(b"error", status=503))
    assert ingestion.download_from_api(timeout=1) is None


def test_an_empty_download_is_not_saved(ingestion: DataIngestion, monkeypatch: Any) -> None:
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Response(b"pl_name,hostname\n"))
    assert ingestion.download_from_api(timeout=1) is None
    assert not (ingestion.raw_dir / "nasa_exoplanet_archive.csv").exists()


def test_a_local_snapshot_is_used_without_the_network(ingestion: DataIngestion, monkeypatch: Any) -> None:
    ingestion.create_directories()
    (ingestion.raw_dir / "nasa_exoplanet_archive.csv").write_bytes(CSV)

    def no_network(*a: Any, **k: Any) -> Any:
        raise AssertionError("the network must not be used when a local snapshot exists")

    monkeypatch.setattr(requests, "get", no_network)
    assert len(ingestion.load_or_download_exoplanet_archive(use_api=False)) == 2


def test_a_failed_download_falls_back_to_another_local_csv(ingestion: DataIngestion, monkeypatch: Any) -> None:
    ingestion.create_directories()
    (ingestion.raw_dir / "other.csv").write_bytes(CSV)
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Response(b"", status=500))
    assert len(ingestion.load_or_download_exoplanet_archive(use_api=True, api_timeout=1)) == 2


def test_no_data_at_all_gives_an_empty_frame(ingestion: DataIngestion, monkeypatch: Any) -> None:
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Response(b"", status=500))
    assert ingestion.load_or_download_exoplanet_archive(use_api=True, api_timeout=1).empty


@pytest.mark.parametrize("content", [None, b"", b"a,b\n"])
def test_an_unreadable_csv_raises_with_its_cause(tmp_path: Path, content: Any) -> None:
    path = tmp_path / "data.csv"
    if content is not None:
        path.write_bytes(content)
    with pytest.raises(ValueError) as caught:
        DataIngestion().load_from_csv(str(path))
    assert str(path) in str(caught.value)


def test_processed_data_round_trip(ingestion: DataIngestion) -> None:
    df = pd.DataFrame({"planet_name": ["A b"], "value": [1.5]})
    ingestion.save_processed_data(df, "x.csv")
    pd.testing.assert_frame_equal(ingestion.load_processed_data("x.csv"), df)


def test_a_failed_explanation_keeps_the_recommendation_and_is_logged(monkeypatch: Any, caplog: Any) -> None:
    def broken(*a: Any, **k: Any) -> Any:
        raise RuntimeError("explainer down")

    monkeypatch.setattr(explainability, "get_plain_english_reasons_for_planet", broken)
    with caplog.at_level(logging.WARNING, logger="app.api.v1"):
        response = TestClient(app).get("/api/v1/recommendations", params={"limit": 2})
    assert response.status_code == 200
    assert all(rec["reasons"] == [] for rec in response.json())
    assert "Explanation reasons unavailable" in caplog.text


def test_cors_origins_that_are_not_json_are_read_as_a_list() -> None:
    assert Settings.assemble_cors_origins("[https://a.example, https://b.example]") == [
        "[https://a.example",
        "https://b.example]",
    ]
    assert Settings.assemble_cors_origins('["https://a.example"]') == ["https://a.example"]
    assert Settings.assemble_cors_origins("https://a.example, https://b.example") == [
        "https://a.example",
        "https://b.example",
    ]


def test_a_reason_template_that_cannot_read_its_value_uses_the_generic_sentence(monkeypatch: Any) -> None:
    def bad_template(value: str) -> str:
        raise ValueError("unexpected format")

    monkeypatch.setitem(explainability.PLAIN_ENGLISH_TEMPLATES, "distance", bad_template)
    text = explainability.format_plain_english_reason("distance", "Distance", "12 pc")
    assert text == "Distance (12 pc) is a primary positive driver for spectroscopic follow-up"


def test_a_corrupt_json_artifact_is_logged_and_skipped(tmp_path: Path, caplog: Any) -> None:
    engine = CatalogQueryEngine.get_instance()
    original = engine.artifacts_dir
    (tmp_path / "broken.json").write_text("{ not json")
    try:
        engine.artifacts_dir = tmp_path
        with caplog.at_level(logging.WARNING, logger="app.services.query_engine"):
            assert engine._load_json_artifact("broken.json") == {}
    finally:
        engine.artifacts_dir = original
    assert "Failed to load" in caplog.text


@pytest.mark.parametrize(
    "path, target",
    [
        ("/api/v1/planets", "query_planets"),
        ("/api/v1/top-targets", "get_top_targets"),
        ("/api/v1/analysis", "get_analysis_stats"),
    ],
)
def test_an_unexpected_error_uses_the_global_error_contract(monkeypatch: Any, path: str, target: str) -> None:
    """The routes no longer wrap their bodies: the global handler answers with the same schema and status."""

    def broken(*a: Any, **k: Any) -> Any:
        raise RuntimeError("internal secret detail")

    monkeypatch.setattr(CatalogQueryEngine.get_instance(), target, broken)
    response = TestClient(app, raise_server_exceptions=False).get(path)
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert body["error"]["status_code"] == 500
    assert body["error"]["request_id"] and response.headers["X-Request-ID"] == body["error"]["request_id"]
    assert "internal secret detail" not in response.text
