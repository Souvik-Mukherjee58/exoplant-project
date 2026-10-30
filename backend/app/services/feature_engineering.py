"""Feature engineering service implementing published astrophysical metrics."""

import numpy as np
import pandas as pd


class FeatureEngineering:
    """
    Computes published, defensible astrophysical metrics:
    - Earth Similarity Index (ESI) via Schulze-Makuch et al. (2011)
    - Circumstellar Habitable Zone boundaries via Kopparapu et al. (2013, 2014)
    - Observational Accessibility using 2MASS infrared stellar magnitudes (J/K)
    - Data completeness score (counted exactly once)

    All transformations are fully vectorized using NumPy and Pandas.
    """

    def __init__(self) -> None:
        pass

    def add_earth_similarity(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute the published Earth Similarity Index (ESI) from Schulze-Makuch et al. (2011).

        ESI is a weighted geometric mean:
            ESI = prod_{i=1}^n (1 - |x_i - x_0| / (x_i + x_0))^(w_i / n)

        Components:
        1. Mean Radius: x0 = 1.0 R_earth, weight = 0.57
        2. Bulk Density: x0 = 1.0 rho_earth, weight = 1.07 (rho = M / R^3)
        3. Escape Velocity: x0 = 1.0 v_esc_earth, weight = 0.70 (v_esc = sqrt(M / R))
        4. Surface/Equilibrium Temperature: x0 = 288 K, weight = 5.58

        Missing parameters are excluded from the product and weights re-normalized over available terms.
        Fully vectorized implementation.
        """
        df = df.copy()

        radius = pd.to_numeric(df.get("planet_radius", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(
            dtype=float
        )
        mass = pd.to_numeric(df.get("planet_mass", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(
            dtype=float
        )
        teq = pd.to_numeric(
            df.get("equilibrium_temperature", pd.Series(np.nan, index=df.index)), errors="coerce"
        ).to_numpy(dtype=float)

        n = len(df)
        # Term 1: Mean Radius (x0 = 1.0, weight = 0.57)
        valid_r = np.isfinite(radius) & (radius > 0)
        diff_r = np.where(valid_r, np.abs(radius - 1.0) / (radius + 1.0), 1.0)
        val_r = np.clip(1.0 - diff_r, 0.0, 1.0)

        # Term 2 & 3: Bulk density & escape velocity (require both mass and radius)
        valid_mr = valid_r & np.isfinite(mass) & (mass > 0)
        with np.errstate(all="ignore"):
            density = np.where(valid_mr, mass / (radius**3), 1.0)
            diff_rho = np.where(valid_mr, np.abs(density - 1.0) / (density + 1.0), 1.0)
            val_rho = np.clip(1.0 - diff_rho, 0.0, 1.0)

            v_esc = np.where(valid_mr, np.sqrt(mass / radius), 1.0)
            diff_v = np.where(valid_mr, np.abs(v_esc - 1.0) / (v_esc + 1.0), 1.0)
            val_v = np.clip(1.0 - diff_v, 0.0, 1.0)

        # Term 4: Equilibrium temperature (x0 = 288 K, weight = 5.58)
        valid_teq = np.isfinite(teq) & (teq > 0)
        diff_teq = np.where(valid_teq, np.abs(teq - 288.0) / (teq + 288.0), 1.0)
        val_teq = np.clip(1.0 - diff_teq, 0.0, 1.0)

        # Total weights per row
        total_weight = (
            np.where(valid_r, 0.57, 0.0) + np.where(valid_mr, 1.07 + 0.70, 0.0) + np.where(valid_teq, 5.58, 0.0)
        )

        # Vectorized geometric mean in log-space
        log_esi = np.zeros(n, dtype=float)
        zero_mask = np.zeros(n, dtype=bool)

        terms = [
            (val_r, 0.57, valid_r),
            (val_rho, 1.07, valid_mr),
            (val_v, 0.70, valid_mr),
            (val_teq, 5.58, valid_teq),
        ]

        safe_total_weight = np.where(total_weight > 0, total_weight, 1.0)
        with np.errstate(all="ignore"):
            for val, w, valid in terms:
                zero_mask |= valid & (val <= 0.0)
                active = valid & (val > 0.0)
                norm_w = np.where(active, w / safe_total_weight, 0.0)
                log_esi += norm_w * np.log(np.maximum(val, 1e-300))

        esi = np.where(total_weight > 0, np.where(zero_mask, 0.0, np.clip(np.exp(log_esi), 0.0, 1.0)), np.nan)

        df["earth_similarity"] = esi
        return df

    def add_habitable_zone(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Classify Habitable Zone status using Kopparapu et al. (2013, 2014).

        Insolation flux thresholds S_eff as a function of stellar Teff:
            S_eff = S_eff_sun + a*T* + b*T*^2 + c*T*^3 + d*T*^4
        where T* = Teff - 5780 K.

        Boundaries (AU):
            d = sqrt( (L / L_sun) / S_eff )

        Classifications:
        - "Inside HZ": within conservative boundaries (Runaway Greenhouse to Maximum Greenhouse)
        - "Near HZ": within optimistic boundaries (Recent Venus to Early Mars), outside conservative
        - "Outside HZ": outside optimistic boundaries
        - "Insufficient data": if sma, luminosity, or Teff is unavailable
        """
        df = df.copy()

        lum = pd.to_numeric(df.get("stellar_luminosity", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(
            dtype=float
        )
        teff = pd.to_numeric(
            df.get("stellar_effective_temperature", pd.Series(np.nan, index=df.index)), errors="coerce"
        ).to_numpy(dtype=float)
        sma = pd.to_numeric(df.get("semi_major_axis", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(
            dtype=float
        )

        valid = (
            np.isfinite(lum)
            & (lum > 0)
            & np.isfinite(teff)
            & (teff >= 1500)
            & (teff <= 15000)
            & np.isfinite(sma)
            & (sma > 0)
        )

        t_star = np.where(valid, teff - 5780.0, 0.0)

        # Kopparapu et al. (2013) Table 3 polynomial coefficients [Seff_sun, a, b, c, d]
        s_rv = 1.776 + 2.136e-4 * t_star + 2.533e-8 * (t_star**2) - 1.332e-11 * (t_star**3) - 3.097e-15 * (t_star**4)
        s_rg = (
            1.0385 + 1.2456e-4 * t_star + 1.4612e-8 * (t_star**2) - 7.6345e-12 * (t_star**3) - 1.7511e-15 * (t_star**4)
        )
        s_mg = (
            0.3507 + 5.9578e-5 * t_star + 1.6707e-9 * (t_star**2) - 3.0058e-12 * (t_star**3) - 5.5064e-16 * (t_star**4)
        )
        s_em = (
            0.3207 + 5.4471e-5 * t_star + 1.5275e-9 * (t_star**2) - 2.7109e-12 * (t_star**3) - 4.9364e-16 * (t_star**4)
        )

        flux_ok = (s_rv > 0) & (s_rg > 0) & (s_mg > 0) & (s_em > 0) & valid

        with np.errstate(all="ignore"):
            r_in_opt = np.where(flux_ok, np.sqrt(lum / s_rv), np.nan)
            r_in_cons = np.where(flux_ok, np.sqrt(lum / s_rg), np.nan)
            r_out_cons = np.where(flux_ok, np.sqrt(lum / s_mg), np.nan)
            r_out_opt = np.where(flux_ok, np.sqrt(lum / s_em), np.nan)
            insolation_flux = np.where(valid, lum / (sma**2), np.nan)

        inside_hz = flux_ok & (sma >= r_in_cons) & (sma <= r_out_cons)
        near_hz = flux_ok & ~inside_hz & (sma >= r_in_opt) & (sma <= r_out_opt)
        outside_hz = flux_ok & ~inside_hz & ~near_hz

        hz_status = np.select(
            [inside_hz, near_hz, outside_hz], ["Inside HZ", "Near HZ", "Outside HZ"], default="Insufficient data"
        )

        df["hz_status"] = hz_status
        df["hz_inner_edge"] = np.where(flux_ok, r_in_cons, np.nan)
        df["hz_outer_edge"] = np.where(flux_ok, r_out_cons, np.nan)
        df["insolation_flux"] = np.where(flux_ok, insolation_flux, np.nan)
        df["hz_data_available"] = df["hz_status"] != "Insufficient data"

        return df

    def add_observational_accessibility(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute observational accessibility based on distance, infrared brightness (2MASS J/K),
        and transit geometry.

        Fully vectorized implementation.
        """
        df = df.copy()

        # 1. Distance score (parsecs): closer targets are more accessible for high SNR observations
        if "distance" in df.columns:
            dist = pd.to_numeric(df["distance"], errors="coerce")
            df["distance_score"] = np.where(dist.notna() & (dist >= 0), 1.0 / (1.0 + dist / 100.0), np.nan)
        else:
            df["distance_score"] = np.nan

        # 2. Stellar brightness score based on real infrared magnitude (2MASS K-band or J-band)
        if "k_magnitude" in df.columns:
            kmag = pd.to_numeric(df["k_magnitude"], errors="coerce")
        elif "j_magnitude" in df.columns:
            kmag = pd.to_numeric(df["j_magnitude"], errors="coerce")
        else:
            kmag = pd.Series(np.nan, index=df.index)

        df["brightness_score"] = np.where(kmag.notna(), np.clip(1.0 - (kmag - 6.0) / 10.0, 0.05, 1.0), np.nan)

        # 3. Transit spectroscopic signal: (R_planet / R_star)^2 transit depth proxy
        r_p = pd.to_numeric(df.get("planet_radius", pd.Series(np.nan, index=df.index)), errors="coerce")
        r_s = pd.to_numeric(df.get("stellar_radius", pd.Series(np.nan, index=df.index)), errors="coerce")
        period = pd.to_numeric(df.get("orbital_period", pd.Series(np.nan, index=df.index)), errors="coerce")

        depth_proxy = np.where(r_p.notna() & (r_p > 0) & r_s.notna() & (r_s > 0), ((r_p * 0.009168) / r_s) ** 2, np.nan)

        period_factor = np.where(period.notna() & (period > 0), 1.0 / np.log10(period + 2.0), 0.5)
        raw_transit_score = depth_proxy * period_factor

        valid_raw = raw_transit_score[pd.notna(raw_transit_score)]
        max_ts = np.nanpercentile(valid_raw, 98) if len(valid_raw) > 0 and np.nanmax(valid_raw) > 0 else 1.0

        df["transit_detectability"] = np.where(
            pd.notna(raw_transit_score), np.clip(raw_transit_score / (max_ts if max_ts > 0 else 1.0), 0.05, 1.0), np.nan
        )

        # 4. Composite accessibility: weighted mean over available physical components
        v1 = df["distance_score"]
        v2 = df["brightness_score"]
        v3 = df["transit_detectability"]

        w1 = np.where(v1.notna(), 0.40, 0.0)
        w2 = np.where(v2.notna(), 0.35, 0.0)
        w3 = np.where(v3.notna(), 0.25, 0.0)

        total_w = w1 + w2 + w3
        weighted_sum = np.nan_to_num(v1) * w1 + np.nan_to_num(v2) * w2 + np.nan_to_num(v3) * w3

        df["observational_accessibility"] = np.where(total_w > 0, weighted_sum / total_w, np.nan)
        return df

    def add_data_quality(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute unambiguous Data Quality score based on fraction of verified parameters available.
        Counted once in the target prioritization engine.
        """
        df = df.copy()
        core_cols = [
            "planet_radius",
            "planet_mass",
            "orbital_period",
            "semi_major_axis",
            "equilibrium_temperature",
            "stellar_effective_temperature",
            "stellar_radius",
            "distance",
        ]
        available_cols = [c for c in core_cols if c in df.columns]
        if available_cols:
            df["data_quality"] = df[available_cols].notna().sum(axis=1) / len(core_cols)
        else:
            df["data_quality"] = 0.5

        return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Execute full feature engineering pipeline."""
        df = self.add_earth_similarity(df)
        df = self.add_habitable_zone(df)
        df = self.add_observational_accessibility(df)
        df = self.add_data_quality(df)
        return df
