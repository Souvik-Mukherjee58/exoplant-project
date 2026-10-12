"""Data cleaning and standardization service."""

import numpy as np
import pandas as pd


class DataCleaning:
    """Cleans and standardizes exoplanet data."""

    # Exoplanet archive column mappings
    PLANET_COLUMNS = [
        "PlanetName",
        "PlanetMass",
        "PlanetMassErr1",
        "PlanetRadius",
        "PlanetRadiusErr1",
        "PlanetRadiusMin",
        "PlanetRadiusMax",
        "PlanetOrbitalPeriod",
        "PlanetOrbitalPeriodErr1",
        "PlanetOrbitalPeriodErr2",
        "PlanetSemiMajorAxis",
        "PlanetSemiMajorAxisErr1",
        "PlanetSemiMajorAxisErr2",
        "PlanetEquiTemp",
        "PlanetEquiTempErr1",
        "PlanetEquiTempErr2",
        "PlanetEccentricity",
        "PlanetEccentricityErr1",
        "PlanetDiscoveryYear",
        "PlanetDiscoveryMethod",
        "SmaUnit",
        "PPerYear",
        "SemiMajorAxis",
    ]

    def __init__(self):
        self.standard_column_names = {
            "PlanetMass": "planet_mass",
            "PlanetMassErr1": "planet_mass_err1",
            "PlanetRadius": "planet_radius",
            "PlanetRadiusErr1": "planet_radius_err1",
            "PlanetOrbitalPeriod": "orbital_period",
            "PlanetOrbitalPeriodErr1": "orbital_period_err1",
            "PlanetOrbitalPeriodErr2": "orbital_period_err2",
            "PlanetSemiMajorAxis": "semi_major_axis",
            "PlanetEquiTemp": "equilibrium_temperature",
            "PlanetEquiTempErr1": "equilibrium_temperature_err1",
            "PlanetEccentricity": "eccentricity",
            "PlanetEccentricityErr1": "eccentricity_err1",
            "PlanetDiscoveryMethod": "discovery_method",
            "PlanetDiscoveryYear": "discovery_year",
            "PlanetName": "planet_name",
            "SmaUnit": "semi_major_axis_unit",
            "PPerYear": "period_in_years",
            "PPerYearErr1": "period_in_years_err1",
            "PPerYearErr2": "period_in_years_err2",
        }

    def clean_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names and remove irrelevant columns."""
        if df.empty:
            return df

        # Convert all column names to lower case
        df.columns = df.columns.str.lower().str.replace(" ", "_")

        # Drop columns that are not useful for prioritization
        drop_cols = [
            col
            for col in df.columns
            if col
            in {
                "discoverydate",
                "updatedby",
                "updateddate",
                "reference",
                "exorbiteccentricity",
                "exorbitalsemimajoraxis",
            }
        ]
        df = df.drop(columns=drop_cols, errors="ignore")

        return df

    def sanitize_numeric(self, df: pd.DataFrame, columns: list) -> pd.DataFrame:
        """Convert columns to numeric, coercing errors to NaN."""
        for col in columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def remove_invalid_records(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove records with invalid/placeholder values used by exoplanet archive."""
        invalid_mask = df["planet_name"].isin(
            ["", "null", "None", "nan", "NAN", "NaN", "NULL"]
        ) | df["planet_name"].str.lower().isin(["null"])
        df = df[~invalid_mask].reset_index(drop=True)
        return df

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run the full cleaning pipeline."""
        df = self.clean_columns(df)

        numeric_columns = [
            "planet_mass",
            "planet_mass_err1",
            "planet_radius",
            "planet_radius_err1",
            "planet_radius_min",
            "planet_radius_max",
            "orbital_period",
            "orbital_period_err1",
            "orbital_period_err2",
            "semi_major_axis",
            "semi_major_axis_err1",
            "semi_major_axis_err2",
            "equilibrium_temperature",
            "equilibrium_temperature_err1",
            "equilibrium_temperature_err2",
            "eccentricity",
            "eccentricity_err1",
            "discovery_year",
            "period_in_years",
            "period_in_years_err1",
            "period_in_years_err2",
        ]
        df = self.sanitize_numeric(df, numeric_columns)

        df = self.remove_invalid_records(df)

        return df
