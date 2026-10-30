"""Ground-truth formulation for exoplanet spectroscopic follow-up targets.

Implements published astronomical ground truth:
1. Transmission Spectroscopy Metric (TSM) - Kempton et al. (2018), PASP 130:114401.
2. Emission Spectroscopy Metric (ESM) - Kempton et al. (2018).
3. NASA / STScI Approved JWST Cycle 1, 2, and 3 Atmospheric Characterization Programs.
4. Empirical Mass-Radius relations (Chen & Kipping 2017) for missing masses.
"""

from pathlib import Path
from typing import Any, Optional, Set, Tuple

import numpy as np
import pandas as pd

from app.config import settings


def load_jwst_transmission_targets(reference_path: Optional[str | Path] = None) -> pd.DataFrame:
    """Load JWST transmission targets reference catalog using application settings."""
    if reference_path:
        csv_path = Path(reference_path)
    else:
        csv_path = settings.get_jwst_targets_path()

    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame(columns=["planet_name", "program_id", "cycle", "mode", "source_url"])


_WARNED_UNVERIFIED: bool = False


def print_unverified_targets_warning(unverified_df: pd.DataFrame) -> None:
    """Print warning listing unverified rows in jwst_transmission_targets.csv."""
    global _WARNED_UNVERIFIED
    if _WARNED_UNVERIFIED:
        return
    _WARNED_UNVERIFIED = True

    width = 80
    border = "#" * width
    lines = [
        "",
        border,
        " [LOUD WARNING] UNVERIFIED JWST REFERENCE TARGETS DETECTED ".center(width, "#"),
        border,
        f" The reference catalog contains {len(unverified_df)} unverified or non-transmission rows.",
        " Labels use ONLY rows with: verified == True AND observation_type == 'transmission'.",
        " Until reviewed and marked verified=True, these targets are excluded from labels.",
        "",
        " Unverified / Pending Review Rows:",
    ]
    pnames = unverified_df.get("planet_name", pd.Series(["Unknown"] * len(unverified_df))).astype(str)
    raw_pids = unverified_df.get("program_id", pd.Series(["N/A"] * len(unverified_df)))
    obs_types = unverified_df.get("observation_type", pd.Series(["unknown"] * len(unverified_df))).astype(str)
    verified_vals = unverified_df.get("verified", pd.Series([False] * len(unverified_df))).astype(str)

    for pname, raw_pid, obs, ver in zip(pnames, raw_pids, obs_types, verified_vals):
        if pd.isna(raw_pid) or str(raw_pid).strip() == "" or str(raw_pid).lower() == "nan":
            pid = "N/A"
        else:
            pid = str(int(float(raw_pid))) if str(raw_pid).replace(".", "", 1).isdigit() else str(raw_pid).strip()
        lines.append(f"   * {pname:<16} | Program: {pid:<6} | Type: {obs:<14} | Verified: {ver}")
    lines.extend(
        [
            "",
            " Action Required: Review reports/jwst_reference_verification.csv and set",
            " verified=True in backend/data/reference/jwst_transmission_targets.csv",
            border,
            "",
        ]
    )
    print("\n".join(lines))


def get_verified_jwst_targets(reference_path: Optional[str | Path] = None) -> Set[str]:
    """
    Get set of verified JWST transmission targets.
    Excludes non-transiting planets and unverified entries with empty program_id (marked with TODO).
    """
    df = load_jwst_transmission_targets(reference_path)
    if df.empty or "planet_name" not in df.columns:
        return set()

    def _parse_bool(val: Any) -> bool:
        if pd.isna(val):
            return False
        if isinstance(val, bool):
            return val
        s = str(val).strip().lower()
        return s in ("true", "1", "yes", "t")

    has_verified = "verified" in df.columns
    has_obs_type = "observation_type" in df.columns

    if has_verified and has_obs_type:
        is_verified = df["verified"].apply(_parse_bool)
        is_transmission = df["observation_type"].astype(str).str.strip().str.lower() == "transmission"
        verified_mask = is_verified & is_transmission

        unverified_df = df[~verified_mask]
        if len(unverified_df) > 0:
            print_unverified_targets_warning(unverified_df)

        verified_planets = df[verified_mask]["planet_name"].astype(str).str.strip().tolist()
        return set(verified_planets)

    # Standard reference catalog: filter rows with non-empty program_id
    verified = df[df["program_id"].notna() & (df["program_id"].astype(str).str.strip() != "")]
    return set(verified["planet_name"].astype(str).str.strip())


