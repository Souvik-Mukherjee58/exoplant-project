"""An explanation must explain the score that the catalog serves (audit finding F-01).

The served scores come from LTRFeatureExtractor.transform() (score_catalog). The SHAP explainer once used a
separate scalar feature path with different formulas and missing-value rules, so for hundreds of planets it
explained a different score (up to 51 points apart). These tests compare the two paths for every eligible planet.
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml.explainability import SHAPExplainer
from app.services.query_engine import CatalogQueryEngine

client = TestClient(app)
TOLERANCE = 0.01  # score points
DOCUMENTED_ESTIMATES = {"j_magnitude", "k_magnitude", "planet_mass", "earth_similarity"}


def _score(margin: float) -> float:
    return float(100.0 / (1.0 + np.exp(-margin)))


@pytest.fixture(scope="module")
def explainer() -> SHAPExplainer:
    return SHAPExplainer.get_instance()


INPUTS = [
    "planet_radius", "planet_mass", "orbital_period", "semi_major_axis", "equilibrium_temperature",
    "stellar_effective_temperature", "stellar_radius", "stellar_mass", "stellar_metallicity",
    "distance", "j_magnitude", "k_magnitude", "earth_similarity",
]  # fmt: skip


@pytest.fixture(scope="module")
def eligible() -> pd.DataFrame:
    cursor = CatalogQueryEngine.get_instance().get_cursor()
    df = cursor.execute("SELECT * FROM planets WHERE eligible_for_transmission").df()
    assert len(df) > 1000, "the served catalog should hold thousands of eligible planets"
    return df.reset_index(drop=True)


@pytest.fixture(scope="module")
def checked(eligible: pd.DataFrame) -> pd.DataFrame:
    """Every planet with a missing model input (where the old paths diverged), every 10th other planet,
    and the planets that were furthest apart before the fix: about 800 of the 4,643. The full catalog is
    compared outside the test suite (about 90 s), with the same result."""
    missing_input = eligible[INPUTS].isna().any(axis=1)
    worst_before = eligible["planet_name"].isin({"K2-371 b", "TOI-5789 c", "WASP-193 b"})
    picked = eligible[missing_input | (eligible.index % 10 == 0) | worst_before]
    assert missing_input.sum() > 100 and len(picked) > 500
    return picked.reset_index(drop=True)


@pytest.fixture(scope="module")
def single_rows(explainer: SHAPExplainer, checked: pd.DataFrame) -> np.ndarray:
    fx = explainer.ltr_model.feature_extractor
    return np.vstack([fx.transform_single(row.to_dict())[0][0] for _, row in checked.iterrows()])


def test_single_planet_features_equal_the_batch_features(
    explainer: SHAPExplainer, eligible: pd.DataFrame, checked: pd.DataFrame, single_rows: np.ndarray
) -> None:
    # The batch is the whole catalog, as score_catalog() scores it; the single rows are taken one at a time.
    batch_all = explainer.ltr_model.feature_extractor.transform(eligible)
    position = {name: i for i, name in enumerate(eligible["planet_name"])}
    batch = batch_all[[position[name] for name in checked["planet_name"]]]
    assert single_rows.shape == batch.shape
    np.testing.assert_allclose(single_rows, batch, rtol=0, atol=1e-12)


def test_explained_score_equals_the_served_score_for_unlabelled_planets(
    explainer: SHAPExplainer, checked: pd.DataFrame, single_rows: np.ndarray
) -> None:
    unlabelled = checked["already_observed_jwst"].ne(True).to_numpy()  # nullable column: missing counts as unlabelled
    assert unlabelled.sum() > 500
    explained = np.array([_score(explainer.ltr_model.get_linear_shap(x)[2]) for x in single_rows[unlabelled]])
    served = pd.to_numeric(checked.loc[unlabelled, "priority_score"]).to_numpy()
    diff = np.abs(explained - served)
    worst = checked.loc[unlabelled, "planet_name"].to_numpy()[int(diff.argmax())]
    assert diff.max() < TOLERANCE, f"largest difference {diff.max():.4f} points ({worst})"


def _sample(eligible: pd.DataFrame) -> List[Dict[str, Any]]:
    """Every 50th planet plus the planets that were furthest apart before the fix."""
    names = {"K2-371 b", "TOI-5789 c", "WASP-193 b"}
    picked = eligible.iloc[::50]
    extra = eligible[eligible["planet_name"].isin(names)]
    return [row.to_dict() for _, row in pd.concat([picked, extra]).drop_duplicates("planet_name").iterrows()]


def test_explain_planet_reports_the_served_score_and_stays_additive(
    explainer: SHAPExplainer, eligible: pd.DataFrame
) -> None:
    for planet in _sample(eligible):
        result = explainer.explain_planet(planet)
        inv = result["mathematical_invariants"]
        assert abs(inv["sum_shap_margin"] + inv["base_margin"] - inv["predicted_margin"]) < 1e-5
        exact = _score(inv["predicted_margin"])
        assert abs(result["ml_priority_score"] - exact) <= 0.05 + 1e-9  # the response rounds to 0.1
        served = float(planet["priority_score"])
        assert result["served_priority_score"] == pytest.approx(round(served, 2))
        if planet.get("already_observed_jwst") is not True:
            assert abs(exact - served) < TOLERANCE, planet["planet_name"]
            assert result["explains_served_score"] is True


def test_labelled_planets_say_that_the_served_score_is_out_of_fold(
    explainer: SHAPExplainer, eligible: pd.DataFrame
) -> None:
    labelled = eligible[eligible["already_observed_jwst"].eq(True)]
    assert len(labelled) > 0
    for _, row in labelled.iterrows():
        result = explainer.explain_planet(row.to_dict())
        exact = _score(result["mathematical_invariants"]["predicted_margin"])
        same = abs(exact - float(row["priority_score"])) < TOLERANCE
        assert result["explains_served_score"] is same


@pytest.mark.parametrize(
    "missing",
    [
        ["distance"],
        ["k_magnitude"],
        ["j_magnitude"],
        ["j_magnitude", "k_magnitude"],
        ["planet_mass"],
        ["stellar_radius", "stellar_effective_temperature"],
        ["semi_major_axis", "equilibrium_temperature"],
        ["earth_similarity", "hz_status"],
        ["planet_radius", "planet_mass", "distance", "j_magnitude", "k_magnitude", "stellar_radius"],
    ],
)
def test_missing_values_take_the_same_path_alone_and_in_a_batch(
    explainer: SHAPExplainer, eligible: pd.DataFrame, missing: List[str]
) -> None:
    fx = explainer.ltr_model.feature_extractor
    records = [row.to_dict() for _, row in eligible.head(5).iterrows()]
    for record in records:
        for key in missing:
            record[key] = None
    batch = fx.transform(pd.DataFrame(records))
    for i, record in enumerate(records):
        x, raw = fx.transform_single(record)
        np.testing.assert_allclose(x[0], batch[i], rtol=0, atol=1e-12)
        for key in missing:
            if key not in raw:
                continue
            # Never a silent 0 (the R17 defect). Only the model's documented estimates may fill a gap:
            # J and K from each other, the mass from the radius (Chen & Kipping) and the default ESI.
            assert pd.isna(raw[key]) or raw[key] != 0.0, f"{key} became 0"
            if key not in DOCUMENTED_ESTIMATES:
                assert pd.isna(raw[key]), f"{key} has no documented estimate and must stay missing"


def test_transform_single_requires_a_fitted_extractor(explainer: SHAPExplainer) -> None:
    fresh = type(explainer.ltr_model.feature_extractor)()
    with pytest.raises(ValueError):
        fresh.transform_single({"planet_radius": 1.0})


def test_the_api_explanations_use_the_served_scores(eligible: pd.DataFrame) -> None:
    unlabelled = eligible[eligible["already_observed_jwst"].ne(True)]
    row = unlabelled[unlabelled["planet_name"] == "K2-371 b"].iloc[0]
    served = float(row["priority_score"])

    single = client.get("/api/v1/planets/K2-371 b/explain")
    assert single.status_code == 200
    body = single.json()
    assert abs(body["ml_priority_score"] - served) <= 0.05 + 1e-9
    assert body["explains_served_score"] is True

    other = unlabelled.iloc[0]
    compare = client.get(
        "/api/v1/planets/compare-explain", params={"planet_a": "K2-371 b", "planet_b": other["planet_name"]}
    )
    assert compare.status_code == 200
    assert abs(compare.json()["planet_a_score"] - served) <= 0.05 + 1e-9
    assert abs(compare.json()["planet_b_score"] - float(other["priority_score"])) <= 0.05 + 1e-9

    recs = client.get("/api/v1/recommendations", params={"limit": 5})
    assert recs.status_code == 200
    for rec in recs.json():
        explained = client.get(f"/api/v1/planets/{rec['planet_name']}/explain").json()
        assert abs(explained["ml_priority_score"] - rec["priority_score"]) <= 0.05 + 1e-9
        assert rec["reasons"], "every recommendation should carry its explanation's reasons"


EXPLAINED_PLANET = "K2-371 b"  # unlabelled; its explained score is about 82.7


def _explain_with_served_score(monkeypatch: pytest.MonkeyPatch, eligible: pd.DataFrame, served: Any) -> Dict[str, Any]:
    """The API explanation of a real planet whose catalog row carries `served` as its priority_score.

    Only the row lookup is replaced: the model, its features and the explanation are the real ones, so the
    explained score stays where it is while the served score is set to values far from it, at it, or missing.
    """
    row = eligible[eligible["planet_name"] == EXPLAINED_PLANET].iloc[0].to_dict()
    row["priority_score"] = served
    monkeypatch.setattr(CatalogQueryEngine.get_instance(), "get_planet_by_name", lambda name: dict(row))
    response = client.get(f"/api/v1/planets/{EXPLAINED_PLANET}/explain")
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize(
    "served, reported, explains",
    [
        (12.34, 12.34, False),  # far below the explained score: the catalog's value is reported, not the explained one
        (0.0, 0.0, False),  # a genuine zero is a served score, not a missing one
        (None, None, None),  # no served score: both fields are null (and still present)
        (float("nan"), None, None),
    ],
    ids=["distinct", "zero", "none", "nan"],
)
def test_served_priority_score_is_the_catalog_score_not_the_explained_score(
    monkeypatch: pytest.MonkeyPatch, eligible: pd.DataFrame, served: Any, reported: Any, explains: Any
) -> None:
    body = _explain_with_served_score(monkeypatch, eligible, served)
    explained = _score(body["mathematical_invariants"]["predicted_margin"])
    assert explained > 50  # so 12.34 and 0.0 are far from the explained score
    assert abs(body["ml_priority_score"] - explained) <= 0.05 + 1e-9  # the explanation itself is unchanged
    assert "served_priority_score" in body and "explains_served_score" in body
    if reported is None:
        assert body["served_priority_score"] is None
    else:
        assert body["served_priority_score"] is not None and body["served_priority_score"] == reported
    assert body["explains_served_score"] is explains


@pytest.mark.parametrize(
    "offset, explains", [(0.0, True), (0.004, True), (-0.004, True), (0.03, False), (-0.03, False)]
)
def test_explains_served_score_says_whether_the_served_score_is_the_explained_one(
    monkeypatch: pytest.MonkeyPatch, eligible: pd.DataFrame, offset: float, explains: bool
) -> None:
    explained = _score(
        _explain_with_served_score(monkeypatch, eligible, None)["mathematical_invariants"]["predicted_margin"]
    )
    served = explained + offset  # within or beyond the 0.01-point tolerance of the explained score
    body = _explain_with_served_score(monkeypatch, eligible, served)
    assert body["served_priority_score"] == round(served, 2)
    assert body["explains_served_score"] is explains
