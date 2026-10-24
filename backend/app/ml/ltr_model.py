"""Learning-to-Rank (LTR) model for exoplanet spectroscopic follow-up prioritization.

Implements production-grade supervised ranking:
1. Feature engineering pipeline with Chen & Kipping (2017) mass-radius imputation
   and derived physical interaction terms.
2. LightGBM GBDT ranking model trained on historical observations (<=2017),
   calibrated against published astronomical ground truth (Kempton et al. 2018 TSM).
3. Feature importance analysis (Gain and Split importance).
4. Score calibration to 0-100 scale, rank delta computation against heuristic baselines.
5. Model persistence and serving integration.
"""

from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.preprocessing import RobustScaler

from app.ml.ground_truth import estimate_planet_mass, generate_ground_truth_labels
from app.ml.evaluation import (
    split_temporal_dataset,
    precision_at_k,
    recall_at_k,
    ndcg_at_k,
    mean_average_precision,
    pr_auc_score
)


# Core physical and derived interaction features used by the ranker
LTR_FEATURE_NAMES: List[str] = [
    # Primary physical dimensions
    "planet_radius",
    "planet_mass",
    "orbital_period",
    "semi_major_axis",
    "equilibrium_temperature",
    "stellar_effective_temperature",
    "stellar_radius",
    "stellar_mass",
    "stellar_metallicity",
    "distance",
    "j_magnitude",
    "k_magnitude",
    "earth_similarity",
    # Derived astrophysical interaction features
    "transit_depth_proxy",       # (R_p / R_*)^2
    "scale_height_proxy",        # T_eq * R_p^2 / M_p
    "transmission_snr_proxy",    # (R_p * H) / (R_*^2) * 10^(-m_J / 5)
    "bulk_density_proxy",        # M_p / R_p^3
    "insolation_flux",           # L_* / a^2
    "distance_attenuation",      # 1 / (1 + d / 100)
    "infrared_brightness_proxy", # 10^(-m_K / 5)
    "hz_proximity_score"         # Continuous Habitable Zone score
]