# Backward-compatible reference to verified JWST targets loaded from reference CSV
CONFIRMED_JWST_ATMOSPHERIC_TARGETS: Set[str] = get_verified_jwst_targets()


def estimate_planet_mass(radius_earth: Optional[float]) -> float:
    """
    Estimate planet mass from radius using Chen & Kipping (2017) empirical relations.
    Used when empirical RV or TTV mass measurement is missing in astronomical catalogs.

    - Terran regime (< 1.23 R_earth): M = 0.9718 * R^3.58
    - Neptunian regime (1.23 - 14.26 R_earth): M = 2.69 * R^0.93
    """
    if radius_earth is None or pd.isna(radius_earth) or radius_earth <= 0:
        return float(np.nan)
    r = float(radius_earth)
    if r < 1.23:
        return float(0.9718 * (r**3.58))
    return float(2.69 * (r**0.93))


def estimate_planet_mass_vectorized(radius: np.ndarray | pd.Series) -> np.ndarray:
    """Vectorized Chen & Kipping (2017) empirical mass estimation."""
    r = np.asarray(radius, dtype=float)
    result = np.full(r.shape, np.nan, dtype=float)
    valid = np.isfinite(r) & (r > 0)
    terran = valid & (r < 1.23)
    neptunian = valid & ~terran

    result[terran] = 0.9718 * (r[terran] ** 3.58)
    result[neptunian] = 2.69 * (r[neptunian] ** 0.93)
    return result


def calculate_tsm(
    radius_earth: Optional[float],
    mass_earth: Optional[float],
    teq_k: Optional[float],
    r_star_solar: Optional[float],
    j_mag: Optional[float],
    k_mag: Optional[float] = None,
) -> float:
    """
    Calculate Kempton et al. (2018) Transmission Spectroscopy Metric (TSM).

    Formula:
        TSM = C * (R_p^3 * T_eq) / (M_p * R_*^2) * 10^(-m_J / 5)

    Scale factor C (Table 1 of Kempton et al. 2018):
        - R_p < 1.5 R_earth: C = 0.190
        - 1.5 <= R_p < 2.75 R_earth: C = 1.26
        - 2.75 <= R_p < 4.0 R_earth: C = 1.28
        - R_p >= 4.0 R_earth: C = 1.15 (extrapolated)
    """
    if radius_earth is None or pd.isna(radius_earth) or radius_earth <= 0:
        return float(np.nan)
    if teq_k is None or pd.isna(teq_k) or teq_k <= 0:
        return float(np.nan)
    if r_star_solar is None or pd.isna(r_star_solar) or r_star_solar <= 0:
        return float(np.nan)

    r = float(radius_earth)
    teq = float(teq_k)
    r_star = float(r_star_solar)

    # Fallback for mass if missing
    effective_mass = mass_earth
    if effective_mass is None or pd.isna(effective_mass) or effective_mass <= 0:
        effective_mass = estimate_planet_mass(r)
    if effective_mass is None or pd.isna(effective_mass) or effective_mass <= 0:
        return float(np.nan)

    # Magnitude resolution: J-band preferred, fallback to K-band + 0.8 mag (standard dwarf offset)
    apparent_mag = j_mag
    if apparent_mag is None or pd.isna(apparent_mag):
        if k_mag is not None and pd.notna(k_mag):
            apparent_mag = float(k_mag) + 0.8
        else:
            return float(np.nan)

    # Determine scale factor C
    if r < 1.5:
        c = 0.190
    elif r < 2.75:
        c = 1.26
    elif r < 4.0:
        c = 1.28
    else:
        c = 1.15

    tsm = c * ((r**3) * teq) / (effective_mass * (r_star**2)) * (10.0 ** (-apparent_mag / 5.0))
    return float(tsm) if np.isfinite(tsm) and tsm >= 0 else float(np.nan)


