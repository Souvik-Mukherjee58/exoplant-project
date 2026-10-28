import logging
import numpy as np
import pandas as pd
from typing import List, Optional

logger = logging.getLogger(__name__)


class DataCleaning:
    """Cleans, standardizes, validates, and transforms exoplanet archive data."""

    def __init__(self):
        # Mappings from NASA TAP pscomppars columns to standardized application schema
        self.tap_column_names = {
            "pl_name": "planet_name",
            "pl_rade": "planet_radius",
            "pl_bmasse": "planet_mass",
            "pl_orbper": "orbital_period",
            "pl_orbsmax": "semi_major_axis",
            "pl_eqt": "equilibrium_temperature",
            "pl_orbeccen": "eccentricity",
            "st_teff": "stellar_effective_temperature",
            "st_rad": "stellar_radius",
            "st_mass": "stellar_mass",
            "st_met": "stellar_metallicity",
            "st_lum": "st_lum_log10",
            "sy_dist": "distance",
            "sy_jmag": "j_magnitude",
            "sy_kmag": "k_magnitude",
            "discoverymethod": "discovery_method",
            "disc_year": "discovery_year",
            "tran_flag": "tran_flag",
        }

        # Legacy column names for backward compatibility with sample CSVs
        self.legacy_column_names = {
            "planetname": "planet_name",
            "planetmass": "planet_mass",
            "planetradius": "planet_radius",
            "planetorbitalperiod": "orbital_period",
            "planetsemimajoraxis": "semi_major_axis",
            "planetequitemp": "equilibrium_temperature",
            "planeteccentricity": "eccentricity",
            "planetdiscoverymethod": "discovery_method",
            "planetdiscoveryyear": "discovery_year",
            "stellareffectivetemperature": "stellar_effective_temperature",
            "stellarradius": "stellar_radius",
            "stellarmass": "stellar_mass",
            "stellarmetallicity": "stellar_metallicity",
            "stellarluminosity": "stellar_luminosity",
            "dist": "distance",
        }

    def standardize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map raw archive column names to consistent standardized names."""
        if df.empty:
            return df

        df = df.copy()

        # Check for TAP names first
        rename_map = {}
        for col in df.columns:
            clean_col = col.strip().lower()
            if clean_col in self.tap_column_names:
                rename_map[col] = self.tap_column_names[clean_col]
            elif clean_col in self.legacy_column_names:
                rename_map[col] = self.legacy_column_names[clean_col]

        if rename_map:
            df = df.rename(columns=rename_map)

        # Normalize remaining columns to lowercase with underscores
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        return df

    def sanitize_numeric(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """Convert specified columns to numeric, coercing unparseable values to NaN."""
        df = df.copy()
        for col in columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def handle_astrophysical_units(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert explicit archive units to standard physical quantities.

        - st_lum in NASA archive is log10(L / L_sun); convert to linear Solar luminosities (L_sun).
        - If st_lum is absent, compute Stefan-Boltzmann approximation: (R_star)^2 * (T_eff / 5780)^4.
        - Distance in parsecs (sy_dist) preserved as 'distance', and 'distance_ly' derived as pc * 3.26156.
        - Derive stellar_name from planet_name if missing.
        """
        df = df.copy()

        # Handle luminosity (log10 L_sun -> linear L_sun)
        if "st_lum_log10" in df.columns:
            linear_lum = np.where(df["st_lum_log10"].notna(), 10.0 ** df["st_lum_log10"], np.nan)
            df["stellar_luminosity"] = linear_lum
        elif "stellar_luminosity" not in df.columns:
            df["stellar_luminosity"] = np.nan

        # Stefan-Boltzmann fallback for missing stellar luminosity
        if "stellar_radius" in df.columns and "stellar_effective_temperature" in df.columns:
            rad = pd.to_numeric(df["stellar_radius"], errors="coerce")
            teff = pd.to_numeric(df["stellar_effective_temperature"], errors="coerce")
            sb_lum = np.where(
                rad.notna() & (rad > 0) & teff.notna() & (teff > 0),
                (rad ** 2) * ((teff / 5780.0) ** 4),
                np.nan
            )
            df["stellar_luminosity"] = df["stellar_luminosity"].fillna(pd.Series(sb_lum, index=df.index))

        # Handle distance (pc) and distance_ly (light-years)
        if "distance" in df.columns:
            dist = pd.to_numeric(df["distance"], errors="coerce")
            df["distance_ly"] = np.where(dist.notna() & (dist >= 0), dist * 3.26156, np.nan)

        # Derive stellar host name from planet_name if not provided
        if "stellar_name" not in df.columns or df["stellar_name"].isna().all():
            if "planet_name" in df.columns:
                # E.g. "TOI-700 d" -> "TOI-700", "Kepler-6 b" -> "Kepler-6"
                df["stellar_name"] = df["planet_name"].astype(str).str.replace(r"\s+[a-z]$", "", regex=True)

        return df

    def validate_and_deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove invalid records, duplicate planet entries, and unphysical outliers.
        """
        df = df.copy()

        # Ensure planet_name is clean string
        df["planet_name"] = df["planet_name"].astype(str).str.strip().str.replace('"', "")
        invalid_names = {"", "null", "none", "nan", "undefined"}
        df = df[~df["planet_name"].str.lower().isin(invalid_names)]

        # Deduplicate on planet_name (keep first occurrence)
        df = df.drop_duplicates(subset=["planet_name"]).reset_index(drop=True)

        # Astrophysical sanity bounds:
        # Flag/clamp corrupt radius (> 40 Earth radii or <= 0)
        if "planet_radius" in df.columns:
            df.loc[(df["planet_radius"] <= 0) | (df["planet_radius"] > 40.0), "planet_radius"] = np.nan

        # Clamp corrupt equilibrium temperature (> 10,000 K or <= 0)
        if "equilibrium_temperature" in df.columns:
            df.loc[(df["equilibrium_temperature"] <= 0) | (df["equilibrium_temperature"] > 10000.0), "equilibrium_temperature"] = np.nan

        # Clamp corrupt orbital period (<= 0)
        if "orbital_period" in df.columns:
            df.loc[df["orbital_period"] <= 0, "orbital_period"] = np.nan

        # Clamp corrupt semi-major axis (<= 0)
        if "semi_major_axis" in df.columns:
            df.loc[df["semi_major_axis"] <= 0, "semi_major_axis"] = np.nan

        return df.reset_index(drop=True)

    def compute_transmission_eligibility(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Derive transit flag and atmospheric transmission spectroscopy eligibility.

        eligible_for_transmission = (
            is_transiting & planet_radius.notna() &
            equilibrium_temperature.notna() & stellar_radius.notna() &
            (j_magnitude.notna() | k_magnitude.notna())
        )
        """
        df = df.copy()

        # Map tran_flag -> is_transiting
        if "tran_flag" in df.columns and not df["tran_flag"].isna().all():
            df["is_transiting"] = pd.to_numeric(df["tran_flag"], errors="coerce").fillna(0).astype(int) == 1
        elif "is_transiting" in df.columns and not df["is_transiting"].isna().all():
            df["is_transiting"] = df["is_transiting"].apply(
                lambda x: True if str(x).strip().lower() in ("1", "true", "1.0") or x is True else False
            )
        else:
            logger.warning("tran_flag missing from data; deriving is_transiting from discovery_method == 'Transit'")
            if "discovery_method" in df.columns:
                df["is_transiting"] = (
                    df["discovery_method"].fillna("").astype(str).str.strip().str.lower() == "transit"
                )
            else:
                df["is_transiting"] = False

        df["is_transiting"] = df["is_transiting"].astype(bool)

        # Ensure required columns exist
        for col in ["planet_radius", "equilibrium_temperature", "stellar_radius", "j_magnitude", "k_magnitude"]:
            if col not in df.columns:
                df[col] = np.nan

        is_transiting = df["is_transiting"]
        has_radius = df["planet_radius"].notna()
        has_teq = df["equilibrium_temperature"].notna()
        has_srad = df["stellar_radius"].notna()
        has_mag = df["j_magnitude"].notna() | df["k_magnitude"].notna()

        df["eligible_for_transmission"] = (
            is_transiting & has_radius & has_teq & has_srad & has_mag
        ).astype(bool)

        # Compute exclusion reason string column
        reasons = []
        for trans, r, teq, srad, mag, elig in zip(
            is_transiting, has_radius, has_teq, has_srad, has_mag, df["eligible_for_transmission"]
        ):
            if elig:
                reasons.append("")
            else:
                r_list = []
                if not trans:
                    r_list.append("Non-transiting")
                if not r:
                    r_list.append("Missing planet radius")
                if not teq:
                    r_list.append("Missing equilibrium temperature")
                if not srad:
                    r_list.append("Missing stellar radius")
                if not mag:
                    r_list.append("Missing J/K magnitude")
                reasons.append("; ".join(r_list) if r_list else "Ineligible")

        df["exclusion_reason"] = reasons
        return df

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run the end-to-end cleaning and standardization pipeline."""
        if df.empty:
            return df

        df = self.standardize_column_names(df)

        numeric_columns = [
            "planet_radius", "planet_mass", "orbital_period", "semi_major_axis",
            "equilibrium_temperature", "eccentricity", "discovery_year",
            "stellar_effective_temperature", "stellar_radius", "stellar_mass",
            "stellar_metallicity", "st_lum_log10", "stellar_luminosity",
            "distance", "j_magnitude", "k_magnitude"
        ]
        df = self.sanitize_numeric(df, numeric_columns)
        df = self.handle_astrophysical_units(df)
        df = self.validate_and_deduplicate(df)
        df = self.compute_transmission_eligibility(df)

        return df

