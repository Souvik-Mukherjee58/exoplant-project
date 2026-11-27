"""The artifact's schema is checked once, when the engine starts (audit finding F-09).

Each artifact version has a fixed schema, so the engine reads its columns at startup, refuses an artifact
without the columns every query needs, and the queries no longer run DESCRIBE on every request. Optional
columns (absent from older artifacts) keep their fallbacks.
"""

from pathlib import Path
from typing import Any, List

import duckdb
import pytest

from app.services.query_engine import REQUIRED_COLUMNS, CatalogQueryEngine

SERVED = Path(CatalogQueryEngine.get_instance().parquet_path)


def _artifact(tmp_path: Path, select: str = "*") -> Path:
    """A one-version artifact directory whose planets.parquet is a projection of the served catalog."""
    version = tmp_path / "artifacts" / "v_test"
    version.mkdir(parents=True)
    out = (version / "planets.parquet").as_posix()
    duckdb.connect().execute(
        f"COPY (SELECT {select} FROM read_parquet('{SERVED.as_posix()}')) TO '{out}' (FORMAT parquet)"
    )
    (tmp_path / "artifacts" / "active_version.txt").write_text("v_test")
    return tmp_path / "artifacts"


def test_a_valid_artifact_is_read_once_with_its_columns(tmp_path: Path) -> None:
    engine = CatalogQueryEngine(artifacts_dir=str(_artifact(tmp_path)))
    try:
        assert REQUIRED_COLUMNS <= engine.columns
        assert engine.query_planets(limit=5, sort_by="priority")
    finally:
        engine.close()


@pytest.mark.parametrize("dropped", ["planet_name", "ml_priority_score", "hz_status"])
def test_an_artifact_without_a_required_column_fails_at_startup(tmp_path: Path, dropped: str) -> None:
    with pytest.raises(RuntimeError, match=dropped):
        CatalogQueryEngine(artifacts_dir=str(_artifact(tmp_path, f"* EXCLUDE ({dropped})")))


def test_a_corrupt_artifact_fails_at_startup(tmp_path: Path) -> None:
    version = tmp_path / "artifacts" / "v_bad"
    version.mkdir(parents=True)
    (version / "planets.parquet").write_bytes(b"this is not a parquet file")
    (tmp_path / "artifacts" / "active_version.txt").write_text("v_bad")
    with pytest.raises(duckdb.Error):
        CatalogQueryEngine(artifacts_dir=str(tmp_path / "artifacts"))


def test_an_older_artifact_without_optional_columns_is_still_served(tmp_path: Path) -> None:
    optional = "priority_rank, priority_score, eligible_for_transmission, kempton_size_class, oof_ml_rank"
    engine = CatalogQueryEngine(artifacts_dir=str(_artifact(tmp_path, f"* EXCLUDE ({optional})")))
    try:
        assert "priority_rank" not in engine.columns
        rows = engine.query_planets(limit=5, sort_by="priority", min_priority=10.0)
        assert rows and all(r["ml_priority_score"] >= 10.0 for r in rows)  # filters on ml_priority_score instead
        assert engine.query_planets(limit=3, size_class="giant") is not None
    finally:
        engine.close()


class _Recorder:
    """A cursor stand-in that records the SQL it runs."""

    def __init__(self, cursor: Any, seen: List[str]) -> None:
        self._cursor, self._seen = cursor, seen

    def execute(self, sql: str, *args: Any) -> Any:
        self._seen.append(sql)
        return self._cursor.execute(sql, *args)


def test_queries_no_longer_describe_the_table_per_request(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = CatalogQueryEngine.get_instance()
    seen: List[str] = []
    real = engine.get_cursor
    monkeypatch.setattr(engine, "get_cursor", lambda: _Recorder(real(), seen))
    engine.query_planets(limit=5, sort_by="priority", exclude_observed=True, size_class="terrestrial")
    engine.get_known_jwst_targets()
    assert seen and not any("DESCRIBE" in sql for sql in seen)
