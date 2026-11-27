"""One PCA implementation for the pipeline and the API fallback (audit finding F-11)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml.pca_projection import PCA_FEATURES, project_catalog
from app.services.query_engine import CatalogQueryEngine


@pytest.fixture(scope="module")
def catalog() -> pd.DataFrame:
    return CatalogQueryEngine.get_instance().get_cursor().execute("SELECT * FROM planets").df()


@pytest.fixture(scope="module")
def stored() -> dict:
    engine = CatalogQueryEngine.get_instance()
    path = Path(engine.artifacts_dir) / str(engine.active_version) / "precomputed_pca.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_shared_function_reproduces_the_committed_projection_exactly(catalog: pd.DataFrame, stored: dict) -> None:
    result = project_catalog(catalog)
    assert list(result) == list(stored)  # same keys in the same order
    for key in stored:
        assert result[key] == stored[key], key


def test_the_api_fallback_gives_the_same_projection(stored: dict) -> None:
    assert CatalogQueryEngine.get_instance()._compute_pca_in_memory() == stored


def test_fewer_than_two_features_is_an_error() -> None:
    df = pd.DataFrame({"planet_name": ["a", "b"], "planet_radius": [1.0, 2.0]})
    assert project_catalog(df) == {"error": "Insufficient features for PCA"}


def _small_catalog(n: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({f: rng.normal(size=n) for f in reversed(PCA_FEATURES[:5])})
    df.insert(0, "planet_name", [f"P{i}" for i in range(n)])
    df["anomaly_score"] = rng.uniform(size=n)
    df["hz_status"] = "Outside HZ"
    return df


def test_a_small_catalog_uses_every_planet_in_its_order_and_keeps_the_feature_order() -> None:
    df = _small_catalog()
    result = project_catalog(df)
    assert result["planets"] == df["planet_name"].tolist()
    assert result["feature_names"] == PCA_FEATURES[:5]  # the documented order, not the frame's column order
    assert len(result["pca_x"]) == len(result["pca_y"]) == len(df)


def test_missing_values_never_become_numbers_or_nan_in_the_output() -> None:
    df = _small_catalog()
    df.loc[[1, 5, 9], "planet_radius"] = np.nan
    df.loc[3, "anomaly_score"] = np.nan
    df["earth_similarity"] = np.nan  # a feature with no value at all
    result = project_catalog(df)
    assert result["anomaly_score"][3] is None
    assert result["priority_score"] == [None] * len(df)  # the column is absent
    json.dumps(result, allow_nan=False)  # raises on NaN or infinity
    assert all(np.isfinite(result["pca_x"])) and all(np.isfinite(result["pca_y"]))
