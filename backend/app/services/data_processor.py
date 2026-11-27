"""Data processing pipeline with caching for ExoSignal."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from app.config import settings
from app.ml.anomaly_detection import AnomalyDetector
from app.scoring.priority_scorer import TargetPriorityScorer
from app.services.data_cleaning import DataCleaning
from app.services.data_ingestion import DataIngestion
from app.services.feature_engineering import FeatureEngineering

logger = logging.getLogger(__name__)


class DataProcessor:
    """Orchestrates the full data processing pipeline with caching."""

    def __init__(self, raw_dir: Optional[str] = None, processed_dir: Optional[str] = None):
        self.raw_dir = Path(raw_dir or settings.RAW_DATA_DIR)
        self.processed_dir = Path(processed_dir or settings.PROCESSED_DATA_DIR)
        self.processed_file = self.processed_dir / "processed_exoplanets.csv"
        self.metadata_file = self.processed_dir / "processing_metadata.json"

        self.ingestion = DataIngestion(str(self.raw_dir), str(self.processed_dir))
        self.cleaner = DataCleaning()
        self.feature_eng = FeatureEngineering()
        self.anomaly_detector = AnomalyDetector(
            contamination=settings.ANOMALY_CONTAMINATION, random_state=settings.RANDOM_STATE
        )
        self.scorer = TargetPriorityScorer()

        self._cached_df: Optional[pd.DataFrame] = None
        self._metadata: Optional[Dict[str, Any]] = None

    def create_directories(self) -> None:
        """Create necessary directories."""
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def is_cache_valid(self) -> bool:
        """Check if cached processed data exists and is valid."""
        if not self.processed_file.exists() or not self.metadata_file.exists():
            return False

        try:
            with open(self.metadata_file, "r") as f:
                self._metadata = json.load(f)

            # Check if raw data has been modified since processing
            csv_files = list(self.raw_dir.glob("*.csv"))
            if not csv_files:
                return False

            latest_raw_mtime = max(f.stat().st_mtime for f in csv_files)
            processed_mtime = self.processed_file.stat().st_mtime

            return latest_raw_mtime <= processed_mtime
        except (OSError, ValueError):  # unreadable or invalid metadata: rebuild
            return False

    def load_cached_data(self) -> pd.DataFrame:
        """Load processed data from cache."""
        if self._cached_df is not None:
            return self._cached_df

        df = pd.read_csv(self.processed_file)
        self._cached_df = df

        with open(self.metadata_file, "r") as f:
            self._metadata = json.load(f)

        return df

    def save_processed_data(self, df: pd.DataFrame) -> None:
        """Save processed data and metadata to cache."""
        self.create_directories()
        df.to_csv(self.processed_file, index=False)

        metadata = {
            "num_planets": len(df),
            "columns": list(df.columns),
            "processed_at": pd.Timestamp.now().isoformat(),
            "version": "1.0",
        }
        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        self._cached_df = df
        self._metadata = metadata

    def process_full_pipeline(self, use_api: bool = False) -> pd.DataFrame:
        """Run the full data processing pipeline."""
        print("Loading raw data...")
        df = self.ingestion.load_or_download_exoplanet_archive(use_api=use_api)

        if df.empty:
            raise ValueError("No exoplanet data available. Please ensure sample data exists in data/raw/")

        print(f"Loaded {len(df)} raw records")

        print("Cleaning data...")
        df = self.cleaner.clean(df)

        print("Engineering features...")
        df = self.feature_eng.transform(df)

        print("Running anomaly detection...")
        self.anomaly_detector.fit(df)
        df = self.anomaly_detector.predict_anomaly_scores(df)

        print("Calculating priority scores...")
        df = self.scorer.score(df)

        print("Sorting by priority score...")
        if "eligible_for_transmission" in df.columns:
            eligible_mask = df["eligible_for_transmission"] == True
            df["heuristic_rank"] = np.nan
            df.loc[eligible_mask, "heuristic_rank"] = (
                df.loc[eligible_mask, "target_priority_score"].rank(ascending=False, method="first").astype(int)
            )
            df = pd.concat(
                [
                    df[eligible_mask].sort_values("target_priority_score", ascending=False),
                    df[~eligible_mask].sort_values("target_priority_score", ascending=False),
                ]
            ).reset_index(drop=True)
        else:
            df = df.sort_values("target_priority_score", ascending=False).reset_index(drop=True)

        print("Saving processed data...")
        self.save_processed_data(df)

        print(f"Pipeline complete. {len(df)} planets processed.")
        return df

    def get_processed_data(self, force_refresh: bool = False, use_api: bool = False) -> pd.DataFrame:
        """Get processed data, using memory cache if available."""
        if self._cached_df is not None and not force_refresh:
            return self._cached_df

        try:
            from app.services.query_engine import CatalogQueryEngine

            engine = CatalogQueryEngine.get_instance()
            if engine.conn is not None:
                df = engine.conn.execute("SELECT * FROM planets").df()
                self._cached_df = df
                return df
        except Exception:  # noqa: BLE001 - logged at debug with traceback; expected without an artifact
            # Expected in pipeline and script runs, where no artifact is loaded yet.
            logger.debug("Query engine unavailable; using the processed-data cache or the pipeline", exc_info=True)

        if not force_refresh and self.is_cache_valid():
            print("Loading from cache...")
            return self.load_cached_data()

        print("Cache invalid or missing, running full pipeline...")
        return self.process_full_pipeline(use_api=use_api)


_processor: Optional[DataProcessor] = None


def get_data_processor() -> DataProcessor:
    """Get or create the global data processor instance."""
    global _processor
    if _processor is None:
        _processor = DataProcessor()
    return _processor
