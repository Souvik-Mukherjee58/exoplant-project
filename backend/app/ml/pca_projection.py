"""2-D PCA projection of the catalog for the anomaly view.

One implementation for both callers: the pipeline writes it to precomputed_pca.json, and the query engine
computes it when an artifact has no such file. Exploratory: outliers are unusual or uncertain catalog
entries, not evidence of anything artificial.
"""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

PCA_FEATURES = [
    "planet_radius",
    "planet_mass",
    "equilibrium_temperature",
    "orbital_period",
    "semi_major_axis",
    "eccentricity",
    "earth_similarity",
    "observational_accessibility",
]
RANDOM_STATE = 42


def rounded_or_none(df: pd.DataFrame, column: str, digits: int) -> List[Optional[float]]:
    """Column values rounded for display; None (never 0.0, never NaN) where a value or the whole column is missing."""
    if column not in df:
        return [None] * len(df)
    return [None if v is None or np.isnan(float(v)) else round(float(v), digits) for v in df[column]]


def _sample(df: pd.DataFrame) -> pd.DataFrame:
    """Up to 500 points: the 200 highest-ranked, the 150 most anomalous and 150 random planets."""
    if len(df) <= 500:
        return df.reset_index(drop=True)
    anomalous = df.nlargest(150, "anomaly_score") if "anomaly_score" in df.columns else df.tail(150)
    parts = [df.head(200), anomalous, df.sample(n=150, random_state=RANDOM_STATE)]
    return pd.concat(parts).drop_duplicates(subset=["planet_name"]).reset_index(drop=True)


def project_catalog(df: pd.DataFrame) -> Dict[str, Any]:
    """PCA of the standardized physical features, with missing values set to the sample median.

    `df` must be in ranking order (the catalog's order). Returns the precomputed_pca.json structure, or
    {"error": ...} when fewer than two features are available.
    """
    features = [c for c in PCA_FEATURES if c in df.columns]
    if len(features) < 2:
        return {"error": "Insufficient features for PCA"}

    sample = _sample(df)
    X = sample[features].apply(pd.to_numeric, errors="coerce")
    X = X.fillna(X.median()).fillna(0.0)  # a column with no value at all becomes 0 after scaling either way

    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    projected = pca.fit_transform(StandardScaler().fit_transform(X))

    return {
        "planets": sample["planet_name"].tolist(),
        "pca_x": [round(float(v), 3) for v in projected[:, 0]],
        "pca_y": [round(float(v), 3) for v in projected[:, 1]],
        "anomaly_score": rounded_or_none(sample, "anomaly_score", 3),
        "priority_score": rounded_or_none(sample, "priority_score", 1),
        "target_priority_score": rounded_or_none(sample, "target_priority_score", 1),
        "hz_status": sample["hz_status"].tolist() if "hz_status" in sample else ["Unknown"] * len(sample),
        "explained_variance": [round(float(v), 4) for v in pca.explained_variance_ratio_],
        "feature_names": features,
    }
