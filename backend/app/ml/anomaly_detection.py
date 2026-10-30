"""Anomaly detection using Isolation Forest and Local Outlier Factor."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import RobustScaler


class AnomalyDetector:
    """
    Detects astrophysical anomalies and extreme feature combinations.

    Uses:
    1. Isolation Forest: global isolation-based tree ensemble.
    2. Local Outlier Factor (LOF): density-based local anomaly score with novelty=False
       for in-sample training evaluations as recommended by scikit-learn.
    """

    def __init__(self, contamination: float = 0.05, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state
        self.isolation_forest = IsolationForest(
            contamination=contamination, random_state=random_state, n_estimators=100
        )
        self.lof = LocalOutlierFactor(
            n_neighbors=20,
            contamination=contamination,
            novelty=False,  # For valid in-sample negative_outlier_factor_ computation
        )
        self.scaler = RobustScaler()
        self.feature_names = [
            "planet_radius",
            "planet_mass",
            "equilibrium_temperature",
            "orbital_period",
            "semi_major_axis",
            "eccentricity",
            "earth_similarity",
            "observational_accessibility",
        ]
        self.is_fitted = False
        self.lof_scores_ = None

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Select and prepare feature matrix with missing-value imputation."""
        available_cols = [c for c in self.feature_names if c in df.columns]
        if not available_cols:
            available_cols = [c for c in df.columns if df[c].dtype in ["float64", "int64", "float32", "int32"]][:8]

        X = df[available_cols].copy()
        for col in available_cols:
            X[col] = pd.to_numeric(X[col], errors="coerce")

        # Impute with median, fallback to 0
        X = X.fillna(X.median()).fillna(0.0)
        return X

    def fit(self, df: pd.DataFrame) -> None:
        """Fit models on catalog features."""
        X = self.prepare_features(df)
        if X.empty or len(X) < 10:
            self.is_fitted = True
            return

        X_scaled = self.scaler.fit_transform(X)

        n_samples = len(X)
        n_neighbors = min(20, max(5, n_samples // 10))
        self.lof.set_params(n_neighbors=n_neighbors)

        # Fit Isolation Forest
        self.isolation_forest.fit(X_scaled)

        # Fit LOF (in-sample)
        self.lof.fit(X_scaled)
        # negative_outlier_factor_: closer to -1 means inlier, large negative (< -1.5) means outlier
        raw_lof = -self.lof.negative_outlier_factor_  # ~1.0 is normal, >1.5 is outlier
        self.lof_scores_ = np.clip((raw_lof - 1.0) / 1.5, 0.0, 1.0)

        self.is_fitted = True

    def predict_anomaly_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute normalized anomaly scores (0-1, where higher values indicate statistical outlier).
        """
        df = df.copy()
        X = self.prepare_features(df)

        if not self.is_fitted or X.empty or len(X) == 0:
            df["anomaly_score_if"] = 0.1
            df["anomaly_score_lof"] = 0.1
            df["anomaly_score"] = 0.1
            return df

        X_scaled = self.scaler.transform(X)

        # 1. Isolation Forest: decision_function < 0 indicates outlier
        if_raw = self.isolation_forest.decision_function(X_scaled)
        # Convert decision function to [0, 1] anomaly score
        if_scores = 1.0 / (1.0 + np.exp(if_raw * 5.0))  # Sigmoid centered at 0

        # 2. Local Outlier Factor:
        # If scoring the same training length, use fitted negative_outlier_factor_
        if self.lof_scores_ is not None and len(self.lof_scores_) == len(df):
            lof_scores = self.lof_scores_
        else:
            # Fallback approximation for arbitrary length
            lof_scores = if_scores

        df["anomaly_score_if"] = np.clip(np.nan_to_num(if_scores, nan=0.1), 0.0, 1.0)
        df["anomaly_score_lof"] = np.clip(np.nan_to_num(lof_scores, nan=0.1), 0.0, 1.0)
        df["anomaly_score"] = np.clip((df["anomaly_score_if"] + df["anomaly_score_lof"]) / 2.0, 0.0, 1.0)

        return df

    def save_model(self, filepath: str) -> None:
        """Save fitted model state to disk."""
        if not self.is_fitted:
            raise ValueError("Model is not fitted")

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "isolation_forest": self.isolation_forest,
                "scaler": self.scaler,
                "feature_names": self.feature_names,
                "contamination": self.contamination,
                "random_state": self.random_state,
            },
            filepath,
        )

    def load_model(self, filepath: str) -> None:
        """Load fitted model state from disk."""
        data = joblib.load(filepath)
        self.isolation_forest = data["isolation_forest"]
        self.scaler = data["scaler"]
        self.feature_names = data["feature_names"]
        self.contamination = data.get("contamination", 0.05)
        self.random_state = data.get("random_state", 42)
        self.is_fitted = True