def calculate_tsm_vectorized(
    radius_earth: np.ndarray | pd.Series,
    mass_earth: np.ndarray | pd.Series,
    teq_k: np.ndarray | pd.Series,
    r_star_solar: np.ndarray | pd.Series,
    j_mag: np.ndarray | pd.Series,
    k_mag: Optional[np.ndarray | pd.Series] = None,
) -> np.ndarray:
    """Vectorized calculation of Transmission Spectroscopy Metric (TSM)."""
    r = np.asarray(radius_earth, dtype=float)
    m = np.asarray(mass_earth, dtype=float)
    teq = np.asarray(teq_k, dtype=float)
    r_star = np.asarray(r_star_solar, dtype=float)
    j = np.asarray(j_mag, dtype=float)
    k = np.asarray(k_mag, dtype=float) if k_mag is not None else np.full_like(r, np.nan)

    est_m = estimate_planet_mass_vectorized(r)
    effective_m = np.where(np.isfinite(m) & (m > 0), m, est_m)

    apparent_mag = np.where(np.isfinite(j), j, np.where(np.isfinite(k), k + 0.8, np.nan))

    c = np.select([r < 1.5, r < 2.75, r < 4.0], [0.190, 1.26, 1.28], default=1.15)

    valid = (
        np.isfinite(r)
        & (r > 0)
        & np.isfinite(teq)
        & (teq > 0)
        & np.isfinite(r_star)
        & (r_star > 0)
        & np.isfinite(effective_m)
        & (effective_m > 0)
        & np.isfinite(apparent_mag)
    )

    result = np.full_like(r, np.nan, dtype=float)
    with np.errstate(all="ignore"):
        tsm = (
            c[valid]
            * ((r[valid] ** 3) * teq[valid])
            / (effective_m[valid] * (r_star[valid] ** 2))
            * (10.0 ** (-apparent_mag[valid] / 5.0))
        )
        finite_mask = np.isfinite(tsm) & (tsm >= 0)
        valid_indices = np.where(valid)[0]
        result[valid_indices[finite_mask]] = tsm[finite_mask]

    return result


def calculate_esm(
    radius_earth: Optional[float],
    teq_k: Optional[float],
    t_star_k: Optional[float],
    r_star_solar: Optional[float],
    k_mag: Optional[float],
) -> float:
    """
    Calculate Kempton et al. (2018) Emission Spectroscopy Metric (ESM).

    Formula:
        ESM = 4.29e6 * (B_7.5(T_day) / B_7.5(T_*)) * (R_p / R_*)^2 * 10^(-m_K / 5)
    where T_day = 1.10 * T_eq, and B_7.5(T) is approximated via Planck's law at lambda = 7.5 um.
    """
    if radius_earth is None or pd.isna(radius_earth) or radius_earth <= 0:
        return float(np.nan)
    if teq_k is None or pd.isna(teq_k) or teq_k <= 0:
        return float(np.nan)
    if t_star_k is None or pd.isna(t_star_k) or t_star_k <= 0:
        return float(np.nan)
    if r_star_solar is None or pd.isna(r_star_solar) or r_star_solar <= 0:
        return float(np.nan)
    if k_mag is None or pd.isna(k_mag):
        return float(np.nan)

    r = float(radius_earth)
    teq = float(teq_k)
    t_star = float(t_star_k)
    r_star = float(r_star_solar)
    km = float(k_mag)

    t_day = 1.10 * teq

    # Planck blackbody function B(lambda, T) at lambda = 7.5 microns (1920 K / T)
    hc_lambda_k = 1920.0
    exp_day = min(500.0, hc_lambda_k / max(1.0, t_day))
    exp_star = min(500.0, hc_lambda_k / max(1.0, t_star))

    try:
        flux_day = 1.0 / (np.exp(exp_day) - 1.0)
        flux_star = 1.0 / (np.exp(exp_star) - 1.0)
    except OverflowError:
        return float(np.nan)

    if flux_star <= 0 or flux_day <= 0:
        return float(np.nan)

    # Earth radius to Solar radius ratio: ~0.009168
    rp_rs_ratio = (r * 0.009168) / r_star

    esm = 4.29e6 * (flux_day / flux_star) * (rp_rs_ratio**2) * (10.0 ** (-km / 5.0))
    return float(esm) if np.isfinite(esm) and esm >= 0 else float(np.nan)