class LTRFeatureExtractor:
    """Extracts and standardizes physical and interaction features for ranking."""

    def __init__(self):
        self.feature_names = LTR_FEATURE_NAMES
        self.scaler = RobustScaler()
        self.median_impute_values: Dict[str, float] = {}
        self.is_fitted = False

    def _extract_raw_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Derive physical interaction terms and handle missing values."""
        df = df.copy()

        # 1. Planet Mass with Chen & Kipping fallback
        r_p = pd.to_numeric(df.get("planet_radius", pd.Series(np.nan, index=df.index)), errors="coerce")
        m_p = pd.to_numeric(df.get("planet_mass", pd.Series(np.nan, index=df.index)), errors="coerce")

        missing_mass = m_p.isna() | (m_p <= 0)
        estimated_masses = r_p[missing_mass].apply(estimate_planet_mass)
        m_p = m_p.copy()
        m_p[missing_mass] = estimated_masses

        # Core parameters
        p_orb = pd.to_numeric(df.get("orbital_period", pd.Series(np.nan, index=df.index)), errors="coerce")
        sma = pd.to_numeric(df.get("semi_major_axis", pd.Series(np.nan, index=df.index)), errors="coerce")
        teq = pd.to_numeric(df.get("equilibrium_temperature", pd.Series(np.nan, index=df.index)), errors="coerce")
        t_star = pd.to_numeric(df.get("stellar_effective_temperature", pd.Series(np.nan, index=df.index)), errors="coerce")
        r_star = pd.to_numeric(df.get("stellar_radius", pd.Series(np.nan, index=df.index)), errors="coerce")
        m_star = pd.to_numeric(df.get("stellar_mass", pd.Series(np.nan, index=df.index)), errors="coerce")
        fe_h = pd.to_numeric(df.get("stellar_metallicity", pd.Series(np.nan, index=df.index)), errors="coerce")
        dist = pd.to_numeric(df.get("distance", pd.Series(np.nan, index=df.index)), errors="coerce")
        jmag = pd.to_numeric(df.get("j_magnitude", pd.Series(np.nan, index=df.index)), errors="coerce")
        kmag = pd.to_numeric(df.get("k_magnitude", pd.Series(np.nan, index=df.index)), errors="coerce")
        esi = pd.to_numeric(df.get("earth_similarity", pd.Series(np.nan, index=df.index)), errors="coerce")

        # Fallback magnitude resolution
        jmag = jmag.fillna(kmag + 0.8)
        kmag = kmag.fillna(jmag - 0.8)

        # 2. Derived interaction features
        # Earth to Solar radius ratio ~ 0.009168
        rp_rs_ratio = (r_p * 0.009168) / np.maximum(0.01, r_star)
        transit_depth_proxy = np.clip(rp_rs_ratio ** 2, 0.0, 0.1)

        safe_mass = np.maximum(0.01, m_p)
        safe_radius = np.maximum(0.01, r_p)
        bulk_density_proxy = np.clip(safe_mass / (safe_radius ** 3), 0.01, 100.0)

        # Atmospheric scale height H propto T_eq / g propto T_eq * R_p^2 / M_p
        scale_height_proxy = np.clip((teq * (safe_radius ** 2)) / safe_mass, 0.0, 50000.0)

        # Transmission SNR proxy ~ (R_p * H) / R_*^2 * 10^(-m_J / 5)
        trans_geom = (r_p * scale_height_proxy) / (np.maximum(0.01, r_star) ** 2)
        flux_factor_j = 10.0 ** (-np.clip(jmag.fillna(14.0), 0.0, 25.0) / 5.0)
        transmission_snr_proxy = np.clip(trans_geom * flux_factor_j * 0.001, 0.0, 1000.0)

        # Insolation flux L / a^2 (using Stefan-Boltzmann L ~ R_*^2 * (T_*/5780)^4)
        stellar_lum = (np.maximum(0.01, r_star) ** 2) * ((np.maximum(1000.0, t_star) / 5780.0) ** 4)
        insolation_flux = np.clip(stellar_lum / (np.maximum(0.001, sma) ** 2), 0.001, 10000.0)

        # Distance attenuation
        distance_attenuation = np.where(dist.notna() & (dist >= 0), 1.0 / (1.0 + dist / 100.0), 0.1)

        # Infrared brightness proxy
        infrared_brightness_proxy = 10.0 ** (-np.clip(kmag.fillna(14.0), 0.0, 25.0) / 5.0)

        # Habitable zone continuous proximity
        hz_mapping = {"Inside HZ": 1.0, "Near HZ": 0.65, "Outside HZ": 0.15, "Insufficient data": 0.30}
        hz_status = df.get("hz_status", pd.Series("Insufficient data", index=df.index)).astype(str)
        hz_proximity_score = hz_status.map(hz_mapping).fillna(0.30)

        features_df = pd.DataFrame({
            "planet_radius": r_p,
            "planet_mass": m_p,
            "orbital_period": p_orb,
            "semi_major_axis": sma,
            "equilibrium_temperature": teq,
            "stellar_effective_temperature": t_star,
            "stellar_radius": r_star,
            "stellar_mass": m_star,
            "stellar_metallicity": fe_h,
            "distance": dist,
            "j_magnitude": jmag,
            "k_magnitude": kmag,
            "earth_similarity": esi.fillna(0.3),
            "transit_depth_proxy": transit_depth_proxy,
            "scale_height_proxy": scale_height_proxy,
            "transmission_snr_proxy": transmission_snr_proxy,
            "bulk_density_proxy": bulk_density_proxy,
            "insolation_flux": insolation_flux,
            "distance_attenuation": distance_attenuation,
            "infrared_brightness_proxy": infrared_brightness_proxy,
            "hz_proximity_score": hz_proximity_score,
        }, index=df.index)

        return features_df

    def fit(self, df: pd.DataFrame) -> "LTRFeatureExtractor":
        """Fit scaler and store median imputation benchmarks on training set."""
        raw_feats = self._extract_raw_features(df)
        self.median_impute_values = raw_feats.median().to_dict()

        imputed_feats = raw_feats.fillna(self.median_impute_values).fillna(0.0)
        self.scaler.fit(imputed_feats)
        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Transform dataframe into scaled feature matrix."""
        if not self.is_fitted:
            raise ValueError("LTRFeatureExtractor must be fitted before transform")

        raw_feats = self._extract_raw_features(df)
        imputed_feats = raw_feats.fillna(self.median_impute_values).fillna(0.0)
        scaled = self.scaler.transform(imputed_feats)
        return scaled


