"""Tests asserting ranking uniqueness, contiguity, deterministic ordering, and OOF score usage."""

import numpy as np
import pandas as pd
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.data_processor import get_data_processor


@pytest.fixture(scope="module")
def processed_catalog():
    """Load the processed exoplanet catalog."""
    processor = get_data_processor()
    return processor.get_processed_data()


@pytest.fixture(scope="module")
def client():
    """FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


def test_priority_rank_is_strictly_unique_and_contiguous(processed_catalog):
    """Assert priority_rank contains zero duplicates and is strictly contiguous across all eligible candidates."""
    eligible = processed_catalog[processed_catalog["eligible_for_transmission"] == True].copy()
    n_eligible = len(eligible)
    assert n_eligible > 0, "Eligible candidates catalog must not be empty"

    priority_ranks = eligible["priority_rank"].dropna().astype(int)
    assert len(priority_ranks) == n_eligible, (
        f"All {n_eligible} eligible candidates must have non-null priority_rank (got {len(priority_ranks)})"
    )
    assert priority_ranks.nunique() == n_eligible, (
        f"priority_rank must be strictly unique across eligible candidates: expected {n_eligible}, got {priority_ranks.nunique()}"
    )

    sorted_ranks = priority_ranks.sort_values().to_numpy()
    expected_ranks = np.arange(1, n_eligible + 1)
    np.testing.assert_array_equal(
        sorted_ranks,
        expected_ranks,
        err_msg="priority_rank must form a contiguous sequence 1..N with zero gaps or duplicate integers",
    )


def test_unobserved_rank_is_strictly_unique_and_separate(processed_catalog):
    """Assert unobserved_rank is strictly unique among already_observed_jwst==False and NaN for observed."""
    eligible = processed_catalog[processed_catalog["eligible_for_transmission"] == True].copy()
    unobs = eligible[eligible["already_observed_jwst"] == False].copy()
    n_unobs = len(unobs)
    assert n_unobs > 0, "Unobserved eligible candidates must exist"

    unobs_ranks = unobs["unobserved_rank"].dropna().astype(int)
    assert len(unobs_ranks) == n_unobs, (
        f"All {n_unobs} unobserved eligible candidates must have non-null unobserved_rank (got {len(unobs_ranks)})"
    )
    assert unobs_ranks.nunique() == n_unobs, (
        f"unobserved_rank must be strictly unique across unobserved candidates: expected {n_unobs}, got {unobs_ranks.nunique()}"
    )

    sorted_unobs = unobs_ranks.sort_values().to_numpy()
    expected_unobs = np.arange(1, n_unobs + 1)
    np.testing.assert_array_equal(
        sorted_unobs,
        expected_unobs,
        err_msg="unobserved_rank must form a contiguous sequence 1..N_unobserved with zero gaps or duplicate integers",
    )

    # Observed planets must have NaN unobserved_rank
    observed = eligible[eligible["already_observed_jwst"] == True]
    assert len(observed) > 0, "Observed JWST targets must exist in catalog"
    assert observed["unobserved_rank"].isna().all(), (
        "Observed JWST targets must have NaN unobserved_rank (reserved strictly for unobserved)"
    )


def test_rank_order_matches_score_order(processed_catalog):
    """Assert rank order matches score order with deterministic tie-breaking (tsm desc, dist asc, name asc)."""
    eligible = processed_catalog[processed_catalog["eligible_for_transmission"] == True].copy()

    # Reconstruct tie-breaking keys
    tsm_col = eligible.get("tsm", eligible.get("transmission_spectroscopy_metric", pd.Series(0.0, index=eligible.index)))
    dist_col = eligible.get("distance", pd.Series(9999.0, index=eligible.index))
    eligible["_tsm_sort"] = pd.to_numeric(tsm_col, errors="coerce").fillna(0.0)
    eligible["_dist_sort"] = pd.to_numeric(dist_col, errors="coerce").fillna(9999.0)

    expected_sorted = eligible.sort_values(
        by=["priority_score", "_tsm_sort", "_dist_sort", "planet_name"],
        ascending=[False, False, True, True],
    ).reset_index(drop=True)

    sorted_by_rank = eligible.sort_values("priority_rank").reset_index(drop=True)

    assert sorted_by_rank["planet_name"].tolist() == expected_sorted["planet_name"].tolist(), (
        "Order induced by priority_rank must match exact score order with tie-breakers"
    )

    # Score monotonicity check: every rank r must have score >= score at rank r+1
    scores = sorted_by_rank["priority_score"].to_numpy()
    diffs = np.diff(scores)
    assert (diffs <= 1e-4).all(), f"Scores must be non-increasing along priority_rank order (max violation: {diffs.max()})"


def test_labelled_planets_use_oof_scores(processed_catalog):
    """Assert labelled planets strictly use out-of-fold scores for priority_score."""
    eligible = processed_catalog[processed_catalog["eligible_for_transmission"] == True].copy()
    labelled = eligible[eligible["already_observed_jwst"] == True]
    assert len(labelled) > 0, "Labelled planets must exist"

    # For labelled planets, priority_score MUST equal oof_priority_score
    np.testing.assert_allclose(
        labelled["priority_score"].to_numpy(),
        labelled["oof_priority_score"].to_numpy(),
        rtol=1e-5,
        atol=1e-4,
        err_msg="Labelled planets must use oof_priority_score for priority_score",
    )

    # For unlabelled planets, priority_score MUST equal in_sample_priority_score
    unlabelled = eligible[eligible["already_observed_jwst"] == False]
    np.testing.assert_allclose(
        unlabelled["priority_score"].to_numpy(),
        unlabelled["in_sample_priority_score"].to_numpy(),
        rtol=1e-5,
        atol=1e-4,
        err_msg="Unlabelled planets must use in_sample_priority_score for priority_score",
    )


def test_ml_rank_is_strictly_unique_across_eligible_candidates(processed_catalog):
    """Assert ml_rank contains zero duplicates among all eligible candidates."""
    eligible = processed_catalog[processed_catalog["eligible_for_transmission"] == True].copy()
    n_eligible = len(eligible)

    ml_ranks = eligible["ml_rank"].dropna().astype(int)
    assert len(ml_ranks) == n_eligible
    assert ml_ranks.nunique() == n_eligible


def test_non_eligible_planets_never_receive_ml_rank(processed_catalog):
    """Non-eligible planets must never be ranked in ml_rank or priority_rank."""
    ineligible = processed_catalog[processed_catalog["eligible_for_transmission"] == False]
    assert len(ineligible) > 0, "Ineligible planets must exist in catalog"

    assert len(ineligible["ml_rank"].dropna()) == 0
    assert len(ineligible["priority_rank"].dropna()) == 0
    assert len(ineligible["unobserved_rank"].dropna()) == 0


def test_heuristic_rank_uniqueness(processed_catalog):
    """Assert heuristic_rank is strictly unique across all eligible candidates."""
    eligible = processed_catalog[processed_catalog["eligible_for_transmission"] == True].copy()
    heuristic_ranks = eligible["heuristic_rank"].dropna().astype(int)
    n_eligible = len(eligible)

    assert len(heuristic_ranks) == n_eligible
    assert heuristic_ranks.nunique() == n_eligible


def test_top_targets_endpoint_ranks_are_strictly_unique(client):
    """Assert /api/v1/top-targets returns candidates with distinct, strictly monotonic ranks."""
    resp = client.get("/api/v1/top-targets?limit=25")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data) > 0
    ranks = [p.get("priority_rank") or p.get("unobserved_rank") or p.get("ml_rank") for p in data]
    ranks = [r for r in ranks if r is not None]

    assert len(ranks) == len(data), "Every top target must have an assigned rank"
    assert len(set(ranks)) == len(ranks), f"Found duplicate ranks in top-targets response: {ranks}"
