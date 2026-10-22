"""Data ingestion service for Exoplanet data."""

import pandas as pd
import os
import json
from pathlib import Path
import requests
from typing import Optional

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
        try:
            df = pd.read_csv(file_path)
            if df.empty:
                raise ValueError(f"CSV file is empty: {file_path}")
            return df
        except Exception as e:
            raise ValueError(f"Failed to load CSV from {file_path}: {str(e)}")

    def download_from_api(self, timeout: int = 30) -> Optional[pd.DataFrame]:
        """
        Download exoplanet data from NASA Exoplanet Archive API.

        Args:
            timeout: Request timeout in seconds

        Returns:
            DataFrame if successful, None if download fails
        """
        try:
            response = requests.get(
                self.exoplanet_archive_url,
                timeout=timeout,
                headers={'Accept': 'text/csv'}
            )
            response.raise_for_status()

            # Parse CSV from response
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))

            if df.empty:
                return None

            # Save to local cache
            cache_path = self.raw_dir / "downloaded_exoplanet_data.csv"
            df.to_csv(cache_path, index=False)
            print(f"Downloaded and cached {len(df)} exoplanets to {cache_path}")

            return df

        except requests.exceptions.Timeout:
            print(f"Timeout when downloading from NASA Exoplanet Archive (timeout={timeout}s)")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Failed to download from NASA Exoplanet Archive: {str(e)}")
            return None
        except Exception as e:
            print(f"Unexpected error during download: {str(e)}")
            return None

    def load_or_download_exoplanet_archive(self, use_api: bool = False, api_timeout: int = None) -> pd.DataFrame:
        """
        Load exoplanet data with fallback strategy.

        Priority:
        1. If use_api=True, attempt API download first, then fallback to local CSV
        2. If use_api=False, load from local CSV directly
        3. If no local CSV found, return empty DataFrame

        Args:
            use_api: Whether to attempt downloading from API
            api_timeout: Timeout for API requests in seconds (defaults to config value)

        Returns:
            DataFrame with exoplanet data, or empty DataFrame if unavailable
        """
        from app.config import settings

        if api_timeout is None:
            api_timeout = settings.API_TIMEOUT

        self.create_directories()

        # Try API download if requested
        if use_api:
            print("Attempting to download from NASA Exoplanet Archive...")
            api_df = self.download_from_api(timeout=api_timeout)
            if api_df is not None and not api_df.empty:
                return api_df
            print("API download failed, falling back to local CSV...")

        # Look for local CSV files
        csv_candidates = list(self.raw_dir.glob("*.csv"))
        if csv_candidates:
            # Prefer explicitly named sample data
            sample_files = [f for f in csv_candidates if "sample" in f.name.lower()]
            target_file = sample_files[0] if sample_files else csv_candidates[0]

            print(f"Loading local CSV: {target_file.name}")
            return self.load_from_csv(str(target_file))

        print("No local CSV files found in raw data directory")
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
