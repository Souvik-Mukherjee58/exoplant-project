"""Science unit tests verifying published astrophysical formulas and physical boundaries.

Covers:
1. TSM scale-factor boundaries per Kempton et al. 2018 Table 1.
2. Chen & Kipping (2017) mass-radius empirical regime boundaries.
3. TSM NaN handling when any required astronomical input is missing.
4. Non-transiting planets are strictly never eligible for transmission spectroscopy.
"""

import numpy as np
import pandas as pd

from app.ml.ground_truth import (
    calculate_tsm,
    calculate_tsm_vectorized,
    estimate_planet_mass,
    estimate_planet_mass_vectorized,
    get_kempton_size_class_and_threshold,
    get_kempton_size_class_and_threshold_vectorized,
)
from app.services.data_cleaning import DataCleaning

# ---------------------------------------------------------------------------
# 1. TSM Scale-Factor Boundaries (Kempton et al. 2018 Table 1)
# ---------------------------------------------------------------------------


class TestTSMScaleFactors:
    """
    Kempton et al. (2018) Table 1 scale factors:
    - Terrestrial (Rp < 1.5): C = 0.190, threshold = 10.0
    - Small Sub-Neptune (1.5 <= Rp < 2.75): C = 1.26, threshold = 90.0
    - Large Sub-Neptune (2.75 <= Rp < 4.0): C = 1.28, threshold = 96.0
    - Sub-Jovian / Gas Giant (Rp >= 4.0): C = 1.15, threshold = 84.0
    """

    def _expected_tsm(self, c: float, r: float, m: float, teq: float, r_star: float, jmag: float) -> float:
        return c * ((r**3) * teq) / (m * (r_star**2)) * (10.0 ** (-jmag / 5.0))

    def test_kempton_scale_factor_terrestrial_boundary(self):
        """Rp = 1.499 uses C = 0.190, Rp = 1.500 uses C = 1.26."""
        m, teq, r_star, jmag = 3.0, 300.0, 1.0, 10.0

        # Just below boundary: C = 0.190
        tsm_below = calculate_tsm(1.499, m, teq, r_star, jmag)
        expected_below = self._expected_tsm(0.190, 1.499, m, teq, r_star, jmag)
        assert np.isclose(tsm_below, expected_below, rtol=1e-5)

        # At boundary: C = 1.26
        tsm_at = calculate_tsm(1.500, m, teq, r_star, jmag)
        expected_at = self._expected_tsm(1.26, 1.500, m, teq, r_star, jmag)
        assert np.isclose(tsm_at, expected_at, rtol=1e-5)

        # Size classes and thresholds
        cls_below, thresh_below = get_kempton_size_class_and_threshold(1.499)
        assert cls_below == "Terrestrial"
        assert thresh_below == 10.0

        cls_at, thresh_at = get_kempton_size_class_and_threshold(1.500)
        assert cls_at == "Small Sub-Neptune"
        assert thresh_at == 90.0

    def test_kempton_scale_factor_small_sub_neptune_boundary(self):
        """Rp = 2.749 uses C = 1.26, Rp = 2.750 uses C = 1.28."""
        m, teq, r_star, jmag = 8.0, 500.0, 1.0, 10.0

        tsm_below = calculate_tsm(2.749, m, teq, r_star, jmag)
        expected_below = self._expected_tsm(1.26, 2.749, m, teq, r_star, jmag)
        assert np.isclose(tsm_below, expected_below, rtol=1e-5)

        tsm_at = calculate_tsm(2.750, m, teq, r_star, jmag)
        expected_at = self._expected_tsm(1.28, 2.750, m, teq, r_star, jmag)
        assert np.isclose(tsm_at, expected_at, rtol=1e-5)

        cls_below, thresh_below = get_kempton_size_class_and_threshold(2.749)
        assert cls_below == "Small Sub-Neptune"
        assert thresh_below == 90.0

        cls_at, thresh_at = get_kempton_size_class_and_threshold(2.750)
        assert cls_at == "Large Sub-Neptune"
        assert thresh_at == 96.0

    def test_kempton_scale_factor_large_sub_neptune_boundary(self):
        """Rp = 3.999 uses C = 1.28, Rp = 4.000 uses C = 1.15."""
        m, teq, r_star, jmag = 15.0, 800.0, 1.0, 10.0

        tsm_below = calculate_tsm(3.999, m, teq, r_star, jmag)
        expected_below = self._expected_tsm(1.28, 3.999, m, teq, r_star, jmag)
        assert np.isclose(tsm_below, expected_below, rtol=1e-5)

        tsm_at = calculate_tsm(4.000, m, teq, r_star, jmag)
        expected_at = self._expected_tsm(1.15, 4.000, m, teq, r_star, jmag)
        assert np.isclose(tsm_at, expected_at, rtol=1e-5)

        cls_below, thresh_below = get_kempton_size_class_and_threshold(3.999)
        assert cls_below == "Large Sub-Neptune"
        assert thresh_below == 96.0

        cls_at, thresh_at = get_kempton_size_class_and_threshold(4.000)
        assert cls_at == "Sub-Jovian / Gas Giant"
        assert thresh_at == 84.0

    def test_vectorized_kempton_boundaries(self):
        """Verify vectorized calculate_tsm_vectorized adheres to all boundaries."""
        radii = np.array([1.499, 1.500, 2.749, 2.750, 3.999, 4.000, 11.2])
        masses = np.array([1.0, 3.0, 7.0, 8.0, 14.0, 16.0, 300.0])
        teqs = np.full_like(radii, 400.0)
        r_stars = np.full_like(radii, 1.0)
        jmags = np.full_like(radii, 10.0)

        tsms = calculate_tsm_vectorized(radii, masses, teqs, r_stars, jmags)
        classes, thresholds = get_kempton_size_class_and_threshold_vectorized(radii)

        assert classes[0] == "Terrestrial"
        assert classes[1] == "Small Sub-Neptune"
        assert classes[2] == "Small Sub-Neptune"
        assert classes[3] == "Large Sub-Neptune"
        assert classes[4] == "Large Sub-Neptune"
        assert classes[5] == "Sub-Jovian / Gas Giant"
        assert classes[6] == "Sub-Jovian / Gas Giant"

        assert np.all(thresholds == np.array([10.0, 90.0, 90.0, 96.0, 96.0, 84.0, 84.0]))
        assert np.all(np.isfinite(tsms))


