"""Strict tests for JWST reference label verification and astrophysical invariants.

Validates the 4 strict requirements:
1. Missing columns raise ValueError with clear message.
2. Unverified rows (verified == False) are excluded from get_verified_jwst_targets().
3. Phase curve (and emission) rows are excluded even if verified is True.
4. Warning is printed to stdout when unverified rows are detected in the reference catalog.
"""

from pathlib import Path

import pytest

from app.ml.ground_truth import get_verified_jwst_targets, load_jwst_transmission_targets


def get_live_reference_path() -> Path:
    """Return path to live backend reference CSV."""
    return Path(__file__).resolve().parent.parent / "data" / "reference" / "jwst_transmission_targets.csv"


def test_missing_columns_raise_value_error(tmp_path: Path):
    """Assert missing verified or observation_type columns raise ValueError with clear message."""
    # Case 1: Missing verified column
    csv_missing_verified = tmp_path / "missing_verified.csv"
    csv_missing_verified.write_text(
        "planet_name,program_id,observation_type\n"
        "TRAPPIST-1 e,2589,transmission\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing required columns 'verified' and/or 'observation_type'"):
        get_verified_jwst_targets(csv_missing_verified)

    # Case 2: Missing observation_type column
    csv_missing_obs_type = tmp_path / "missing_obs_type.csv"
    csv_missing_obs_type.write_text(
        "planet_name,program_id,verified\n"
        "TRAPPIST-1 e,2589,True\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing required columns 'verified' and/or 'observation_type'"):
        get_verified_jwst_targets(csv_missing_obs_type)


def test_unverified_rows_excluded(tmp_path: Path):
    """Assert rows with verified=False are strictly excluded from get_verified_jwst_targets()."""
    # 1. Test against custom fixture containing a mix of verified and unverified rows
    mixed_csv = tmp_path / "mixed_reference.csv"
    mixed_csv.write_text(
        "planet_name,program_id,observation_type,verified\n"
        "TRAPPIST-1 e,2589,transmission,True\n"
        "Unverified-Planet b,9999,transmission,False\n"
        "Pending-Planet c,8888,transmission,False\n",
        encoding="utf-8",
    )
    verified = get_verified_jwst_targets(mixed_csv)
    assert "TRAPPIST-1 e" in verified
    assert "Unverified-Planet b" not in verified
    assert "Pending-Planet c" not in verified

    # 2. Test live reference catalog: unverified targets must be strictly excluded
    live_csv = get_live_reference_path()
    assert live_csv.exists(), f"Live reference CSV missing at {live_csv}"
    live_df = load_jwst_transmission_targets(live_csv)

    unverified_planets = live_df[live_df["verified"] == False]["planet_name"].tolist()
    live_verified = get_verified_jwst_targets(live_csv)
    for planet in unverified_planets:
        assert planet not in live_verified, f"Unverified planet {planet} leaked into verified targets set"


def test_phase_curve_rows_excluded(tmp_path: Path):
    """Assert phase_curve and emission rows are excluded even if verified=True."""
    obs_type_csv = tmp_path / "obs_type_reference.csv"
    obs_type_csv.write_text(
        "planet_name,program_id,observation_type,verified\n"
        "Valid-Transiting b,1001,transmission,True\n"
        "Phase-Curve c,1002,phase_curve,True\n"
        "Emission-Target d,1003,emission,True\n"
        "Transit-Timing e,1004,transit_timing,True\n",
        encoding="utf-8",
    )
    verified = get_verified_jwst_targets(obs_type_csv)
    assert "Valid-Transiting b" in verified
    assert "Phase-Curve c" not in verified, "phase_curve target must be excluded even if verified=True"
    assert "Emission-Target d" not in verified, "emission target must be excluded even if verified=True"
    assert "Transit-Timing e" not in verified, "transit_timing target must be excluded even if verified=True"


def test_warning_printed_for_unverified_rows(tmp_path: Path, capsys: pytest.CaptureFixture):
    """Assert a loud warning is printed when unverified rows exist in the reference catalog."""
    import app.ml.ground_truth as gt

    # Reset warning flag to ensure warning prints
    gt._WARNED_UNVERIFIED = False

    csv_with_unverified = tmp_path / "warn_reference.csv"
    csv_with_unverified.write_text(
        "planet_name,program_id,observation_type,verified\n"
        "Reviewed-Target b,1234,transmission,True\n"
        "Unreviewed-Target c,5678,unknown,False\n",
        encoding="utf-8",
    )

    get_verified_jwst_targets(csv_with_unverified)
    captured = capsys.readouterr()

    assert "[LOUD WARNING] UNVERIFIED JWST REFERENCE TARGETS DETECTED" in captured.out
    assert "Unreviewed-Target c" in captured.out
    assert "Action Required: Review reports/jwst_reference_verification.csv" in captured.out
