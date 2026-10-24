"""Golden benchmark tests for astrophysical accuracy and scientific defensibility."""

import pytest
import numpy as np
import pandas as pd
from app.services.data_processor import get_data_processor


@pytest.fixture(scope="module")
def processed_catalog():
    """Load the processed exoplanet catalog."""
    processor = get_data_processor()
    df = processor.get_processed_data()
    assert not df.empty, "Processed catalog must not be empty"
    return df


def test_golden_toi_700_d(processed_catalog):
    """
    Verify TOI-700 d properties:
    - Host star is an M dwarf (~3459 K, ~0.41 R_sun)
    - Planet is inside the circumstellar Habitable Zone
    - Planet is terrestrial (~1.15 R_earth) with high ESI (> 0.85)
    """
    matches = processed_catalog[processed_catalog["planet_name"] == "TOI-700 d"]
    assert not matches.empty, "TOI-700 d must exist in archive catalog"
    planet = matches.iloc[0]

    # Stellar parameter checks
    assert 3000 <= planet["stellar_effective_temperature"] <= 3800, "TOI-700 must be an M dwarf"
    assert planet["stellar_radius"] < 0.6, "TOI-700 radius must be characteristic of an M dwarf"

    # Habitable Zone check
    assert planet["hz_status"] == "Inside HZ", "TOI-700 d must be Inside HZ"

    # Earth similarity check
    assert planet["earth_similarity"] >= 0.85, "TOI-700 d must have high Earth Similarity Index"
    assert 0.9 <= planet["planet_radius"] <= 1.4, "TOI-700 d must be Earth-sized"


def test_golden_trappist_1_e(processed_catalog):
    """
    Verify TRAPPIST-1 e properties:
    - Host star is an ultra-cool M dwarf (~2566 K)
    - Planet is inside the conservative Habitable Zone
    - High Earth Similarity Index (> 0.85)
    """
    matches = processed_catalog[processed_catalog["planet_name"] == "TRAPPIST-1 e"]
    assert not matches.empty, "TRAPPIST-1 e must exist in archive catalog"
    planet = matches.iloc[0]

    assert planet["stellar_effective_temperature"] < 3000, "TRAPPIST-1 must be an ultra-cool M dwarf"
    assert planet["hz_status"] == "Inside HZ", "TRAPPIST-1 e must be Inside HZ"
    assert planet["earth_similarity"] >= 0.85, "TRAPPIST-1 e must have high ESI"
    assert 0.7 <= planet["planet_radius"] <= 1.2, "TRAPPIST-1 e must be Earth-sized"


def test_golden_lhs_1140_b(processed_catalog):
    """
    Verify LHS 1140 b properties:
    - Temperate super-Earth (~1.73 R_earth)
    - Inside Habitable Zone with high habitability score
    """
    matches = processed_catalog[processed_catalog["planet_name"] == "LHS 1140 b"]
    assert not matches.empty, "LHS 1140 b must exist in archive catalog"
    planet = matches.iloc[0]

    assert planet["hz_status"] in ["Inside HZ", "Near HZ"]
    assert planet["earth_similarity"] >= 0.75
    assert 1.3 <= planet["planet_radius"] <= 2.2


def test_golden_kepler_6_b_is_not_terrestrial(processed_catalog):
    """
    Verify Kepler-6 b properties (fixing C1 unit bug):
    - Kepler-6 b is a hot Jupiter (R > 10 R_earth, Teq > 1000 K)
    - Must be Outside HZ
    - Must have low Earth Similarity Index (< 0.40)
    - Must NOT be in the top priority tier
    """
    matches = processed_catalog[processed_catalog["planet_name"] == "Kepler-6 b"]
    assert not matches.empty, "Kepler-6 b must exist in archive catalog"
    planet = matches.iloc[0]

    assert planet["planet_radius"] > 10.0, "Kepler-6 b is a gas giant (R > 10 R_earth), not terrestrial"
    assert planet["equilibrium_temperature"] > 1000.0, "Kepler-6 b is a hot Jupiter"
    assert planet["hz_status"] == "Outside HZ", "Kepler-6 b is outside HZ"
    assert planet["earth_similarity"] < 0.40, "Kepler-6 b must have low ESI"

    # Verify Kepler-6 b does not rank anywhere near top targets
    rank = processed_catalog[processed_catalog["planet_name"] == "Kepler-6 b"].index[0] + 1
    assert rank > 500, f"Kepler-6 b should rank in the tail, but was rank {rank}"


def test_no_zero_variance_score_inputs(processed_catalog):
    """
    Verify that none of the score components have zero variance (C3 fix):
    - observational_accessibility has variance
    - data_quality has variance
    - earth_similarity has variance
    - target_priority_score has meaningful spread
    """
    for col in ["earth_similarity", "observational_accessibility", "data_quality", "target_priority_score"]:
        assert col in processed_catalog.columns
        valid_vals = processed_catalog[col].dropna()
        std = float(valid_vals.std())
        assert std > 0.05, f"Column {col} has insufficient variance (std={std:.4f})"


def test_top_targets_habitable_zone_alignment(processed_catalog):
    """
    Verify that top-ranked targets are genuinely habitable-zone candidates (C2 fix).
    At least 70% of the top 20 targets must be Inside HZ or Near HZ.
    """
    top_20 = processed_catalog.head(20)
    hz_count = top_20["hz_status"].isin(["Inside HZ", "Near HZ"]).sum()
    fraction = hz_count / len(top_20)
    assert fraction >= 0.70, f"Top 20 targets must be predominantly in HZ (got {fraction:.1%})"
