"""Feature engineering service."""

import numpy as np
import pandas as pd
from scipy.stats import zscore


class FeatureEngineering:
    """Creates derived scientific features."""

    def __init__(self):
        pass

    def add_earth_similarity(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute an Earth Similarity Index (ESI) based on radius, mass, temperature."""
        # ESI components (0-1 scale)
        radius_eq = 1.0  # Earth radius in Earth radii
        mass_eq = 1.0  # Earth mass in Earth masses
        temp_eq = 288.0  # Earth equilibrium temp in K

        # Normalize: assume typical exoplanet ranges for scaling
        r = pd.to_numeric(df.get("planet_radius", pd.Series(np.nan, index=df.index)), errors="coerce")
        m = pd.to_numeric(df.get("planet_mass", pd.Series(np.nan, index=df.index)), errors="coerce")
        t = pd.to_numeric(df.get("equilibrium_temperature", pd.Series(np.nan, index=df.index)), errors="coerce")

        df["radius_esi"] = np.where(r.notna(), np.exp(-0.5 * ((r - radius_eq) / 2.0) ** 2), np.nan)
        df["mass_esi"] = np.where(m.notna(), np.exp(-0.5 * ((m - mass_eq) / 2.0) ** 2), np.nan)
        df["temp_esi"] = np.where(t.notna(), np.exp(-0.5 * ((t - temp_eq) / 100.0) ** 2), np.nan)

        # Combined ESI: average available components, fallback to 0.5 if all missing
        esi_df = df[["radius_esi", "mass_esi", "temp_esi"]]
        df["earth_similarity"] = esi_df.mean(axis=1).fillna(0.5)

        return df

    def add_habitable_zone_status(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Estimate habitable zone status using stellar mass and luminosity.

        Uses a simplified calculation based on stellar luminosity:
        HZ inner ~0.95 AU, outer ~1.67 AU for Sun-like stars.
        Scales with sqrt(luminosity).
        """
        def classify_hz(row):
            sma = row.get("semi_major_axis")
            lum = row.get("stellar_luminosity")
            if pd.isna(sma) or pd.isna(lum):
                return "Insufficient data"

            try:
                lum = float(lum)
                a = float(sma)
            except (ValueError, TypeError):
                return "Insufficient data"

            if lum <= 0 or a <= 0 or np.isnan(lum) or np.isnan(a):
                return "Insufficient data"

            hz_inner = 0.95 * np.sqrt(lum)
            hz_outer = 1.67 * np.sqrt(lum)

            if a < hz_inner * 0.8:
                return "Outside HZ"
            elif a < hz_inner:
                return "Near HZ"
            elif a <= hz_outer:
                return "Inside HZ"
            else:
                return "Outside HZ"

        df["hz_status"] = df.apply(classify_hz, axis=1)
        return df

    def add_observational_accessibility(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute observational accessibility score based on distance, brightness, etc."""
        # Closer stars are easier to observe
        if "distance" in df.columns:
            dist = pd.to_numeric(df["distance"], errors="coerce")
            df["distance_score"] = np.where(dist.notna() & (dist >= 0), 1 / (1 + dist / 100.0), 0.5)
        else:
            df["distance_score"] = 0.5

        # Brighter stars are easier to observe (stellar magnitude proxy)
        if "stellar_magnitude" in df.columns:
            mag = pd.to_numeric(df["stellar_magnitude"], errors="coerce")
            df["brightness_score"] = np.where(mag.notna(), 1 / (1 + np.maximum(mag, 0) / 10.0), 0.5)
        else:
            df["brightness_score"] = 0.5

        # Transit detectability (larger radius, shorter period)
        period = pd.to_numeric(df.get("orbital_period", pd.Series(np.nan, index=df.index)), errors="coerce")
        radius = pd.to_numeric(df.get("planet_radius", pd.Series(np.nan, index=df.index)), errors="coerce")
        
        valid_period = np.where(period.notna() & (period > 0), period, 365.0)
        valid_radius = np.where(radius.notna() & (radius > 0), radius, 1.0)
        td = valid_radius * (1.0 / np.maximum(valid_period, 0.1))
        
        max_td = np.nanmax(td) if len(td) > 0 else 0.0
        if pd.notna(max_td) and max_td > 0:
            df["transit_detectability"] = td / max_td
        else:
            df["transit_detectability"] = 0.5

        # Data quality proxy: number of available measurements
        available_quality_cols = [
            col for col in [
                "planet_radius",
                "planet_mass",
                "equilibrium_temperature",
                "semi_major_axis",
                "eccentricity",
            ] if col in df.columns
        ]
        if available_quality_cols:
            df["data_quality"] = df[available_quality_cols].notna().sum(axis=1) / 5.0
        else:
            df["data_quality"] = 0.5

        # Combined accessibility
        df["observational_accessibility"] = (
            df["distance_score"] * 0.3
            + df["brightness_score"] * 0.2
            + df["transit_detectability"] * 0.3
            + df["data_quality"] * 0.2
        ).fillna(0.5)

        return df

    def add_anomaly_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add features useful for anomaly detection."""
        # Z-scores of key properties
        for col in ["planet_radius", "planet_mass", "equilibrium_temperature", "orbital_period"]:
            if col in df.columns:
                series = pd.to_numeric(df[col], errors="coerce")
                med = series.median()
                if pd.isna(med):
                    med = 1.0
                filled = series.fillna(med)
                std = filled.std()
                if pd.notna(std) and std > 1e-8:
                    df[f"{col}_zscore"] = (filled - filled.mean()) / std
                else:
                    df[f"{col}_zscore"] = 0.0

        return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run full feature engineering pipeline."""
        df = self.add_earth_similarity(df)
        df = self.add_habitable_zone_status(df)
        df = self.add_observational_accessibility(df)
        df = self.add_anomaly_features(df)

        return df