# ---------------------------------------------------------------------------
# 2. Chen & Kipping (2017) Empirical Mass-Radius Regimes
# ---------------------------------------------------------------------------


class TestChenKippingRegimes:
    """
    Chen & Kipping (2017) mass-radius relations:
    - Terran regime (< 1.23 R_earth): M = 0.9718 * R^3.58
    - Neptunian regime (>= 1.23 R_earth): M = 2.69 * R^0.93
    """

    def test_chen_kipping_terran_regime(self):
        # Earth: R = 1.0 R_earth -> M = 0.9718 * 1^3.58 = 0.9718 M_earth
        m_earth = estimate_planet_mass(1.0)
        assert np.isclose(m_earth, 0.9718, rtol=1e-5)

        # Mars-sized: R = 0.53 R_earth
        m_sub = estimate_planet_mass(0.53)
        expected_sub = 0.9718 * (0.53**3.58)
        assert np.isclose(m_sub, expected_sub, rtol=1e-5)

    def test_chen_kipping_boundary_step(self):
        """Sharp boundary at R = 1.23 R_earth."""
        # Just below boundary (1.229 R_earth): Terran equation
        m_below = estimate_planet_mass(1.229)
        expected_below = 0.9718 * (1.229**3.58)
        assert np.isclose(m_below, expected_below, rtol=1e-5)

        # At boundary (1.230 R_earth): Neptunian equation
        m_at = estimate_planet_mass(1.230)
        expected_at = 2.69 * (1.230**0.93)
        assert np.isclose(m_at, expected_at, rtol=1e-5)

    def test_chen_kipping_vectorized_matches_scalar(self):
        radii = np.array([0.5, 0.9, 1.0, 1.229, 1.23, 1.5, 2.4, 4.0, -1.0, np.nan])
        v_masses = estimate_planet_mass_vectorized(radii)

        for r, vm in zip(radii, v_masses):
            sm = estimate_planet_mass(r if np.isfinite(r) else None)
            if np.isnan(sm):
                assert np.isnan(vm)
            else:
                assert np.isclose(vm, sm, rtol=1e-6)


# ---------------------------------------------------------------------------
# 3. Missing Inputs Yield NaN TSM
# ---------------------------------------------------------------------------


