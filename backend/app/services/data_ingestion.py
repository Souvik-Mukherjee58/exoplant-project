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
            "select+pl_name,pl_rade,pl_bmasse,pl_orbper,pl_orbsmax,pl_eqt,pl_orbeccen,"
            "st_teff,st_rad,st_mass,st_met,st_lum,sy_dist,sy_jmag,sy_kmag,"
            "discoverymethod,disc_year,tran_flag+from+pscomppars&format=csv"
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

    def download_from_api(self, timeout: int = 60) -> Optional[pd.DataFrame]:
        """
        Download exoplanet data from NASA Exoplanet Archive TAP API.

        Args:
            timeout: Request timeout in seconds

        Returns:
            DataFrame if successful, None if download fails
        """
        import hashlib
        import datetime
        from io import StringIO

        try:
            response = requests.get(
                self.exoplanet_archive_url,
                timeout=timeout,
                headers={"Accept": "text/csv"}
            )
            response.raise_for_status()

            df = pd.read_csv(StringIO(response.text))
            if df.empty:
                return None

            # Save snapshot and manifest
            self.create_directories()
            cache_path = self.raw_dir / "nasa_exoplanet_archive.csv"
            sha256 = hashlib.sha256(response.content).hexdigest()

            with open(cache_path, "wb") as f:
                f.write(response.content)

            manifest = {
                "source": "NASA Exoplanet Archive (pscomppars table via TAP)",
                "url": self.exoplanet_archive_url,
                "download_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "sha256": sha256,
                "row_count": len(df),
                "file": cache_path.name
            }
            with open(self.raw_dir / "manifest.json", "w") as f:
                json.dump(manifest, f, indent=2)

            print(f"Downloaded and cached {len(df)} planets to {cache_path} (SHA256: {sha256[:12]}...)")
            return df

        except Exception as e:
            print(f"Failed to download from NASA Exoplanet Archive TAP: {str(e)}")
            return None

    def load_or_download_exoplanet_archive(self, use_api: bool = False, api_timeout: int = None) -> pd.DataFrame:
        """
        Load exoplanet data with fallback strategy.

        Priority:
        1. If local nasa_exoplanet_archive.csv exists and not use_api, load it directly
        2. If use_api=True or local archive missing, download via NASA TAP API
        3. Fallback to any local CSV candidate
        """
        from app.config import settings

        if api_timeout is None:
            api_timeout = settings.API_TIMEOUT

        self.create_directories()

        # Primary archive snapshot file
        primary_file = self.raw_dir / "nasa_exoplanet_archive.csv"
        if primary_file.exists() and not use_api:
            print(f"Loading local NASA archive snapshot: {primary_file.name}")
            return self.load_from_csv(str(primary_file))

        # Try API download if requested or file missing
        if use_api or not primary_file.exists():
            print("Attempting to download from NASA Exoplanet Archive TAP...")
            api_df = self.download_from_api(timeout=api_timeout)
            if api_df is not None and not api_df.empty:
                return api_df
            print("API download failed or unavailable, checking local files...")

        # Fallback to any local CSV file
        csv_candidates = list(self.raw_dir.glob("*.csv"))
        if csv_candidates:
            # Prefer nasa_exoplanet_archive if it was found
            target_file = primary_file if primary_file.exists() else csv_candidates[0]
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
