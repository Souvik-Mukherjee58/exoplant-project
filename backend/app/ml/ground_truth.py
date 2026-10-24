"""Ground-truth formulation for exoplanet spectroscopic follow-up targets.

Implements published astronomical ground truth:
1. Transmission Spectroscopy Metric (TSM) - Kempton et al. (2018), PASP 130:114401.
2. Emission Spectroscopy Metric (ESM) - Kempton et al. (2018).
3. NASA / STScI Approved JWST Cycle 1, 2, and 3 Atmospheric Characterization Programs.
4. Empirical Mass-Radius relations (Chen & Kipping 2017) for missing masses.
"""

from typing import Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd


# Ground-truth confirmed targets in approved JWST Atmospheric Characterization Programs
# (Cycles 1, 2, and 3: ERS, GTO, and GO programs)
CONFIRMED_JWST_ATMOSPHERIC_TARGETS: Set[str] = {
    # High-profile terrestrial & temperate M-dwarf systems
    "TRAPPIST-1 b", "TRAPPIST-1 c", "TRAPPIST-1 d", "TRAPPIST-1 e",
    "TRAPPIST-1 f", "TRAPPIST-1 g", "TRAPPIST-1 h",
    "LHS 1140 b", "TOI-700 d", "L 98-59 b", "L 98-59 c", "L 98-59 d",
    "GJ 1132 b", "GJ 1214 b", "GJ 436 b", "GJ 3470 b", "GJ 367 b",
    "LP 791-18 d", "TOI-270 d", "K2-18 b", "55 Cnc e",
    "Proxima Cen b", "Wolf 1061 c", "GJ 273 b", "Gl 725 B c",
    # Benchmark giant/sub-Neptune spectroscopic laboratories
    "WASP-39 b", "WASP-96 b", "WASP-121 b", "WASP-76 b", "WASP-43 b",
    "WASP-18 b", "WASP-80 b", "WASP-107 b", "HD 209458 b", "HD 189733 b",
    "HAT-P-18 b", "HAT-P-26 b", "HAT-P-32 b", "TOI-849 b"
}


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


def generate_ground_truth_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate ground-truth relevance labels for exoplanet spectroscopic follow-up targets.

    Creates:
    - tsm: Continuous Kempton et al. (2018) Transmission Spectroscopy Metric
    - esm: Continuous Kempton et al. (2018) Emission Spectroscopy Metric
    - is_jwst_target: Boolean flag for targets in approved JWST atmospheric programs
    - ground_truth_binary: Binary relevance label (1 = high priority follow-up, 0 = non-target)
        * 1 if confirmed JWST program target OR
        * 1 if (TSM >= 10 for terrestrial/temperate planets R_p <= 1.8 R_earth) OR
        * 1 if (TSM >= 80 for sub-Neptunes / gas giants in high SNR regimes)
    - ground_truth_graded: Multi-level relevance grade (0-3 scale):
        * 3: Elite target (Confirmed JWST atmospheric program target OR terrestrial HZ with TSM >= 15)
        * 2: High priority candidate (TSM >= 10 for terrestrial OR TSM >= 80 for sub-Neptune)
        * 1: Marginal / secondary candidate (TSM >= 5)
        * 0: Non-target / unobservable / noisy
    """
    df = df.copy()

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
        jwst_confirmed = p_name in CONFIRMED_JWST_ATMOSPHERIC_TARGETS

        tsm_values.append(tsm)
        esm_values.append(esm)
        is_jwst.append(jwst_confirmed)

    df["tsm"] = tsm_values
    df["esm"] = esm_values
    df["is_jwst_target"] = is_jwst

    # Determine binary and graded ground truth
    binary_labels = []
    graded_labels = []

    for _, row in df.iterrows():
        jwst = row["is_jwst_target"]
        tsm = row["tsm"]
        r = row.get("planet_radius", np.nan)
        hz = str(row.get("hz_status", ""))

        is_terrestrial = pd.notna(r) and (r <= 1.8)
        is_hz = hz in ["Inside HZ", "Near HZ"]
        tsm_valid = pd.notna(tsm) and tsm > 0

        # Binary label
        is_high_priority = False
        if jwst:
            is_high_priority = True
        elif tsm_valid:
            if is_terrestrial and tsm >= 10.0:
                is_high_priority = True
            elif not is_terrestrial and tsm >= 80.0:
                is_high_priority = True

        binary_labels.append(1 if is_high_priority else 0)

        # Graded label (0 to 3)
        if jwst or (is_terrestrial and is_hz and tsm_valid and tsm >= 15.0):
            grade = 3
        elif is_high_priority:
            grade = 2
        elif tsm_valid and tsm >= 5.0:
            grade = 1
        else:
            grade = 0

        graded_labels.append(grade)

    df["ground_truth_binary"] = binary_labels
    df["ground_truth_graded"] = graded_labels

    return df
