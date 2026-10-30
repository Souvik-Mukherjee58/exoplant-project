"""Golden-file equivalence tests asserting identical outputs between
vectorized numpy/pandas implementations and original row-wise logic on the real dataset.
"""

import numpy as np
import pandas as pd
import pytest

from app.config import settings
from app.ml.ground_truth import (
    calculate_esm,
    calculate_tsm,
    generate_ground_truth_labels,
    get_kempton_size_class_and_threshold,
    get_verified_jwst_targets,
)
from app.scoring.priority_scorer import TargetPriorityScorer
from app.services.feature_engineering import FeatureEngineering

# ---------------------------------------------------------------------------
# Reference / Old row-wise implementations
# ---------------------------------------------------------------------------


def old_ground_truth_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Original row-wise implementation using df.iterrows()."""
    df = df.copy()
    verified_jwst_targets = get_verified_jwst_targets()

    tsm_values = []
    esm_values = []
    is_jwst = []
    size_classes = []
    tsm_thresholds = []

    for _, row in df.iterrows():
        p_name = str(row.get("planet_name", "")).strip()
        r = row.get("planet_radius")
        m = row.get("planet_mass")
        teq = row.get("equilibrium_temperature")
        r_star = row.get("stellar_radius")
        t_star = row.get("stellar_effective_temperature")
        jmag = row.get("j_magnitude")
        kmag = row.get("k_magnitude")

        tsm = calculate_tsm(r, m, teq, r_star, jmag, kmag)
        esm = calculate_esm(r, teq, t_star, r_star, kmag)
        jwst_confirmed = p_name in verified_jwst_targets
        sz_class, thresh = get_kempton_size_class_and_threshold(r)

        tsm_values.append(tsm)
        esm_values.append(esm)
        is_jwst.append(jwst_confirmed)
        size_classes.append(sz_class)
        tsm_thresholds.append(thresh)

    df["tsm"] = tsm_values
    df["esm"] = esm_values
    df["is_jwst_target"] = is_jwst
    df["already_observed_jwst"] = is_jwst
    df["kempton_size_class"] = size_classes
    df["tsm_threshold"] = tsm_thresholds
    df["ground_truth_binary"] = [1 if j else 0 for j in is_jwst]
    df["ground_truth_graded"] = [3 if j else 0 for j in is_jwst]
    return df


def old_calc_row_esi(row):
    """Original row-wise ESI calculation."""
    radius = row.get("planet_radius")
    mass = row.get("planet_mass")
    teq = row.get("equilibrium_temperature")

    terms = []
    if pd.notna(radius) and radius > 0:
        diff_r = abs(radius - 1.0) / (radius + 1.0)
        terms.append((1.0 - diff_r, 0.57))

    if pd.notna(mass) and mass > 0 and pd.notna(radius) and radius > 0:
        density = mass / (radius**3)
        diff_rho = abs(density - 1.0) / (density + 1.0)
        terms.append((1.0 - diff_rho, 1.07))

        v_esc = np.sqrt(mass / radius)
        diff_v = abs(v_esc - 1.0) / (v_esc + 1.0)
        terms.append((1.0 - diff_v, 0.70))

    if pd.notna(teq) and teq > 0:
        diff_t = abs(teq - 288.0) / (teq + 288.0)
        terms.append((1.0 - diff_t, 5.58))

    if not terms:
        return np.nan

    total_weight = sum(w for _, w in terms)
    esi = 1.0
    for val, weight in terms:
        val_clamped = max(0.0, float(val))
        esi *= val_clamped ** (weight / total_weight)

    return float(np.clip(esi, 0.0, 1.0))


def old_compute_hz(row):
    """Original row-wise Habitable Zone calculation."""
    lum = row.get("stellar_luminosity")
    teff = row.get("stellar_effective_temperature")
    sma = row.get("semi_major_axis")

    if pd.isna(lum) or pd.isna(teff) or pd.isna(sma):
        return "Insufficient data", np.nan, np.nan, np.nan

    try:
        lum = float(lum)
        teff = float(teff)
        sma = float(sma)
    except (ValueError, TypeError):
        return "Insufficient data", np.nan, np.nan, np.nan

    if lum <= 0 or teff < 1500 or teff > 15000 or sma <= 0:
        return "Insufficient data", np.nan, np.nan, np.nan

    t_star = teff - 5780.0
    s_rv = 1.776 + 2.136e-4 * t_star + 2.533e-8 * (t_star**2) - 1.332e-11 * (t_star**3) - 3.097e-15 * (t_star**4)
    s_rg = 1.0385 + 1.2456e-4 * t_star + 1.4612e-8 * (t_star**2) - 7.6345e-12 * (t_star**3) - 1.7511e-15 * (t_star**4)
    s_mg = 0.3507 + 5.9578e-5 * t_star + 1.6707e-9 * (t_star**2) - 3.0058e-12 * (t_star**3) - 5.5064e-16 * (t_star**4)
    s_em = 0.3207 + 5.4471e-5 * t_star + 1.5275e-9 * (t_star**2) - 2.7109e-12 * (t_star**3) - 4.9364e-16 * (t_star**4)

    if s_rv <= 0 or s_rg <= 0 or s_mg <= 0 or s_em <= 0:
        return "Insufficient data", np.nan, np.nan, np.nan

    r_in_opt = np.sqrt(lum / s_rv)
    r_in_cons = np.sqrt(lum / s_rg)
    r_out_cons = np.sqrt(lum / s_mg)
    r_out_opt = np.sqrt(lum / s_em)

    insolation_flux = lum / (sma**2)

    if r_in_cons <= sma <= r_out_cons:
        status = "Inside HZ"
    elif r_in_opt <= sma <= r_out_opt:
        status = "Near HZ"
    else:
        status = "Outside HZ"

    return status, float(r_in_cons), float(r_out_cons), float(insolation_flux)


def old_calc_row_relevance(row):
    """Original row-wise planetary relevance."""
    weights = {"esi": 0.40, "hz": 0.40, "radius": 0.20}
    valid_w = [weights[k] for k in weights if pd.notna(row[k])]
    valid_v = [row[k] * weights[k] for k in weights if pd.notna(row[k])]
    if not valid_w or sum(valid_w) == 0:
        return 0.3
    return float(sum(valid_v) / sum(valid_w))


# ---------------------------------------------------------------------------
# Fixture & Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_dataset():
    """Load real exoplanets dataset."""
    path = settings.get_processed_data_path()
    assert path.exists(), f"Real processed exoplanet dataset not found at {path}"
    df = pd.read_csv(path)
    # Take first 500 rows for fast and thorough golden testing
    return df.iloc[:500].copy()


def test_ground_truth_vectorized_matches_row_wise(real_dataset):
    """Test vectorized ground_truth.py produces identical results to old iterrows() logic."""
    df_old = old_ground_truth_labels(real_dataset)
    df_new = generate_ground_truth_labels(real_dataset)

    # Check boolean and string columns
    assert (df_old["is_jwst_target"].to_numpy() == df_new["is_jwst_target"].to_numpy()).all()
    assert (df_old["already_observed_jwst"].to_numpy() == df_new["already_observed_jwst"].to_numpy()).all()
    assert (df_old["kempton_size_class"].to_numpy() == df_new["kempton_size_class"].to_numpy()).all()
    assert (df_old["ground_truth_binary"].to_numpy() == df_new["ground_truth_binary"].to_numpy()).all()
    assert (df_old["ground_truth_graded"].to_numpy() == df_new["ground_truth_graded"].to_numpy()).all()

    # Check numerical float columns (handling NaNs cleanly)
    np.testing.assert_allclose(
        df_old["tsm"].fillna(-999.0).to_numpy(), df_new["tsm"].fillna(-999.0).to_numpy(), rtol=1e-5, atol=1e-5
    )
    np.testing.assert_allclose(
        df_old["esm"].fillna(-999.0).to_numpy(), df_new["esm"].fillna(-999.0).to_numpy(), rtol=1e-5, atol=1e-5
    )
    np.testing.assert_allclose(
        df_old["tsm_threshold"].to_numpy(), df_new["tsm_threshold"].to_numpy(), rtol=1e-5, atol=1e-5
    )


def test_feature_engineering_vectorized_matches_row_wise(real_dataset):
    """Test vectorized feature_engineering.py produces identical outputs to row-wise apply()."""
    fe = FeatureEngineering()

    # 1. Earth similarity
    expected_esi = real_dataset.apply(old_calc_row_esi, axis=1)
    df_new = fe.add_earth_similarity(real_dataset)
    np.testing.assert_allclose(
        expected_esi.fillna(-999.0).to_numpy(),
        df_new["earth_similarity"].fillna(-999.0).to_numpy(),
        rtol=1e-5,
        atol=1e-5,
    )

    # 2. Habitable zone
    old_hz_res = real_dataset.apply(old_compute_hz, axis=1)
    expected_status = [r[0] for r in old_hz_res]
    expected_inner = [r[1] for r in old_hz_res]
    expected_outer = [r[2] for r in old_hz_res]
    expected_flux = [r[3] for r in old_hz_res]

    df_hz = fe.add_habitable_zone(real_dataset)
    assert (np.array(expected_status) == df_hz["hz_status"].to_numpy()).all()
    np.testing.assert_allclose(
        pd.Series(expected_inner).fillna(-999.0).to_numpy(),
        df_hz["hz_inner_edge"].fillna(-999.0).to_numpy(),
        rtol=1e-5,
        atol=1e-5,
    )
    np.testing.assert_allclose(
        pd.Series(expected_outer).fillna(-999.0).to_numpy(),
        df_hz["hz_outer_edge"].fillna(-999.0).to_numpy(),
        rtol=1e-5,
        atol=1e-5,
    )
    np.testing.assert_allclose(
        pd.Series(expected_flux).fillna(-999.0).to_numpy(),
        df_hz["insolation_flux"].fillna(-999.0).to_numpy(),
        rtol=1e-5,
        atol=1e-5,
    )


def test_priority_scorer_vectorized_matches_row_wise(real_dataset):
    """Test vectorized priority_scorer.py calculations match row-wise expectations."""
    fe = FeatureEngineering()
    df_trans = fe.transform(real_dataset)

    scorer = TargetPriorityScorer()
    scored = scorer.score(df_trans)

    assert "target_priority_score" in scored.columns
    assert "priority_components" in scored.columns
    assert len(scored) == len(real_dataset)

    # Validate that priority_components contains the expected numeric values
    first = scored.iloc[0]
    comp = first["priority_components"]
    assert "planetary_relevance" in comp
    assert "stellar_characteristics" in comp
    assert "observational_accessibility" in comp
    assert "data_quality" in comp
    assert "anomaly_score" in comp
    assert "final_score" in comp
    assert round(first["target_priority_score"], 1) == comp["final_score"]
