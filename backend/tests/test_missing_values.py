"""Missing values stay missing (a missing value is not 0.0). SYNTHETIC TEST DATA: fictional planets."""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.config import settings
from app.numeric import zero_where_missing
from app.scoring.priority_scorer import TargetPriorityScorer
from app.services.data_cleaning import DataCleaning
from app.services.feature_engineering import FeatureEngineering

APP = Path(__file__).resolve().parent.parent / "app"


def frame():
    known = {
        "planet_name": "SYN-1 b",
        "distance": 10.0,
        "k_magnitude": 8.0,
        "planet_radius": 1.1,
        "planet_mass": 1.2,
        "stellar_radius": 0.5,
        "stellar_mass": 0.5,
        "stellar_effective_temperature": 4000.0,
        "stellar_metallicity": 0.0,
        "orbital_period": 5.0,
        "semi_major_axis": 0.05,
        "equilibrium_temperature": 300.0,
        "hz_status": "Outside HZ",
        "anomaly_score": 0.1,
    }
    unknown = {k: (np.nan if isinstance(v, float) else v) for k, v in known.items()} | {"planet_name": "SYN-2 b"}
    zero = known | {"planet_name": "SYN-3 b", "distance": 0.0, "stellar_metallicity": 0.0}
    return pd.DataFrame([known, unknown, zero])


def test_helper_leaves_its_input_alone():
    for values in (
        pd.Series([1.0, np.nan, 0.0]),
        np.array([1.0, np.nan, 0.0]),
        pd.DataFrame({"a": [1.0, np.nan, 0.0]})["a"],
    ):
        assert zero_where_missing(values).tolist() == [1.0, 0.0, 0.0]
        assert np.isnan(np.asarray(values)[1])


def test_accessibility_components_stay_missing():
    out = FeatureEngineering().add_observational_accessibility(frame())
    for column in ("distance_score", "brightness_score", "transit_detectability", "observational_accessibility"):
        assert np.isnan(out[column].iloc[1]), column
        assert out[column].iloc[0] > 0, column
    assert out["distance_score"].iloc[2] == 1.0  # a genuine 0 is a value


@pytest.mark.parametrize("method", ["calculate_planetary_relevance", "calculate_stellar_characteristics", "score"])
def test_scoring_changes_no_input_column(method):
    df = (
        FeatureEngineering().transform(frame())
        if method == "score"
        else frame().assign(earth_similarity=[0.9, np.nan, 0.0])
    )
    before = df.copy(deep=True)
    out = getattr(TargetPriorityScorer(), method)(df)
    out = out.set_index("planet_name").loc[df["planet_name"]].reset_index()  # score() sorts
    pd.testing.assert_frame_equal(df, before)
    for column in before.columns.intersection(out.columns):
        if pd.api.types.is_float_dtype(before[column]) and column != "target_priority_score":
            assert out[column].isna().tolist() == before[column].isna().tolist(), column
    if method == "calculate_planetary_relevance":
        assert np.isnan(out["earth_similarity"].iloc[1]) and out["earth_similarity"].iloc[2] == 0.0


def test_the_archive_snapshot_keeps_its_missing_values():
    """The served catalog has 11, 28, 299 and 379 missing values here; a rebuild must have them too."""
    raw = pd.read_csv(Path(settings.resolve_path(Path("data/raw"))) / "nasa_exoplanet_archive.csv")
    scored = TargetPriorityScorer().score(
        FeatureEngineering().transform(DataCleaning().clean(raw)).assign(anomaly_score=0.1)
    )
    served = pd.read_parquet(APP.parent / "artifacts" / "v1_2026-10-29" / "planets.parquet").set_index("planet_name")
    scored = scored.set_index("planet_name").reindex(served.index)
    for column, n in (
        ("earth_similarity", 11),
        ("distance_score", 28),
        ("brightness_score", 299),
        ("transit_detectability", 379),
    ):
        assert served[column].isna().sum() == n
        assert scored[column].isna().tolist() == served[column].isna().tolist(), column


def test_nan_to_num_is_not_used_on_columns():
    """Allowed only on plain arrays in the anomaly detector."""
    users = {p.name for p in APP.rglob("*.py") if re.search(r"np\.nan_to_num\(", p.read_text(encoding="utf-8"))}
    assert users == {"anomaly_detection.py"}
