"""Golden benchmark tests for astrophysical accuracy and scientific defensibility."""

import pandas as pd
import pytest

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


def test_transit_eligibility_and_non_ranked_targets(processed_catalog):
    """
    Verify Phase 1 transit eligibility rules:
    - eligible_for_transmission and is_transiting columns exist
    - exclusion_reason string column exists
    - No ranked planet has is_transiting == False
    - Non-transiting radial velocity planets are not ranked:
      HD 160691 b, GJ 667 C f, GJ 667 C e, Proxima Cen b, HD 10180 g
    """
    assert "eligible_for_transmission" in processed_catalog.columns
    assert "is_transiting" in processed_catalog.columns
    assert "exclusion_reason" in processed_catalog.columns

    # No ranked planet has is_transiting == False
    for rank_col in ["ml_rank", "heuristic_rank"]:
        if rank_col in processed_catalog.columns:
            ranked = processed_catalog[processed_catalog[rank_col].notna()]
            assert not ranked.empty
            assert (ranked["is_transiting"] == True).all(), f"Found non-transiting planet in {rank_col}"
            assert (ranked["eligible_for_transmission"] == True).all(), f"Found ineligible planet in {rank_col}"

    # Explicit check for specified non-transiting planets
    unranked_targets = ["HD 160691 b", "GJ 667 C f", "GJ 667 C e", "Proxima Cen b", "HD 10180 g"]
    for name in unranked_targets:
        matches = processed_catalog[processed_catalog["planet_name"] == name]
        if not matches.empty:
            planet = matches.iloc[0]
            assert planet["is_transiting"] == False, f"{name} should have is_transiting == False"
            assert planet["eligible_for_transmission"] == False, f"{name} should not be eligible"
            assert planet["exclusion_reason"] != "", f"{name} should have non-empty exclusion_reason"
            for rank_col in ["ml_rank", "heuristic_rank"]:
                if rank_col in processed_catalog.columns:
                    assert pd.isna(planet[rank_col]), f"{name} should not have {rank_col}, got {planet[rank_col]}"


def test_one_score_one_rank_consistency():
    """
    Verify Phase 4 One Score, One Rank invariants:
    - API rank on list endpoints == detail endpoint rank
    - Rank order matches score order
    - Every endpoint returns priority_score and priority_rank
    - Ineligible planets have priority_rank is None
    """
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)

    # 1. Fetch top targets
    top_resp = client.get("/api/v1/top-targets?limit=25")
    assert top_resp.status_code == 200
    top_planets = top_resp.json()
    assert len(top_planets) >= 10

    # Verify score order matches rank order
    prev_rank = 0
    prev_score = float("inf")
    for p in top_planets:
        assert "priority_score" in p and p["priority_score"] is not None
        assert "priority_rank" in p and p["priority_rank"] is not None
        assert p["priority_rank"] > prev_rank, "Ranks must be strictly increasing"
        assert p["priority_score"] <= prev_score + 1e-5, "Scores must be descending or equal"
        prev_rank = p["priority_rank"]
        prev_score = p["priority_score"]

    # 2. Check detail endpoint rank matches list endpoint rank
    for p in top_planets[:5]:
        name = p["planet_name"]
        detail_resp = client.get(f"/api/v1/planets/{name}")
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()

        assert detail_data["priority_score"] == p["priority_score"], f"Score mismatch on {name}"
        assert detail_data["priority_rank"] == p["priority_rank"], (
            f"Rank mismatch on {name}: list={p['priority_rank']}, detail={detail_data['priority_rank']}"
        )

    # 3. Check ineligible planets in general planets list have priority_rank is None
    planets_resp = client.get("/api/v1/planets?limit=200")
    assert planets_resp.status_code == 200
    all_planets = planets_resp.json()

    for p in all_planets:
        assert "priority_score" in p
        assert "priority_rank" in p
        if p.get("eligible_for_transmission") is False:
            assert p["priority_rank"] is None, f"Ineligible planet {p['planet_name']} should have None rank"
            # Verify detail also has None rank
            d_resp = client.get(f"/api/v1/planets/{p['planet_name']}")
            if d_resp.status_code == 200:
                assert d_resp.json()["priority_rank"] is None


def test_flexible_search_kepler_452_b():
    """
    Verify flexible search for 'kepler 452 b' (without hyphen) matches 'Kepler-452 b'
    and supports direct TreeSHAP explanation retrieval.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)

    # 1. Search via /planets?q=kepler 452 b
    search_resp = client.get("/api/v1/planets?q=kepler 452 b")
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert len(results) >= 1
    matched_names = [p["planet_name"] for p in results]
    assert "Kepler-452 b" in matched_names

    # 2. Direct planet detail lookup with unhyphenated name
    detail_resp = client.get("/api/v1/planets/kepler 452 b")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["planet_name"] == "Kepler-452 b"

    # 3. Direct TreeSHAP explanation with unhyphenated name
    explain_resp = client.get("/api/v1/planets/kepler 452 b/explain")
    assert explain_resp.status_code == 200
    exp_data = explain_resp.json()
    assert exp_data["planet_name"] == "Kepler-452 b"
    assert "mathematical_invariants" in exp_data
    assert "full_waterfall" in exp_data
