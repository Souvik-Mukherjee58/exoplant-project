"""Data ingestion service for Exoplanet data."""

import pandas as pd
import os
import json
from pathlib import Path

from app.config import settings


class DataIngestion:
    """Handles downloading and loading exoplanet data."""

    def __init__(self, raw_dir: str = None, processed_dir: str = None):
        self.raw_dir = Path(raw_dir or settings.RAW_DATA_DIR)
        self.processed_dir = Path(processed_dir or settings.PROCESSED_DATA_DIR)
        self.exoplanet_archive_url = (
            "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query="
            "SELECT+*+FROM+Planet+Primary+Parameter+Collection"
        )

    def create_directories(self) -> None:
        """Create raw and processed data directories."""
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def load_from_csv(self, file_path: str) -> pd.DataFrame:
        """Load exoplanet data from a CSV file."""
        df = pd.read_csv(file_path)
        return df

    def load_or_download_exoplanet_archive(self, use_api: bool = False) -> pd.DataFrame:
        """
        Load exoplanet data.

        If use_api is False, looks for a local CSV in the raw directory.
        If use_api is True, downloads the NASA Exoplanet Archive TAP table.
        """
        self.create_directories()

        # Look for local CSV first
        csv_candidates = list(self.raw_dir.glob("*.csv"))
        if csv_candidates:
            return self.load_from_csv(str(csv_candidates[0]))

        return pd.DataFrame()

    def save_processed_data(self, df: pd.DataFrame, filename: str) -> str:
        """Save processed data to disk."""
        self.create_directories()
        path = self.processed_dir / filename
        df.to_csv(path, index=False)
        return str(path)

    def load_processed_data(self, filename: str) -> pd.DataFrame:
        """Load processed data from disk."""
        path = self.processed_dir / filename
        return pd.read_csv(path)