class TestTSMMissingInputs:
    """TSM is strictly NaN when any required astronomical input is missing."""

    def test_missing_radius_yields_nan(self):
        assert np.isnan(calculate_tsm(None, 1.0, 300.0, 1.0, 10.0))
        assert np.isnan(calculate_tsm(np.nan, 1.0, 300.0, 1.0, 10.0))
        assert np.isnan(calculate_tsm(0.0, 1.0, 300.0, 1.0, 10.0))
        assert np.isnan(calculate_tsm(-1.5, 1.0, 300.0, 1.0, 10.0))

    def test_missing_teq_yields_nan(self):
        assert np.isnan(calculate_tsm(1.0, 1.0, None, 1.0, 10.0))
        assert np.isnan(calculate_tsm(1.0, 1.0, np.nan, 1.0, 10.0))
        assert np.isnan(calculate_tsm(1.0, 1.0, 0.0, 1.0, 10.0))
        assert np.isnan(calculate_tsm(1.0, 1.0, -100.0, 1.0, 10.0))

    def test_missing_stellar_radius_yields_nan(self):
        assert np.isnan(calculate_tsm(1.0, 1.0, 300.0, None, 10.0))
        assert np.isnan(calculate_tsm(1.0, 1.0, 300.0, np.nan, 10.0))
        assert np.isnan(calculate_tsm(1.0, 1.0, 300.0, 0.0, 10.0))
        assert np.isnan(calculate_tsm(1.0, 1.0, 300.0, -0.5, 10.0))

    def test_missing_both_magnitudes_yields_nan(self):
        # Missing both J-band and K-band
        assert np.isnan(calculate_tsm(1.0, 1.0, 300.0, 1.0, None, None))
        assert np.isnan(calculate_tsm(1.0, 1.0, 300.0, 1.0, np.nan, np.nan))

    def test_fallback_k_mag_when_j_missing(self):
        # When J-mag is missing but K-mag is provided, TSM is computed using K + 0.8
        tsm_k = calculate_tsm(1.0, 1.0, 300.0, 1.0, None, k_mag=9.2)
        assert np.isfinite(tsm_k)
        # Same as if J = 10.0
        tsm_j = calculate_tsm(1.0, 1.0, 300.0, 1.0, j_mag=10.0)
        assert np.isclose(tsm_k, tsm_j, rtol=1e-5)


# ---------------------------------------------------------------------------
# 4. Non-Transiting Planets are Strictly Never Eligible
# ---------------------------------------------------------------------------


class TestNonTransitingEligibility:
    """Non-transiting planets (tran_flag == 0 or is_transiting == False) are never eligible."""

    def test_non_transiting_planet_is_never_eligible(self):
        cleaner = DataCleaning()

        # Planet with perfect observation parameters but is_transiting = False
        df = pd.DataFrame(
            [
                {
                    "planet_name": "NonTransiting-1 b",
                    "is_transiting": False,
                    "tran_flag": 0,
                    "planet_radius": 1.0,
                    "planet_mass": 1.0,
                    "equilibrium_temperature": 288.0,
                    "stellar_radius": 1.0,
                    "j_magnitude": 8.0,
                    "k_magnitude": 7.5,
                    "orbital_period": 10.0,
                    "distance": 10.0,
                }
            ]
        )

        cleaned = cleaner.clean(df)
        assert cleaned["is_transiting"].iloc[0] == False
        assert cleaned["eligible_for_transmission"].iloc[0] == False
        assert "Non-transiting" in cleaned["exclusion_reason"].iloc[0]

    def test_tran_flag_zero_forces_ineligible_even_with_perfect_data(self):
        cleaner = DataCleaning()

        # Dataset with mixed transiting and non-transiting
        df = pd.DataFrame(
            [
                {
                    "planet_name": "Transiting Planet",
                    "tran_flag": 1,
                    "planet_radius": 1.2,
                    "equilibrium_temperature": 310.0,
                    "stellar_radius": 0.8,
                    "j_magnitude": 9.5,
                },
                {
                    "planet_name": "Non-Transiting Radial Velocity Planet",
                    "tran_flag": 0,
                    "planet_radius": 1.2,
                    "equilibrium_temperature": 310.0,
                    "stellar_radius": 0.8,
                    "j_magnitude": 9.5,
                },
            ]
        )

        cleaned = cleaner.clean(df)

        p_trans = cleaned[cleaned["planet_name"] == "Transiting Planet"].iloc[0]
        p_non = cleaned[cleaned["planet_name"] == "Non-Transiting Radial Velocity Planet"].iloc[0]

        assert p_trans["is_transiting"] == True
        assert p_trans["eligible_for_transmission"] == True
        assert p_trans["exclusion_reason"] == ""

        assert p_non["is_transiting"] == False
        assert p_non["eligible_for_transmission"] == False
        assert "Non-transiting" in p_non["exclusion_reason"]
