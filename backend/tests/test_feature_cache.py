"""The explainer caches each planet's features (a regression found while fixing audit finding F-01).

transform_single() runs the batch feature code on a one-row frame, so the explanation explains the served score,
but pandas overhead made that ~40 times slower per planet than the old scalar path (0.2 ms to 9 ms). The
explainer now caches features by the planet's input values and fills the cache at startup with one vectorized
transform of the catalog. A cached entry must equal what transform_single() computes, and the cache key must
contain every column the feature code reads.
"""

import time
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest

from app.ml import explainability
from app.ml.explainability import SHAPExplainer, _feature_key
from app.ml.ltr_model import RAW_INPUT_COLUMNS
from app.services.query_engine import CatalogQueryEngine


@pytest.fixture(scope="module")
def catalog() -> pd.DataFrame:
    return CatalogQueryEngine.get_instance().get_cursor().execute("SELECT * FROM planets").df()


@pytest.fixture
def fresh(monkeypatch: pytest.MonkeyPatch) -> SHAPExplainer:
    """The served explainer with an empty cache of its own."""
    explainer = SHAPExplainer.get_instance()
    monkeypatch.setattr(explainer, "_feature_cache", {})
    return explainer


def _same_raw(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return a.keys() == b.keys() and all((pd.isna(a[k]) and pd.isna(b[k])) or a[k] == b[k] for k in a)


def test_the_warmed_cache_equals_the_single_planet_path(fresh: SHAPExplainer, catalog: pd.DataFrame) -> None:
    assert fresh.warm_feature_cache(catalog) > 0.9 * len(catalog)  # planets with identical inputs share an entry
    fx = fresh.ltr_model.feature_extractor
    sample = catalog.iloc[::25].to_dict(orient="records")
    for record in sample:
        cached_x, cached_raw = fresh._features(record)
        x, raw = fx.transform_single(record)
        assert np.array_equal(cached_x, x), record["planet_name"]
        assert _same_raw(cached_raw, raw), record["planet_name"]


def test_explanations_are_the_same_with_and_without_the_cache(fresh: SHAPExplainer, catalog: pd.DataFrame) -> None:
    records = catalog.head(40).to_dict(orient="records")
    cold = [fresh.explain_planet(r) for r in records]
    fresh.warm_feature_cache(catalog)
    assert [fresh.explain_planet(r) for r in records] == cold


@pytest.mark.parametrize("column", RAW_INPUT_COLUMNS)
def test_every_column_the_features_read_is_in_the_key(column: str, catalog: pd.DataFrame) -> None:
    record = catalog.iloc[0].to_dict()
    changed = {**record, column: "Inside HZ" if column == "hz_status" else 12345.0}
    if record.get(column) == changed[column]:
        changed[column] = "Outside HZ"
    assert _feature_key(changed) != _feature_key(record)


def test_no_other_catalog_column_changes_the_features(fresh: SHAPExplainer, catalog: pd.DataFrame) -> None:
    """If the feature code starts reading a new column, it must be added to RAW_INPUT_COLUMNS."""
    fx = fresh.ltr_model.feature_extractor
    record = catalog[catalog["planet_name"] == "TOI-700 d"].iloc[0].to_dict()
    x0, raw0 = fx.transform_single(record)
    others = [c for c in catalog.columns if c not in RAW_INPUT_COLUMNS]
    assert len(others) > 20
    for column in others:
        value = record[column]
        changed = {**record, column: (None if isinstance(value, str) else -1.0e6)}
        x, raw = fx.transform_single(changed)
        assert np.array_equal(x, x0) and _same_raw(raw, raw0), f"{column} changes the features"


def test_missing_values_share_a_key_and_unhashable_input_is_not_cached(fresh: SHAPExplainer) -> None:
    assert _feature_key({"planet_radius": None}) == _feature_key({"planet_radius": float("nan")})
    assert _feature_key({"planet_radius": pd.NA}) == _feature_key({})
    assert _feature_key({"planet_radius": [1.0]}) is None
    fresh._features({"planet_radius": [1.0, 2.0]})  # computed, not cached
    assert fresh._feature_cache == {}


def test_callers_get_copies(fresh: SHAPExplainer, catalog: pd.DataFrame) -> None:
    record = catalog.iloc[0].to_dict()
    x, raw = fresh._features(record)
    x[0, 0] = 999.0
    raw["planet_radius"] = 999.0
    x2, raw2 = fresh._features(record)
    assert x2[0, 0] != 999.0 and raw2["planet_radius"] != 999.0


def test_the_cache_is_bounded(fresh: SHAPExplainer, catalog: pd.DataFrame, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(explainability, "FEATURE_CACHE_MAX_ENTRIES", 10)
    fresh.warm_feature_cache(catalog)
    fresh._features({**catalog.iloc[0].to_dict(), "planet_radius": 777.0})
    assert len(fresh._feature_cache) == 10


def test_a_cached_explanation_is_fast(fresh: SHAPExplainer, catalog: pd.DataFrame) -> None:
    record = catalog[catalog["planet_name"] == "TOI-700 d"].iloc[0].to_dict()
    fresh.explain_planet(record)  # computes and caches
    timings = []
    for _ in range(50):
        t0 = time.perf_counter()
        fresh.explain_planet(record)
        timings.append((time.perf_counter() - t0) * 1000.0)
    assert float(np.median(timings)) < 5.0  # ~0.3 ms on a laptop; the uncached path takes ~9 ms


def test_startup_precomputes_the_catalog(fresh: SHAPExplainer, catalog: pd.DataFrame) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:  # runs the lifespan
        assert client.get("/health").status_code == 200
    assert len(fresh._feature_cache) > 0.9 * len(catalog)


def test_a_failed_precomputation_is_logged_and_the_app_still_starts(
    fresh: SHAPExplainer, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    from fastapi.testclient import TestClient

    from app.main import app

    def broken(catalog: pd.DataFrame) -> int:
        raise RuntimeError("no catalog")

    monkeypatch.setattr(fresh, "warm_feature_cache", broken)
    with caplog.at_level(logging.WARNING, logger="app.main"):
        with TestClient(app) as client:
            assert client.get("/health").json()["status"] == "ok"
    assert "Could not precompute explanation features" in caplog.text
    assert "Could not initialize Linear SHAP explainer" not in caplog.text