def calculate_esm_vectorized(
    radius_earth: np.ndarray | pd.Series,
    teq_k: np.ndarray | pd.Series,
    t_star_k: np.ndarray | pd.Series,
    r_star_solar: np.ndarray | pd.Series,
    k_mag: np.ndarray | pd.Series,
) -> np.ndarray:
    """Vectorized calculation of Emission Spectroscopy Metric (ESM)."""
    r = np.asarray(radius_earth, dtype=float)
    teq = np.asarray(teq_k, dtype=float)
    t_star = np.asarray(t_star_k, dtype=float)
    r_star = np.asarray(r_star_solar, dtype=float)
    k = np.asarray(k_mag, dtype=float)

    valid = (
        np.isfinite(r)
        & (r > 0)
        & np.isfinite(teq)
        & (teq > 0)
        & np.isfinite(t_star)
        & (t_star > 0)
        & np.isfinite(r_star)
        & (r_star > 0)
        & np.isfinite(k)
    )

    result = np.full_like(r, np.nan, dtype=float)
    t_day = 1.10 * teq
    hc_lambda = 1920.0

    with np.errstate(all="ignore"):
        exp_day = np.clip(hc_lambda / np.maximum(1.0, t_day), None, 500.0)
        exp_star = np.clip(hc_lambda / np.maximum(1.0, t_star), None, 500.0)
        flux_day = 1.0 / (np.exp(exp_day) - 1.0)
        flux_star = 1.0 / (np.exp(exp_star) - 1.0)
        flux_ok = (flux_star > 0) & (flux_day > 0) & valid

        rp_rs_ratio = (r * 0.009168) / r_star
        esm = 4.29e6 * (flux_day / flux_star) * (rp_rs_ratio**2) * (10.0 ** (-k / 5.0))
        finite_esm = np.isfinite(esm) & (esm >= 0) & flux_ok
        result[finite_esm] = esm[finite_esm]

    return result


def get_kempton_size_class_and_threshold(radius_earth: Optional[float]) -> Tuple[str, float]:
    """
    Categorize exoplanet into Kempton et al. (2018) Table 1 size regime and recommended TSM threshold:
    - Terrestrial: Rp < 1.5 R_earth (TSM threshold = 10.0)
    - Small Sub-Neptune: 1.5 <= Rp < 2.75 R_earth (TSM threshold = 90.0)
    - Large Sub-Neptune: 2.75 <= Rp < 4.0 R_earth (TSM threshold = 96.0)
    - Sub-Jovian / Gas Giant: Rp >= 4.0 R_earth (TSM threshold = 84.0)
    """
    if radius_earth is None or pd.isna(radius_earth) or radius_earth <= 0:
        return "Unknown", 10.0
    r = float(radius_earth)
    if r < 1.5:
        return "Terrestrial", 10.0
    elif r < 2.75:
        return "Small Sub-Neptune", 90.0
    elif r < 4.0:
        return "Large Sub-Neptune", 96.0
    else:
        return "Sub-Jovian / Gas Giant", 84.0


