"""Test priority scoring functionality."""

import pandas as pd
import numpy as np
from app.scoring.priority_scorer import TargetPriorityScorer

def test_priority_scorer():
    """Test that the priority scorer works correctly."""
    # Create sample data
    data = {
        'planet_name': ['Test Planet 1', 'Test Planet 2'],
        'planet_radius': [1.0, 2.5],
        'planet_mass': [1.0, 5.0],
        'equilibrium_temperature': [288.0, 350.0],
        'orbital_period': [365.0, 100.0],
        'semi_major_axis': [1.0, 0.5],
        'eccentricity': [0.01, 0.1],
        'stellar_effective_temperature': [5778.0, 4000.0],
        'stellar_radius': [1.0, 0.5],
        'stellar_mass': [1.0, 0.5],
        'stellar_metallicity': [0.0, -0.5],
        'distance': [10.0, 50.0],
        'discovery_method': ['Transit', 'Radial Velocity']
    }
    df = pd.DataFrame(data)

    # Test scorer
    scorer = TargetPriorityScorer()
    result = scorer.score(df)

    # Verify output
    assert 'target_priority_score' in result.columns
    assert len(result) == 2
    assert all(result['target_priority_score'] >= 0)
    assert all(result['target_priority_score'] <= 100)
    assert 'priority_components' in result.columns

    # Verify component scores exist
    components = result['priority_components'].iloc[0]
    expected_components = [
        'planetary_relevance', 'stellar_characteristics',
        'observational_accessibility', 'data_quality', 'anomaly_score', 'final_score'
    ]
    for comp in expected_components:
        assert comp in components

    print("✓ Priority scorer test passed")

def test_planetary_relevance():
    """Test planetary relevance calculation."""
    scorer = TargetPriorityScorer()
    df = pd.DataFrame({
        'planet_name': ['Earth-like', 'Jupiter-like'],
        'planet_radius': [1.0, 11.0],  # Earth radius, Jupiter radius
        'planet_mass': [1.0, 318.0],   # Earth mass, Jupiter mass
        'equilibrium_temperature': [288.0, 110.0],  # Earth temp, Jupiter temp
        'orbital_period': [365.0, 4333.0]  # Earth year, Jupiter year
    })

    result = scorer.calculate_planetary_relevance(df)
    assert 'planetary_relevance' in result.columns

    # Earth-like planet should have higher relevance than Jupiter-like
    earth_rel = result[result['planet_name'] == 'Earth-like']['planetary_relevance'].iloc[0]
    jupiter_rel = result[result['planet_name'] == 'Jupiter-like']['planetary_relevance'].iloc[0]
    assert earth_rel > jupiter_rel

    print("✓ Planetary relevance test passed")

if __name__ == "__main__":
    test_priority_scorer()
    test_planetary_relevance()
    print("All tests passed!")