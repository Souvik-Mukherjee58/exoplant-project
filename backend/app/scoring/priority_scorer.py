"""Target priority scoring system."""

import numpy as np
import pandas as pd


class TargetPriorityScorer:
    """Calculate scientifically interpretable target priority scores."""

    def __init__(self):
        self.scoring_config = {
            "planetary_relevance_weight": 0.25,
            "stellar_characteristics_weight": 0.25,
            "observational_accessibility_weight": 0.2,
            "data_quality_weight": 0.15,
            "anomaly_score_weight": 0.15,
        }

    def calculate_planetary_relevance(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Planetary relevance based on size, mass, and temperature.

        Higher scores for planets that are Earth-like or at least potentially habitable.
        """
        df = df.copy()

        # Radius relevance: Earth-like (0.5-2.0 Earth radii) is most relevant
        if "planet_radius" in df.columns:
            r = pd.to_numeric(df["planet_radius"], errors="coerce")
            radius_relevance = np.where(r.notna(), np.exp(-0.5 * ((r - 1.0) / 0.8) ** 2), np.nan)
        else:
            radius_relevance = np.full(len(df), np.nan)

        # Mass relevance: Earth-like (0.1-10 Earth masses) is most relevant
        if "planet_mass" in df.columns:
            m = pd.to_numeric(df["planet_mass"], errors="coerce")
            mass_relevance = np.where(m.notna(), np.exp(-0.5 * ((m - 1.0) / 3.0) ** 2), np.nan)
        else:
            mass_relevance = np.full(len(df), np.nan)

        # Temperature relevance: moderate temperatures (200-400K) are most relevant
        if "equilibrium_temperature" in df.columns:
            t = pd.to_numeric(df["equilibrium_temperature"], errors="coerce")
            temp_relevance = np.where(t.notna(), np.exp(-0.5 * ((t - 300.0) / 150.0) ** 2), np.nan)
        else:
            temp_relevance = np.full(len(df), np.nan)

        # Orbital period relevance: neither too short nor too long
        if "orbital_period" in df.columns:
            p = pd.to_numeric(df["orbital_period"], errors="coerce")
            period_relevance = np.where(
                p.notna() & (p > 0),
                np.exp(-0.5 * ((np.log10(p + 0.1) - 0.5) / 0.5) ** 2),
                np.nan
            )
        else:
            period_relevance = np.full(len(df), np.nan)

        # Build DataFrame of relevance components with their scientific weights
        rel_df = pd.DataFrame({
            "radius": radius_relevance,
            "mass": mass_relevance,
            "temp": temp_relevance,
            "period": period_relevance,
        }, index=df.index)

        weights = {"radius": 0.3, "mass": 0.3, "temp": 0.2, "period": 0.2}
        
        # Weighted mean over available (non-NaN) components
        def calc_weighted_relevance(row):
            valid_w = [weights[k] for k in weights if pd.notna(row[k])]
            valid_v = [row[k] * weights[k] for k in weights if pd.notna(row[k])]
            if not valid_w or sum(valid_w) == 0:
                return 0.5
            return sum(valid_v) / sum(valid_w)

        df["planetary_relevance"] = rel_df.apply(calc_weighted_relevance, axis=1)
        return df

    def calculate_stellar_characteristics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Stellar characteristics score based on effective temperature, radius, etc.

        Stars with temperatures similar to the Sun are generally most favorable.
        """
        df = df.copy()

        # Stellar effective temperature relevance
        if "stellar_effective_temperature" in df.columns:
            st_temp = pd.to_numeric(df["stellar_effective_temperature"], errors="coerce")
            temp_score = np.clip(st_temp / 5778.0, 0.3, 2.0)
            df["stellar_temp_relevance"] = np.where(
                st_temp.notna(),
                np.exp(-0.5 * ((temp_score - 1.0) / 0.5) ** 2),
                np.nan
            )
        else:
            df["stellar_temp_relevance"] = np.nan

        # Stellar radius relevance (similar to Sun is better)
        if "stellar_radius" in df.columns:
            st_rad = pd.to_numeric(df["stellar_radius"], errors="coerce")
            radius_score = np.clip(st_rad / 1.0, 0.3, 3.0)
            df["stellar_radius_relevance"] = np.where(
                st_rad.notna(),
                np.exp(-0.5 * ((radius_score - 1.0) / 0.5) ** 2),
                np.nan
            )
        else:
            df["stellar_radius_relevance"] = np.nan

        # Stellar metallicity (higher metallicity stars have more likely planet formation)
        if "stellar_metallicity" in df.columns:
            st_met = pd.to_numeric(df["stellar_metallicity"], errors="coerce")
            norm_metallicity = np.clip((st_met + 0.5) / 1.0, 0.0, 1.0)
            df["stellar_metallicity_relevance"] = np.where(st_met.notna(), norm_metallicity, np.nan)
        else:
            df["stellar_metallicity_relevance"] = np.nan

        # Weighted mean over available stellar components
        stellar_df = df[["stellar_temp_relevance", "stellar_radius_relevance", "stellar_metallicity_relevance"]]
        s_weights = {"stellar_temp_relevance": 0.4, "stellar_radius_relevance": 0.3, "stellar_metallicity_relevance": 0.3}

        def calc_weighted_stellar(row):
            valid_w = [s_weights[k] for k in s_weights if pd.notna(row[k])]
            valid_v = [row[k] * s_weights[k] for k in s_weights if pd.notna(row[k])]
            if not valid_w or sum(valid_w) == 0:
                return 0.5
            return sum(valid_v) / sum(valid_w)

        df["stellar_characteristics"] = stellar_df.apply(calc_weighted_stellar, axis=1)
        return df

    def calculate_target_priority(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the final target priority score (0-100).

        This is the core scoring method described in the project requirements.
        """
        df = df.copy()

        # Planetary relevance (0-1 -> 0-100)
        p_rel = pd.to_numeric(df.get("planetary_relevance", pd.Series(0.5, index=df.index)), errors="coerce").fillna(0.5)
        df["planetary_relevance_score"] = np.clip(p_rel * 100.0, 0.0, 100.0)

        # Stellar characteristics (0-1 -> 0-100)
        s_char = pd.to_numeric(df.get("stellar_characteristics", pd.Series(0.5, index=df.index)), errors="coerce").fillna(0.5)
        df["stellar_characteristics_score"] = np.clip(s_char * 100.0, 0.0, 100.0)

        # Observational accessibility (0-1 -> 0-100)
        obs = pd.to_numeric(df.get("observational_accessibility", pd.Series(0.5, index=df.index)), errors="coerce").fillna(0.5)
        df["observational_accessibility_score"] = np.clip(obs * 100.0, 0.0, 100.0)

        # Data quality (0-1 -> 0-100)
        dq = pd.to_numeric(df.get("data_quality", pd.Series(0.5, index=df.index)), errors="coerce").fillna(0.5)
        df["data_quality_score"] = np.clip(dq * 100.0, 0.0, 100.0)

        # Anomaly score (0-1 -> 0-100)
        anom = pd.to_numeric(df.get("anomaly_score", pd.Series(0.0, index=df.index)), errors="coerce").fillna(0.0)
        df["anomaly_score_normalized"] = np.clip(anom * 100.0, 0.0, 100.0)

        # Weighted sum for final priority score
        weighted_sum = (
            df["planetary_relevance_score"] * self.scoring_config["planetary_relevance_weight"]
            + df["stellar_characteristics_score"] * self.scoring_config["stellar_characteristics_weight"]
            + df["observational_accessibility_score"] * self.scoring_config["observational_accessibility_weight"]
            + df["data_quality_score"] * self.scoring_config["data_quality_weight"]
            + df["anomaly_score_normalized"] * self.scoring_config["anomaly_score_weight"]
        )

        df["target_priority_score"] = np.clip(weighted_sum.fillna(0.0), 0.0, 100.0)

        # Add explanation metadata
        def make_components(row):
            def safe_round(val):
                if pd.isna(val):
                    return 0.0
                return round(float(val), 1)

            return {
                "planetary_relevance": safe_round(row.get("planetary_relevance_score", 0)),
                "stellar_characteristics": safe_round(row.get("stellar_characteristics_score", 0)),
                "observational_accessibility": safe_round(row.get("observational_accessibility_score", 0)),
                "data_quality": safe_round(row.get("data_quality_score", 0)),
                "anomaly_score": safe_round(row.get("anomaly_score_normalized", 0)),
                "final_score": safe_round(row.get("target_priority_score", 0)),
            }

        df["priority_components"] = df.apply(make_components, axis=1)

        return df

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run full scoring pipeline."""
        df = self.calculate_planetary_relevance(df)
        df = self.calculate_stellar_characteristics(df)
        df = self.calculate_target_priority(df)

        return df