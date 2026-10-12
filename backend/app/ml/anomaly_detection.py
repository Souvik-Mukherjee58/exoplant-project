"""Anomaly detection using Isolation Forest and Local Outlier Factor."""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
import joblib
from pathlib import Path


class AnomalyDetector:
    """Anomaly detection models for exoplanet features."""

    def __init__(self, contamination: float = 0.1, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state
        self.isolation_forest = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=100
        )
        self.lof = LocalOutlierFactor(
            contamination=contamination,
            n_neighbors=20,
            novelty=True
        )
        self.scaler = StandardScaler()
        self.is_fitted = False

    def prepare_features(self, df: pd.DataFrame):
        """Select and prepare features for anomaly detection."""
        feature_cols = [
            "planet_radius", "planet_mass", "equilibrium_temperature",
            "orbital_period", "semi_major_axis", "eccentricity",
            "earth_similarity", "observational_accessibility",
            "planet_radius_zscore", "planet_mass_zscore",
            "equilibrium_temperature_zscore", "orbital_period_zscore"
        ]

        # Only use columns that exist
        available_cols = [col for col in feature_cols if col in df.columns]
        if not available_cols:
            available_cols = [col for col in df.columns if df[col].dtype in ['float64', 'int64', 'float32', 'int32']][:10]

        X = df[available_cols].copy() if available_cols else pd.DataFrame(index=df.index)
        for col in available_cols:
            X[col] = pd.to_numeric(X[col], errors="coerce")
        X = X.fillna(X.median()).fillna(0.0)
        return X, available_cols

    def fit(self, df: pd.DataFrame) -> None:
        """Fit anomaly detection models."""
        X, self.feature_names = self.prepare_features(df)
        if X.empty or len(X) == 0:
            self.is_fitted = True
            return

        X_scaled = self.scaler.fit_transform(X)

        n_samples = len(X)
        n_neighbors = min(20, max(1, n_samples - 1))
        self.lof.set_params(n_neighbors=n_neighbors)

        self.isolation_forest.fit(X_scaled)
        self.lof.fit(X_scaled)
        self.is_fitted = True

    def predict_anomaly_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate anomaly scores (0-1, higher = more anomalous)."""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")

        df = df.copy()
        X, _ = self.prepare_features(df)

        if X.empty or len(X) == 0:
            df["anomaly_score_if"] = 0.5
            df["anomaly_score_lof"] = 0.5
            df["anomaly_score"] = 0.5
            return df

        X_scaled = self.scaler.transform(X)

        # Isolation Forest: anomaly score is negative, so invert and scale to 0-1
        if_scores = self.isolation_forest.decision_function(X_scaled)
        if_min, if_max = if_scores.min(), if_scores.max()
        if if_max > if_min:
            if_anomaly = 1.0 - (if_scores - if_min) / (if_max - if_min)
        else:
            if_anomaly = np.zeros_like(if_scores) + 0.5

        # LOF: negative_outlier_factor, higher = more normal, so invert
        lof_scores = self.lof.decision_function(X_scaled)
        lof_min, lof_max = lof_scores.min(), lof_scores.max()
        if lof_max > lof_min:
            lof_anomaly = 1.0 - (lof_scores - lof_min) / (lof_max - lof_min)
        else:
            lof_anomaly = np.zeros_like(lof_scores) + 0.5

        # Combined anomaly score (average)
        df["anomaly_score_if"] = np.clip(np.nan_to_num(if_anomaly, nan=0.5), 0.0, 1.0)
        df["anomaly_score_lof"] = np.clip(np.nan_to_num(lof_anomaly, nan=0.5), 0.0, 1.0)
        df["anomaly_score"] = np.clip((df["anomaly_score_if"] + df["anomaly_score_lof"]) / 2.0, 0.0, 1.0)

        return df

    def save_model(self, filepath: str) -> None:
        """Save the fitted model."""
        if not self.is_fitted:
            raise ValueError("No fitted model to save")

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            'isolation_forest': self.isolation_forest,
            'lof': self.lof,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'contamination': self.contamination,
            'random_state': self.random_state
        }, filepath)

    def load_model(self, filepath: str) -> None:
        """Load a fitted model."""
        data = joblib.load(filepath)
        self.isolation_forest = data['isolation_forest']
        self.lof = data['lof']
        self.scaler = data['scaler']
        self.feature_names = data['feature_names']
        self.contamination = data['contamination']
        self.random_state = data['random_state']
        self.is_fitted = True
