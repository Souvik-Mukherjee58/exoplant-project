"""Feature engineering service implementing published astrophysical metrics."""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional


class FeatureEngineering:
    """
    Computes published, defensible astrophysical metrics:
    - Earth Similarity Index (ESI) via Schulze-Makuch et al. (2011)
    - Circumstellar Habitable Zone boundaries via Kopparapu et al. (2013, 2014)
    - Observational Accessibility using 2MASS infrared stellar magnitudes (J/K)
    - Data completeness score (counted exactly once)
    """

    def __init__(self):
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
        """
        df = df.copy()

        def calc_row_esi(row):
            radius = row.get("planet_radius")
            mass = row.get("planet_mass")
            teq = row.get("equilibrium_temperature")

            terms = []
            # 1. Radius term
            if pd.notna(radius) and radius > 0:
                diff_r = abs(radius - 1.0) / (radius + 1.0)
                terms.append((1.0 - diff_r, 0.57))

            # 2. Bulk density & escape velocity (require both mass and radius)
            if pd.notna(mass) and mass > 0 and pd.notna(radius) and radius > 0:
                density = mass / (radius ** 3)
                diff_rho = abs(density - 1.0) / (density + 1.0)
                terms.append((1.0 - diff_rho, 1.07))

                v_esc = np.sqrt(mass / radius)
                diff_v = abs(v_esc - 1.0) / (v_esc + 1.0)
                terms.append((1.0 - diff_v, 0.70))

            # 3. Surface temperature term (reference: 288 K)
            if pd.notna(teq) and teq > 0:
                diff_t = abs(teq - 288.0) / (teq + 288.0)
                terms.append((1.0 - diff_t, 5.58))

            if not terms:
                return np.nan

            total_weight = sum(w for _, w in terms)
            esi = 1.0
            for val, weight in terms:
                val_clamped = max(0.0, float(val))
                esi *= (val_clamped ** (weight / total_weight))

            return float(np.clip(esi, 0.0, 1.0))

        df["earth_similarity"] = df.apply(calc_row_esi, axis=1)
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

        def compute_hz(row):
            lum = row.get("stellar_luminosity")
            teff = row.get("stellar_effective_temperature")
            sma = row.get("semi_major_axis")

            # Check validity
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

            # T* relative to Solar effective temperature (5780 K)
            t_star = teff - 5780.0

            # Kopparapu et al. (2013) Table 3 polynomial coefficients [Seff_sun, a, b, c, d]
            # 1. Recent Venus (optimistic inner edge)
            s_rv = 1.776 + 2.136e-4 * t_star + 2.533e-8 * (t_star ** 2) - 1.332e-11 * (t_star ** 3) - 3.097e-15 * (t_star ** 4)
            # 2. Runaway Greenhouse (conservative inner edge)
            s_rg = 1.0385 + 1.2456e-4 * t_star + 1.4612e-8 * (t_star ** 2) - 7.6345e-12 * (t_star ** 3) - 1.7511e-15 * (t_star ** 4)
            # 3. Maximum Greenhouse (conservative outer edge)
            s_mg = 0.3507 + 5.9578e-5 * t_star + 1.6707e-9 * (t_star ** 2) - 3.0058e-12 * (t_star ** 3) - 5.5064e-16 * (t_star ** 4)
            # 4. Early Mars (optimistic outer edge)
            s_em = 0.3207 + 5.4471e-5 * t_star + 1.5275e-9 * (t_star ** 2) - 2.7109e-12 * (t_star ** 3) - 4.9364e-16 * (t_star ** 4)

            # Avoid division by zero or negative flux limits
            if s_rv <= 0 or s_rg <= 0 or s_mg <= 0 or s_em <= 0:
                return "Insufficient data", np.nan, np.nan, np.nan

            r_in_opt = np.sqrt(lum / s_rv)
            r_in_cons = np.sqrt(lum / s_rg)
            r_out_cons = np.sqrt(lum / s_mg)
            r_out_opt = np.sqrt(lum / s_em)

            # Insolation flux incident on planet relative to Earth
            insolation_flux = lum / (sma ** 2)

            if r_in_cons <= sma <= r_out_cons:
                status = "Inside HZ"
            elif r_in_opt <= sma <= r_out_opt:
                status = "Near HZ"
            else:
                status = "Outside HZ"

            return status, float(r_in_cons), float(r_out_cons), float(insolation_flux)

        results = df.apply(compute_hz, axis=1)
        df["hz_status"] = [r[0] for r in results]
        df["hz_inner_edge"] = [r[1] for r in results]
        df["hz_outer_edge"] = [r[2] for r in results]
        df["insolation_flux"] = [r[3] for r in results]
        df["hz_data_available"] = df["hz_status"] != "Insufficient data"

        return df

    def add_observational_accessibility(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute observational accessibility based on distance, infrared brightness (2MASS J/K),
        and transit geometry.

        Note: data_quality is intentionally excluded to prevent double-counting.
        """
        df = df.copy()

        # 1. Distance score (parsecs): closer targets are more accessible for high SNR observations
        if "distance" in df.columns:
            dist = pd.to_numeric(df["distance"], errors="coerce")
            # Characteristic scale: 100 pc
            df["distance_score"] = np.where(dist.notna() & (dist >= 0), 1.0 / (1.0 + dist / 100.0), np.nan)
        else:
            df["distance_score"] = np.nan

        # 2. Stellar brightness score based on real infrared magnitude (2MASS K-band or J-band)
        # For transit spectroscopy (JWST/HST), K-band magnitude is the standard benchmark
        if "k_magnitude" in df.columns:
            kmag = pd.to_numeric(df["k_magnitude"], errors="coerce")
        elif "j_magnitude" in df.columns:
            kmag = pd.to_numeric(df["j_magnitude"], errors="coerce")
        else:
            kmag = pd.Series(np.nan, index=df.index)

        # Standard observational scale: K = 6 is very bright (1.0), K = 16 is faint (0.0)
        df["brightness_score"] = np.where(
            kmag.notna(),
            np.clip(1.0 - (kmag - 6.0) / 10.0, 0.05, 1.0),
            np.nan
        )

        # 3. Transit spectroscopic signal: (R_planet / R_star)^2 transit depth proxy
        r_p = pd.to_numeric(df.get("planet_radius", pd.Series(np.nan, index=df.index)), errors="coerce")
        r_s = pd.to_numeric(df.get("stellar_radius", pd.Series(np.nan, index=df.index)), errors="coerce")
        period = pd.to_numeric(df.get("orbital_period", pd.Series(np.nan, index=df.index)), errors="coerce")

        # Earth to Solar radius ratio: ~0.009168
        depth_proxy = np.where(
            r_p.notna() & (r_p > 0) & r_s.notna() & (r_s > 0),
            ((r_p * 0.009168) / r_s) ** 2,
            np.nan
        )

        # Frequent transits (shorter periods) yield higher observing opportunity
        period_factor = np.where(period.notna() & (period > 0), 1.0 / np.log10(period + 2.0), 0.5)
        raw_transit_score = depth_proxy * period_factor

        max_ts = np.nanpercentile(raw_transit_score, 98) if np.nanmax(raw_transit_score) > 0 else 1.0
        df["transit_detectability"] = np.where(
            pd.notna(raw_transit_score),
            np.clip(raw_transit_score / (max_ts if max_ts > 0 else 1.0), 0.05, 1.0),
            np.nan
        )

        # 4. Composite accessibility: weighted mean over available physical components
        components = ["distance_score", "brightness_score", "transit_detectability"]
        weights = {"distance_score": 0.40, "brightness_score": 0.35, "transit_detectability": 0.25}

        def calc_accessibility(row):
            valid_w = [weights[c] for c in components if pd.notna(row.get(c))]
            valid_v = [row.get(c) * weights[c] for c in components if pd.notna(row.get(c))]
            if not valid_w or sum(valid_w) == 0:
                return np.nan
            return sum(valid_v) / sum(valid_w)

        df["observational_accessibility"] = df.apply(calc_accessibility, axis=1)
        return df

    def add_data_quality(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute unambiguous Data Quality score based on fraction of verified parameters available.
        Counted once in the target prioritization engine.
        """
        df = df.copy()
        core_cols = [
            "planet_radius", "planet_mass", "orbital_period", "semi_major_axis",
            "equilibrium_temperature", "stellar_effective_temperature",
            "stellar_radius", "distance"
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