class ExoSignalLTRModel:
    """
    Supervised Learning-to-Rank (LTR) model for exoplanet prioritization.

    Uses LightGBM gradient boosted decision trees calibrated against
    astronomical ground truth (Kempton et al. 2018 TSM & approved JWST programs).
    """

    def __init__(
        self,
        n_estimators: int = 150,
        learning_rate: float = 0.04,
        num_leaves: int = 31,
        max_depth: int = 5,
        min_child_samples: int = 20,
        subsample: float = 0.85,
        colsample_bytree: float = 0.85,
        random_state: int = 42
    ):
        self.hyperparameters = {
            "n_estimators": n_estimators,
            "learning_rate": learning_rate,
            "num_leaves": num_leaves,
            "max_depth": max_depth,
            "min_child_samples": min_child_samples,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "random_state": random_state,
        }
        self.feature_extractor = LTRFeatureExtractor()
        self.model = lgb.LGBMClassifier(
            objective="binary",
            metric=["binary_logloss", "auc"],
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            num_leaves=num_leaves,
            max_depth=max_depth,
            min_child_samples=min_child_samples,
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            random_state=random_state,
            verbose=-1,
            n_jobs=2
        )
        self.is_fitted = False
        self.training_metadata: Dict[str, Any] = {}
        self.feature_importances: Dict[str, Any] = {}

    def fit(
        self,
        train_df: pd.DataFrame,
        val_df: Optional[pd.DataFrame] = None
    ) -> "ExoSignalLTRModel":
        """
        Train LTR model on historical exoplanet observations with early stopping.

        Args:
            train_df: Historical dataset (Discovery <= 2017) with ground-truth labels
            val_df: Optional validation dataset (Discovery 2018-2021) for early stopping
        """
        # Ensure ground truth labels exist
        if "ground_truth_binary" not in train_df.columns:
            train_df = generate_ground_truth_labels(train_df)

        self.feature_extractor.fit(train_df)
        X_train = self.feature_extractor.transform(train_df)
        y_train = train_df["ground_truth_binary"].to_numpy()

        import warnings

        eval_set = None
        callbacks = []
        if val_df is not None:
            if "ground_truth_binary" not in val_df.columns:
                val_df = generate_ground_truth_labels(val_df)
            X_val = self.feature_extractor.transform(val_df)
            y_val = val_df["ground_truth_binary"].to_numpy()
            eval_set = [(X_val, y_val)]
            callbacks = [lgb.early_stopping(stopping_rounds=20, verbose=False)]

        # Fit LightGBM
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.model.fit(
                X_train,
                y_train,
                eval_set=eval_set,
                callbacks=callbacks
            )
        self.is_fitted = True

        # Compute feature importances
        split_importances = self.model.feature_importances_
        gain_importances = self.model.booster_.feature_importance(importance_type="gain")
        total_gain = float(np.sum(gain_importances)) if np.sum(gain_importances) > 0 else 1.0

        names = self.feature_extractor.feature_names
        importance_list = []
        for i, name in enumerate(names):
            importance_list.append({
                "feature": name,
                "split_count": int(split_importances[i]),
                "gain": round(float(gain_importances[i]), 2),
                "gain_percentage": round(float(gain_importances[i] / total_gain * 100.0), 2)
            })

        # Sort descending by gain
        importance_list.sort(key=lambda x: x["gain"], reverse=True)
        self.feature_importances = {
            "total_features": len(names),
            "top_features": importance_list[:10],
            "all_features": importance_list
        }

        self.training_metadata = {
            "algorithm": "LightGBM Supervised Learning-to-Rank GBDT",
            "hyperparameters": self.hyperparameters,
            "train_samples": len(train_df),
            "train_positive_rate": round(float(np.mean(y_train)), 4),
            "best_iteration": int(self.model.best_iteration_ if hasattr(self.model, "best_iteration_") else self.hyperparameters["n_estimators"]),
            "val_samples": len(val_df) if val_df is not None else 0
        }

        return self

    def predict_raw_scores(self, df: pd.DataFrame) -> np.ndarray:
        """Predict continuous probability scores P(y=1) in [0.0, 1.0]."""
        if not self.is_fitted:
            raise ValueError("ExoSignalLTRModel must be fitted before predict")
        X = self.feature_extractor.transform(df)
        probs = self.model.predict_proba(X)[:, 1]
        return probs

    def predict_priority_scores(self, df: pd.DataFrame) -> np.ndarray:
        """
        Output calibrated priority scores on [0.0, 100.0] scale.

        Applies monotonic percentile-preserving transformation for fluid UI presentation.
        """
        raw_probs = self.predict_raw_scores(df)
        # Scale to 0-100 with smooth distribution spread
        scores = np.clip(raw_probs * 100.0, 0.0, 100.0)
        return np.round(scores, 1)

    def score_catalog(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Augment catalog with LTR priority scores, rankings, and comparison metrics.

        Adds:
        - ml_priority_score: Calibrated 0-100 LTR score
        - ml_rank: Integer rank (1 = highest priority target)
        - heuristic_rank: Legacy rank based on target_priority_score
        - rank_delta: (heuristic_rank - ml_rank) -> positive value means LTR elevated target
        """
        df = df.copy()
        scores = self.predict_priority_scores(df)
        df["ml_priority_score"] = scores

        # Compute ML rank
        df["ml_rank"] = df["ml_priority_score"].rank(ascending=False, method="min").astype(int)

        # Compute Heuristic rank if target_priority_score exists
        if "target_priority_score" in df.columns:
            df["heuristic_rank"] = df["target_priority_score"].rank(ascending=False, method="min").astype(int)
            df["rank_delta"] = df["heuristic_rank"] - df["ml_rank"]
        else:
            df["heuristic_rank"] = df["ml_rank"]
            df["rank_delta"] = 0

        return df

    def evaluate(self, test_df: pd.DataFrame) -> Dict[str, Any]:
        """Evaluate LTR model against ground truth on test split."""
        if "ground_truth_binary" not in test_df.columns:
            test_df = generate_ground_truth_labels(test_df)

        y_true_binary = test_df["ground_truth_binary"].to_numpy()
        y_true_graded = test_df["ground_truth_graded"].to_numpy()
        scores = self.predict_raw_scores(test_df)

        return {
            "model_name": "Supervised LightGBM LTR Ranker",
            "test_samples": len(test_df),
            "precision@5": round(precision_at_k(y_true_binary, scores, k=5), 4),
            "precision@10": round(precision_at_k(y_true_binary, scores, k=10), 4),
            "precision@20": round(precision_at_k(y_true_binary, scores, k=20), 4),
            "recall@10": round(recall_at_k(y_true_binary, scores, k=10), 4),
            "recall@20": round(recall_at_k(y_true_binary, scores, k=20), 4),
            "ndcg@5": round(ndcg_at_k(y_true_graded, scores, k=5), 4),
            "ndcg@10": round(ndcg_at_k(y_true_graded, scores, k=10), 4),
            "ndcg@20": round(ndcg_at_k(y_true_graded, scores, k=20), 4),
            "map": round(mean_average_precision(y_true_binary, scores), 4),
            "pr_auc": round(pr_auc_score(y_true_binary, scores), 4)
        }

    def save(self, filepath: str) -> None:
        """Serialize model bundle, extractor, and metadata to disk."""
        if not self.is_fitted:
            raise ValueError("Cannot save unfitted model")

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        bundle = {
            "model": self.model,
            "feature_extractor": self.feature_extractor,
            "hyperparameters": self.hyperparameters,
            "training_metadata": self.training_metadata,
            "feature_importances": self.feature_importances
        }
        joblib.dump(bundle, str(path))

    @classmethod
    def load(cls, filepath: str) -> "ExoSignalLTRModel":
        """Deserialize model bundle from disk."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"LTR model artifact not found at {path}")

        bundle = joblib.load(str(path))
        instance = cls(**bundle["hyperparameters"])
        instance.model = bundle["model"]
        instance.feature_extractor = bundle["feature_extractor"]
        instance.training_metadata = bundle["training_metadata"]
        instance.feature_importances = bundle["feature_importances"]
        instance.is_fitted = True
        return instance
