"""Target priority scoring system based on published astrophysical metrics."""

from typing import Dict

import numpy as np
import pandas as pd


class TargetPriorityScorer:
    """
    Computes defensible follow-up target priority scores (0-100) combining:
    - Planetary habitability & relevance (ESI, Kopparapu HZ alignment, terrestrial sizing)
    - Observational accessibility (distance, 2MASS infrared stellar magnitude, transit signal)
    - Host star viability (M, K, G dwarf suitability, metallicity)
    - Data completeness (single non-redundant accounting)
    - Anomaly / novelty factor

    Fully vectorized implementation using NumPy and Pandas.
    """

    def __init__(self) -> None:
        self.scoring_config: Dict[str, float] = {
            "planetary_relevance_weight": 0.35,
            "observational_accessibility_weight": 0.30,
            "stellar_characteristics_weight": 0.15,
            "data_quality_weight": 0.10,
            "anomaly_score_weight": 0.10,
        }

    def calculate_planetary_relevance(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Evaluate planetary relevance for follow-up spectroscopic study.

        Combines:
        1. Published Earth Similarity Index (ESI) (Schulze-Makuch et al. 2011)
        2. Habitable Zone classification (Kopparapu et al. 2013/2014)
        3. Terrestrial / super-Earth radius envelope (0.8 - 1.8 R_earth)
        """
        df = df.copy()

        # 1. Earth Similarity Index (0-1)
        if "earth_similarity" in df.columns:
            esi = pd.to_numeric(df["earth_similarity"], errors="coerce")
        else:
            esi = pd.Series(np.nan, index=df.index)

        # 2. Kopparapu Habitable Zone score
        hz_mapping = {
            "Inside HZ": 1.0,
            "Near HZ": 0.65,
            "Outside HZ": 0.15,
            "Insufficient data": 0.30,
        }
        if "hz_status" in df.columns:
            hz_score = df["hz_status"].map(hz_mapping).fillna(0.30)
        else:
            hz_score = pd.Series(0.30, index=df.index)

        # 3. Radius appropriateness for rocky / terrestrial atmospheres
        if "planet_radius" in df.columns:
            r = pd.to_numeric(df["planet_radius"], errors="coerce")
            radius_score = np.where(
                r.notna() & (r > 0),
                np.where(
                    r <= 1.8,
                    np.exp(-0.5 * ((r - 1.1) / 0.5) ** 2),
                    np.maximum(0.05, np.exp(-0.5 * ((r - 1.1) / 2.0) ** 2)),
                ),
                np.nan,
            )
        else:
            radius_score = pd.Series(np.nan, index=df.index)

        # Vectorized weighted combination of available planetary components
        w_esi = np.where(esi.notna(), 0.40, 0.0)
        w_hz = np.where(hz_score.notna(), 0.40, 0.0)
        w_rad = np.where(pd.notna(radius_score), 0.20, 0.0)

        total_w = w_esi + w_hz + w_rad
        weighted_sum = np.nan_to_num(esi) * w_esi + np.nan_to_num(hz_score) * w_hz + np.nan_to_num(radius_score) * w_rad

        df["planetary_relevance"] = np.where(total_w > 0, weighted_sum / total_w, 0.3)
        return df

    def calculate_stellar_characteristics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Evaluate host star suitability for atmospheric characterization.

        Avoids penalizing M-dwarfs (which provide optimal transit contrast ratios for JWST).
        Favors main-sequence M, K, and G dwarfs (Teff 2500K - 6500K) and non-extreme stellar radii.
        """
        df = df.copy()

        # 1. Effective temperature suitability
        if "stellar_effective_temperature" in df.columns:
            teff = pd.to_numeric(df["stellar_effective_temperature"], errors="coerce")
            teff_score = np.where(
                teff.notna(),
                np.where(
                    (teff >= 2600) & (teff <= 6200),
                    0.85 + 0.15 * np.exp(-0.5 * ((teff - 4500) / 1500) ** 2),
                    np.maximum(0.1, np.exp(-0.5 * ((teff - 5000) / 2000) ** 2)),
                ),
                np.nan,
            )
        else:
            teff_score = pd.Series(np.nan, index=df.index)

        # 2. Stellar radius
        if "stellar_radius" in df.columns:
            rad = pd.to_numeric(df["stellar_radius"], errors="coerce")
            rad_score = np.where(
                rad.notna() & (rad > 0),
                np.where(
                    rad <= 1.2,
                    1.0 - 0.25 * rad,
                    np.maximum(0.1, 1.0 / (1.0 + (rad - 1.0))),
                ),
                np.nan,
            )
        else:
            rad_score = pd.Series(np.nan, index=df.index)

        # 3. Metallicity (Fe/H)
        if "stellar_metallicity" in df.columns:
            met = pd.to_numeric(df["stellar_metallicity"], errors="coerce")
            met_score = np.where(
                met.notna(),
                np.clip((met + 0.5) / 1.0, 0.2, 1.0),
                np.nan,
            )
        else:
            met_score = pd.Series(np.nan, index=df.index)

        # Vectorized weighted combination of host star components
        w_teff = np.where(pd.notna(teff_score), 0.45, 0.0)
        w_rad = np.where(pd.notna(rad_score), 0.40, 0.0)
        w_met = np.where(pd.notna(met_score), 0.15, 0.0)

        total_w = w_teff + w_rad + w_met
        weighted_sum = (
            np.nan_to_num(teff_score) * w_teff + np.nan_to_num(rad_score) * w_rad + np.nan_to_num(met_score) * w_met
        )

        df["stellar_characteristics"] = np.where(total_w > 0, weighted_sum / total_w, 0.5)
        return df

    def calculate_target_priority(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate composite target priority score (0-100)."""
        df = df.copy()

        # Component scores on 0-100 scale
        p_rel = pd.to_numeric(df.get("planetary_relevance", pd.Series(0.3, index=df.index)), errors="coerce").fillna(
            0.3
        )
        df["planetary_relevance_score"] = np.clip(p_rel * 100.0, 0.0, 100.0)

        obs = pd.to_numeric(
            df.get("observational_accessibility", pd.Series(0.4, index=df.index)), errors="coerce"
        ).fillna(0.4)
        df["observational_accessibility_score"] = np.clip(obs * 100.0, 0.0, 100.0)

        s_char = pd.to_numeric(
            df.get("stellar_characteristics", pd.Series(0.5, index=df.index)), errors="coerce"
        ).fillna(0.5)
        df["stellar_characteristics_score"] = np.clip(s_char * 100.0, 0.0, 100.0)

        dq = pd.to_numeric(df.get("data_quality", pd.Series(0.5, index=df.index)), errors="coerce").fillna(0.5)
        df["data_quality_score"] = np.clip(dq * 100.0, 0.0, 100.0)

        anom = pd.to_numeric(df.get("anomaly_score", pd.Series(0.1, index=df.index)), errors="coerce").fillna(0.1)
        df["anomaly_score_normalized"] = np.clip(anom * 100.0, 0.0, 100.0)

        # Final weighted composite
        final_scores = (
            df["planetary_relevance_score"] * self.scoring_config["planetary_relevance_weight"]
            + df["observational_accessibility_score"] * self.scoring_config["observational_accessibility_weight"]
            + df["stellar_characteristics_score"] * self.scoring_config["stellar_characteristics_weight"]
            + df["data_quality_score"] * self.scoring_config["data_quality_weight"]
            + df["anomaly_score_normalized"] * self.scoring_config["anomaly_score_weight"]
        )

        df["target_priority_score"] = np.clip(final_scores, 0.0, 100.0)

        # Store priority component breakdown dict fast without row-wise apply
        p_vals = np.round(df["planetary_relevance_score"].to_numpy(dtype=float), 1)
        s_vals = np.round(df["stellar_characteristics_score"].to_numpy(dtype=float), 1)
        o_vals = np.round(df["observational_accessibility_score"].to_numpy(dtype=float), 1)
        d_vals = np.round(df["data_quality_score"].to_numpy(dtype=float), 1)
        a_vals = np.round(df["anomaly_score_normalized"].to_numpy(dtype=float), 1)
        f_vals = np.round(df["target_priority_score"].to_numpy(dtype=float), 1)

        df["priority_components"] = [
            {
                "planetary_relevance": float(p),
                "stellar_characteristics": float(s),
                "observational_accessibility": float(o),
                "data_quality": float(d),
                "anomaly_score": float(a),
                "final_score": float(f),
            }
            for p, s, o, d, a, f in zip(p_vals, s_vals, o_vals, d_vals, a_vals, f_vals)
        ]

        # Sort descending by priority
        df = df.sort_values("target_priority_score", ascending=False).reset_index(drop=True)
        return df

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run full prioritization scoring pipeline."""
        df = self.calculate_planetary_relevance(df)
        df = self.calculate_stellar_characteristics(df)
        df = self.calculate_target_priority(df)
        return df