def get_kempton_size_class_and_threshold_vectorized(
    radius_earth: np.ndarray | pd.Series,
) -> Tuple[np.ndarray, np.ndarray]:
    """Vectorized Kempton et al. (2018) size regime categorization and threshold assignment."""
    r = np.asarray(radius_earth, dtype=float)
    valid = np.isfinite(r) & (r > 0)

    conds = [
        valid & (r < 1.5),
        valid & (r < 2.75),
        valid & (r < 4.0),
        valid & (r >= 4.0),
    ]
    classes = ["Terrestrial", "Small Sub-Neptune", "Large Sub-Neptune", "Sub-Jovian / Gas Giant"]
    thresholds = [10.0, 90.0, 96.0, 84.0]

    size_classes = np.select(conds, classes, default="Unknown")
    tsm_thresholds = np.select(conds, thresholds, default=10.0)
    return size_classes, tsm_thresholds


def generate_ground_truth_labels(df: pd.DataFrame, reference_path: Optional[str | Path] = None) -> pd.DataFrame:
    """
    Generate ground-truth relevance labels for exoplanet spectroscopic follow-up targets.

    Labels are strictly JWST-membership-based:
    - already_observed_jwst: Boolean flag indicating verified approved JWST transmission program
    - is_jwst_target: Boolean flag (synonymous with already_observed_jwst)
    - ground_truth_binary: Binary label (1 if in a verified JWST transmission program, 0 otherwise)
    - ground_truth_graded: Relevance grade (3 for verified JWST program targets, 0 otherwise)
    - kempton_size_class: Kempton et al. (2018) physical regime
    - tsm_threshold: Recommended Kempton et al. (2018) threshold for target selection

    All metrics are computed using vectorized numpy/pandas operations.
    """
    df = df.copy()
    verified_jwst_targets = get_verified_jwst_targets(reference_path)

    r = pd.to_numeric(df.get("planet_radius", pd.Series(np.nan, index=df.index)), errors="coerce")
    m = pd.to_numeric(df.get("planet_mass", pd.Series(np.nan, index=df.index)), errors="coerce")
    teq = pd.to_numeric(df.get("equilibrium_temperature", pd.Series(np.nan, index=df.index)), errors="coerce")
    r_star = pd.to_numeric(df.get("stellar_radius", pd.Series(np.nan, index=df.index)), errors="coerce")
    t_star = pd.to_numeric(df.get("stellar_effective_temperature", pd.Series(np.nan, index=df.index)), errors="coerce")
    jmag = pd.to_numeric(df.get("j_magnitude", pd.Series(np.nan, index=df.index)), errors="coerce")
    kmag = pd.to_numeric(df.get("k_magnitude", pd.Series(np.nan, index=df.index)), errors="coerce")

    p_names = (
        df["planet_name"].fillna("").astype(str).str.strip()
        if "planet_name" in df.columns
        else pd.Series("", index=df.index)
    )
    is_jwst = p_names.isin(verified_jwst_targets).to_numpy()

    # Vectorized calculations
    tsm_values = calculate_tsm_vectorized(r, m, teq, r_star, jmag, kmag)
    esm_values = calculate_esm_vectorized(r, teq, t_star, r_star, kmag)
    size_classes, tsm_thresholds = get_kempton_size_class_and_threshold_vectorized(r)

    df["tsm"] = tsm_values
    df["esm"] = esm_values
    df["is_jwst_target"] = is_jwst
    df["already_observed_jwst"] = is_jwst
    df["kempton_size_class"] = size_classes
    df["tsm_threshold"] = tsm_thresholds

    # Labels are strictly JWST-membership-based (TSM is never used in the label)
    df["ground_truth_binary"] = np.where(is_jwst, 1, 0)
    df["ground_truth_graded"] = np.where(is_jwst, 3, 0)

    return df
