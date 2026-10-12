"""Test data ingestion functionality."""

import os
import tempfile
import pandas as pd
from app.services.data_ingestion import DataIngestion
from app.services.data_cleaning import DataCleaning


def test_load_sample_csv():
    """Test loading sample CSV data."""
    ingestion = DataIngestion()

    # Load the sample CSV
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'sample_exoplanet_data.csv')
    df = ingestion.load_from_csv(path)

    assert not df.empty
    assert len(df) == 10  # 10 planets in sample data
    assert 'planet_name' in df.columns
    print(f"✓ Loaded {len(df)} planets from sample CSV")


def test_data_cleaning():
    """Test data cleaning pipeline."""
    ingestion = DataIngestion()
    cleaner = DataCleaning()

    # Load sample data
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'sample_exoplanet_data.csv')
    df = ingestion.load_from_csv(path)

    # Clean
    cleaned = cleaner.clean(df)

    # Verify it's not empty
    assert not cleaned.empty
    assert len(cleaned) > 0

    # Verify no invalid name values
    assert not cleaned['planet_name'].str.lower().isin(['null', 'none']).any()

    print(f"✓ Data cleaning processed {len(df)} -> {len(cleaned)} records")


def test_feature_engineering():
    """Test feature engineering pipeline."""
    ingestion = DataIngestion()
    fe = __import__('app.services.feature_engineering', fromlist=['FeatureEngineering']).FeatureEngineering()

    # Load sample data
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'sample_exoplanet_data.csv')
    df = ingestion.load_from_csv(path)

    # Clean first
    cleaner = DataCleaning()
    df = cleaner.clean(df)

    # Apply features
    df_fe = fe.transform(df)

    # Verify new features exist
    assert 'earth_similarity' in df_fe.columns
    assert 'hz_status' in df_fe.columns
    assert 'observational_accessibility' in df_fe.columns

    print(f"✓ Feature engineering added {len(df_fe.columns)} total columns")


def test_ml_anomaly_detection():
    """Test ML anomaly detection."""
    from app.ml.anomaly_detection import AnomalyDetector

    ingestion = DataIngestion()
    cleaner = DataCleaning()
    fe = __import__('app.services.feature_engineering', fromlist=['FeatureEngineering']).FeatureEngineering()

    # Load and process sample data
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'sample_exoplanet_data.csv')
    df = ingestion.load_from_csv(path)
    df = cleaner.clean(df)
    df = fe.transform(df)

    # Fit anomaly detector
    detector = AnomalyDetector(contamination=0.2, random_state=42)
    detector.fit(df)

    # Predict scores
    df_scores = detector.predict_anomaly_scores(df)

    # Verify scores exist
    assert 'anomaly_score' in df_scores.columns
    assert 'anomaly_score_if' in df_scores.columns
    assert 'anomaly_score_lof' in df_scores.columns

    # Verify scores are in 0-1 range
    assert df_scores['anomaly_score'].max() <= 1.0
    assert df_scores['anomaly_score'].min() >= 0.0

    print(f"✓ ML anomaly detection: {len(df_scores)} planets scored")


if __name__ == "__main__":
    test_load_sample_csv()
    test_data_cleaning()
    test_feature_engineering()
    test_ml_anomaly_detection()
    print("\nAll ingestion tests passed!")