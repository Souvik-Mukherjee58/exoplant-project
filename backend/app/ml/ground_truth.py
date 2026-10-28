"""Ground-truth formulation for exoplanet spectroscopic follow-up targets.

Implements published astronomical ground truth:
1. Transmission Spectroscopy Metric (TSM) - Kempton et al. (2018), PASP 130:114401.
2. Emission Spectroscopy Metric (ESM) - Kempton et al. (2018).
3. NASA / STScI Approved JWST Cycle 1, 2, and 3 Atmospheric Characterization Programs.
4. Empirical Mass-Radius relations (Chen & Kipping 2017) for missing masses.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd


def load_jwst_transmission_targets(reference_path: Optional[str] = None) -> pd.DataFrame:
    """Load JWST transmission targets reference catalog."""
    if reference_path:
        csv_path = Path(reference_path)
    else:
        # Check standard locations
        candidates = [
            Path("data/reference/jwst_transmission_targets.csv"),
            Path("backend/data/reference/jwst_transmission_targets.csv"),
            Path(__file__).resolve().parent.parent.parent / "data" / "reference" / "jwst_transmission_targets.csv",
        ]
        csv_path = next((p for p in candidates if p.exists()), candidates[0])

    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame(columns=["planet_name", "program_id", "cycle", "mode", "source_url"])


def get_verified_jwst_targets(reference_path: Optional[str] = None) -> Set[str]:
    """
    Get set of verified JWST transmission targets.
    Excludes non-transiting planets and unverified entries with empty program_id (marked with TODO).
    """
    df = load_jwst_transmission_targets(reference_path)
    if df.empty or "planet_name" not in df.columns:
        return set()
    verified = df[df["program_id"].notna() & (df["program_id"].astype(str).str.strip() != "")]
    return set(verified["planet_name"].astype(str).str.strip())


# Backward-compatible reference to verified JWST targets loaded from reference CSV
CONFIRMED_JWST_ATMOSPHERIC_TARGETS: Set[str] = get_verified_jwst_targets()



def estimate_planet_mass(radius_earth: float) -> float:
    """
    Estimate planet mass from radius using Chen & Kipping (2017) empirical relations.
    Used when empirical RV or TTV mass measurement is missing in astronomical catalogs.

    - Terran regime (< 1.23 R_earth): M = 0.9718 * R^3.58
    - Neptunian regime (1.23 - 14.26 R_earth): M = 2.69 * R^0.93
    """
    if pd.isna(radius_earth) or radius_earth <= 0:
        return np.nan
    if radius_earth < 1.23:
        return float(0.9718 * (radius_earth ** 3.58))
    return float(2.69 * (radius_earth ** 0.93))


def calculate_tsm(
    radius_earth: float,
    mass_earth: Optional[float],
    teq_k: float,
    r_star_solar: float,
    j_mag: Optional[float],
    k_mag: Optional[float] = None
) -> float:
    """
    Calculate Kempton et al. (2018) Transmission Spectroscopy Metric (TSM).

    Formula:
        TSM = C * (R_p^3 * T_eq) / (M_p * R_*^2) * 10^(-m_J / 5)

    Scale factor C (Table 1 of Kempton et al. 2018):
        - R_p < 1.5 R_earth: C = 0.190
        - 1.5 <= R_p < 2.75 R_earth: C = 1.26
        - 2.75 <= R_p < 4.0 R_earth: C = 1.28
        - 4.0 <= R_p < 10.0 R_earth: C = 1.15
        - R_p >= 10.0 R_earth: C = 1.15 (extrapolated)
    """
    if pd.isna(radius_earth) or radius_earth <= 0:
        return np.nan
    if pd.isna(teq_k) or teq_k <= 0:
        return np.nan
    if pd.isna(r_star_solar) or r_star_solar <= 0:
        return np.nan

    # Fallback for mass if missing
    if pd.isna(mass_earth) or mass_earth <= 0:
        mass_earth = estimate_planet_mass(radius_earth)
    if pd.isna(mass_earth) or mass_earth <= 0:
        return np.nan

    # Magnitude resolution: J-band preferred, fallback to K-band + 0.8 mag (standard dwarf offset)
    apparent_mag = j_mag
    if pd.isna(apparent_mag):
        if pd.notna(k_mag):
            apparent_mag = k_mag + 0.8
        else:
            return np.nan

    # Determine scale factor C
    if radius_earth < 1.5:
        c = 0.190
    elif radius_earth < 2.75:
        c = 1.26
    elif radius_earth < 4.0:
        c = 1.28
    else:
        c = 1.15

    tsm = c * ((radius_earth ** 3) * teq_k) / (mass_earth * (r_star_solar ** 2)) * (10.0 ** (-apparent_mag / 5.0))
    return float(tsm) if np.isfinite(tsm) and tsm >= 0 else np.nan


def calculate_esm(
    radius_earth: float,
    teq_k: float,
    t_star_k: float,
    r_star_solar: float,
    k_mag: Optional[float]
) -> float:
    """
    Calculate Kempton et al. (2018) Emission Spectroscopy Metric (ESM).

    Formula:
        ESM = 4.29e6 * (B_7.5(T_day) / B_7.5(T_*)) * (R_p / R_*)^2 * 10^(-m_K / 5)
    where T_day = 1.10 * T_eq, and B_7.5(T) is approximated via Planck's law at lambda = 7.5 um.
    """
    if pd.isna(radius_earth) or radius_earth <= 0:
        return np.nan
    if pd.isna(teq_k) or teq_k <= 0:
        return np.nan
    if pd.isna(t_star_k) or t_star_k <= 0:
        return np.nan
    if pd.isna(r_star_solar) or r_star_solar <= 0:
        return np.nan
    if pd.isna(k_mag):
        return np.nan

    t_day = 1.10 * teq_k

    # Planck blackbody function B(lambda, T) at lambda = 7.5 microns (1918.7 K / T)
    hc_lambda_k = 1920.0
    exp_day = min(500.0, hc_lambda_k / max(1.0, t_day))
    exp_star = min(500.0, hc_lambda_k / max(1.0, t_star_k))

    try:
        flux_day = 1.0 / (np.exp(exp_day) - 1.0)
        flux_star = 1.0 / (np.exp(exp_star) - 1.0)
    except OverflowError:
        return np.nan

    if flux_star <= 0 or flux_day <= 0:
        return np.nan

    # Earth radius to Solar radius ratio: ~0.009168
    rp_rs_ratio = (radius_earth * 0.009168) / r_star_solar

    esm = 4.29e6 * (flux_day / flux_star) * (rp_rs_ratio ** 2) * (10.0 ** (-k_mag / 5.0))
    return float(esm) if np.isfinite(esm) and esm >= 0 else np.nan


def generate_ground_truth_labels(
    df: pd.DataFrame,
    reference_path: Optional[str] = None
) -> pd.DataFrame:
    """
    Generate ground-truth relevance labels for exoplanet spectroscopic follow-up targets.

    Labels are strictly JWST-membership-based:
    - is_jwst_target: Boolean flag indicating verified JWST transmission target
    - ground_truth_binary: Binary label (1 if in a verified JWST transmission program, 0 otherwise)
    - ground_truth_graded: Relevance grade (3 for verified JWST program targets, 0 otherwise)

    TSM and ESM are computed and preserved as separate columns for use ONLY as baselines,
    NEVER in the ground truth label.
    """
    df = df.copy()
    verified_jwst_targets = get_verified_jwst_targets(reference_path)

    # Vectorized / row-wise computation of TSM and ESM
    tsm_values = []
    esm_values = []
    is_jwst = []

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

        tsm_values.append(tsm)
        esm_values.append(esm)
        is_jwst.append(jwst_confirmed)

    df["tsm"] = tsm_values
    df["esm"] = esm_values
    df["is_jwst_target"] = is_jwst

    # Labels are strictly JWST-membership-based (TSM is never used in the label)
    df["ground_truth_binary"] = [1 if j else 0 for j in is_jwst]
    df["ground_truth_graded"] = [3 if j else 0 for j in is_jwst]

    return df

