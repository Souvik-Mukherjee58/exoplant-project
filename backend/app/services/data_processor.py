"""Data processing pipeline with caching for ExoSignal."""

import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any

from app.config import settings
from app.services.data_ingestion import DataIngestion
from app.services.data_cleaning import DataCleaning
from app.services.feature_engineering import FeatureEngineering
from app.ml.anomaly_detection import AnomalyDetector
from app.scoring.priority_scorer import TargetPriorityScorer


class DataProcessor:
    """Orchestrates the full data processing pipeline with caching."""

    def __init__(self, raw_dir: str = None, processed_dir: str = None):
        self.raw_dir = Path(raw_dir or settings.RAW_DATA_DIR)
        self.processed_dir = Path(processed_dir or settings.PROCESSED_DATA_DIR)
        self.processed_file = self.processed_dir / "processed_exoplanets.csv"
        self.metadata_file = self.processed_dir / "processing_metadata.json"

        self.ingestion = DataIngestion(str(self.raw_dir), str(self.processed_dir))
        self.cleaner = DataCleaning()
        self.feature_eng = FeatureEngineering()
        self.anomaly_detector = AnomalyDetector(
            contamination=settings.ANOMALY_CONTAMINATION,
            random_state=settings.RANDOM_STATE
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
            with open(self.metadata_file, 'r') as f:
                self._metadata = json.load(f)

            # Check if raw data has been modified since processing
            csv_files = list(self.raw_dir.glob("*.csv"))
            if not csv_files:
                return False

            latest_raw_mtime = max(f.stat().st_mtime for f in csv_files)
            processed_mtime = self.processed_file.stat().st_mtime

            return latest_raw_mtime <= processed_mtime
        except Exception:
            return False

    def load_cached_data(self) -> pd.DataFrame:
        """Load processed data from cache."""
        if self._cached_df is not None:
            return self._cached_df

        df = pd.read_csv(self.processed_file)
        self._cached_df = df

        with open(self.metadata_file, 'r') as f:
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
            "version": "1.0"
        }
        with open(self.metadata_file, 'w') as f:
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
        df = df.sort_values("target_priority_score", ascending=False).reset_index(drop=True)

        print("Saving processed data...")
        self.save_processed_data(df)

        print(f"Pipeline complete. {len(df)} planets processed.")
        return df

    def get_processed_data(self, force_refresh: bool = False, use_api: bool = False) -> pd.DataFrame:
        """Get processed data, using cache if available and valid."""
        if not force_refresh and self.is_cache_valid():
            print("Loading from cache...")
            return self.load_cached_data()

        print("Cache invalid or missing, running full pipeline...")
        return self.process_full_pipeline(use_api=use_api)

    def get_planet_by_name(self, planet_name: str) -> Optional[pd.Series]:
        """Get a specific planet by name (case-insensitive exact match)."""
        df = self.get_processed_data()
        normalized = planet_name.strip().casefold()
        matches = df[df["planet_name"].astype(str).str.strip().str.casefold() == normalized]
        if matches.empty:
            return None
        return matches.iloc[0]

    def search_planets(self, query: str, limit: int = 50) -> pd.DataFrame:
        """Search planets by substring match on name without regex interpretation."""
        df = self.get_processed_data()
        normalized = query.strip().casefold()
        matches = df[df["planet_name"].astype(str).str.casefold().str.contains(normalized, na=False, regex=False)]
        return matches.head(limit)

    def get_top_targets(self, limit: int = 10, min_priority: float = 0.0) -> pd.DataFrame:
        """Get top priority targets."""
        df = self.get_processed_data()
        df = df[df["target_priority_score"] >= min_priority]
        result = df.head(limit)
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get system-wide statistics including real priority histogram."""
        df = self.get_processed_data()

        # Compute empirical priority score histogram across standard 20-point bins
        scores = df["target_priority_score"].dropna()
        counts, bin_edges = np.histogram(scores, bins=[0, 20, 40, 60, 80, 100])
        priority_histogram = [
            {"range": f"{int(bin_edges[i])}-{int(bin_edges[i+1])}", "count": int(counts[i])}
            for i in range(len(counts))
        ]

        return {
            "total_planets": len(df),
            "score_distribution": {
                "min": float(df["target_priority_score"].min()),
                "max": float(df["target_priority_score"].max()),
                "mean": float(df["target_priority_score"].mean()),
                "median": float(df["target_priority_score"].median()),
                "std": float(df["target_priority_score"].std())
            },
            "priority_histogram": priority_histogram,
            "anomaly_distribution": {
                "min": float(df["anomaly_score"].min()),
                "max": float(df["anomaly_score"].max()),
                "mean": float(df["anomaly_score"].mean()),
                "median": float(df["anomaly_score"].median())
            },
            "hz_distribution": df["hz_status"].value_counts().to_dict(),
            "discovery_method_distribution": df["discovery_method"].value_counts().to_dict(),
        }

    def get_anomaly_pca_data(self) -> Dict[str, Any]:
        """Get PCA data for anomaly visualization."""
        df = self.get_processed_data()

        # Select features for PCA
        feature_cols = [
            "planet_radius", "planet_mass", "equilibrium_temperature",
            "orbital_period", "semi_major_axis", "eccentricity",
            "earth_similarity", "observational_accessibility",
        ]

        available_cols = [col for col in feature_cols if col in df.columns]
        if len(available_cols) < 2:
            return {"error": "Insufficient features for PCA"}

        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler

        X = df[available_cols].fillna(df[available_cols].median())
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        pca = PCA(n_components=2)
        X_pca = pca.fit_transform(X_scaled)

        return {
            "planets": df["planet_name"].tolist(),
            "pca_x": X_pca[:, 0].tolist(),
            "pca_y": X_pca[:, 1].tolist(),
            "anomaly_score": df["anomaly_score"].tolist(),
            "target_priority_score": df["target_priority_score"].tolist(),
            "hz_status": df["hz_status"].tolist(),
            "explained_variance": pca.explained_variance_ratio_.tolist(),
            "feature_names": available_cols
        }


# Global processor instance
_processor: Optional[DataProcessor] = None


def get_data_processor() -> DataProcessor:
    """Get or create the global data processor instance."""
    global _processor
    if _processor is None:
        _processor = DataProcessor()
    return _processor