"""Unit tests for JWST MAST candidate label extraction and time-series mode filtering."""

import sys
from pathlib import Path
from unittest.mock import patch

from astropy.table import Table

# Add scripts directory to sys.path to import build_jwst_labels_from_mast
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_jwst_labels_from_mast as mast_builder  # noqa: E402


def test_is_time_series_spectroscopy_positive_modes():
    """Assert all approved JWST time-series spectroscopy modes return True."""
    # 1. NIRISS SOSS
    assert mast_builder.is_time_series_spectroscopy("NIRISS/SOSS", "CLEAR;GR700XD")
    assert mast_builder.is_time_series_spectroscopy("NIRISS", "GR700XD")
    assert mast_builder.is_time_series_spectroscopy("NIRISS/SOSS", "SUBSTRIP256")

    # 2. NIRSpec BOTS / PRISM / G395H / G140H / G235H
    assert mast_builder.is_time_series_spectroscopy("NIRSPEC/SLIT", "CLEAR;PRISM")
    assert mast_builder.is_time_series_spectroscopy("NIRSPEC/SLIT", "F290LP;G395H")
    assert mast_builder.is_time_series_spectroscopy("NIRSPEC/BOTS", "CLEAR;PRISM")
    assert mast_builder.is_time_series_spectroscopy("NIRSPEC/SLIT", "F100LP;G140H")

    # 3. NIRCam grism time series
    assert mast_builder.is_time_series_spectroscopy("NIRCAM/GRISM", "F322W2;GRISMR")
    assert mast_builder.is_time_series_spectroscopy("NIRCAM/GRISM", "F444W;GRISMC")

    # 4. MIRI LRS slitless
    assert mast_builder.is_time_series_spectroscopy("MIRI/SLITLESS", "P750L")
    assert mast_builder.is_time_series_spectroscopy("MIRI", "LRS;P750L")


def test_is_time_series_spectroscopy_negative_modes():
    """Assert non-spectroscopic, imaging, target acquisition, or IFU modes return False."""
    assert not mast_builder.is_time_series_spectroscopy("NIRCAM/IMAGE", "F210M;WLP8")
    assert not mast_builder.is_time_series_spectroscopy("MIRI/TARGACQ", "F1000W")
    assert not mast_builder.is_time_series_spectroscopy("NIRISS/IMAGE", "F150W")
    assert not mast_builder.is_time_series_spectroscopy("NIRSPEC/IFU", "CLEAR;PRISM")
    assert not mast_builder.is_time_series_spectroscopy("MIRI/CORON", "F1065C")


def test_classify_likely_type_from_title():
    """Assert observation type classification follows strict title keyword rules."""
    # Phase curve
    assert (
        mast_builder.classify_likely_type_from_title(
            "Unlocking the Mysteries of the Archetype Sub-Neptune with a Full-Orbit Phase Curve"
        )
        == "phase_curve"
    )
    assert mast_builder.classify_likely_type_from_title("NIRSpec Phase Curve for WASP-121b") == "phase_curve"

    # Secondary eclipse / emission
    assert (
        mast_builder.classify_likely_type_from_title(
            "Determining the Atmospheric Composition via Secondary Eclipse Emission"
        )
        == "eclipse"
    )
    assert mast_builder.classify_likely_type_from_title("Dayside Thermal Occultation of Hot Jupiter") == "eclipse"

    # Transmission spectroscopy
    assert (
        mast_builder.classify_likely_type_from_title(
            "NIRSpec PRISM transmission spectroscopy of temperate sub-Neptune"
        )
        == "transmission"
    )
    assert mast_builder.classify_likely_type_from_title("Transit Reconnaissance of TRAPPIST-1 System") == "transmission"
    assert mast_builder.classify_likely_type_from_title("Atmospheric Characterization of Transiting Planet") == "transmission"

    # Unknown / generic
    assert mast_builder.classify_likely_type_from_title("General calibration and flux monitoring") == "unknown"
    assert mast_builder.classify_likely_type_from_title("") == "unknown"


def test_query_mast_with_mocked_response_and_caching(tmp_path: Path):
    """Test query_mast_for_host with mocked Observations.query_criteria and verify disk caching."""
    mock_data = Table(
        {
            "proposal_id": ["1201", "1366"],
            "instrument_name": ["NIRISS/SOSS", "NIRSPEC/SLIT"],
            "filters": ["CLEAR;GR700XD", "CLEAR;PRISM"],
            "target_name": ["TRAPPIST-1", "TRAPPIST-1"],
            "t_min": [59780.5, 59795.2],
            "obs_title": [
                "NIRISS Exploration of Transiting Exoplanet Atmospheres",
                "The Transiting Exoplanet Community ERS Program",
            ],
        }
    )

    cache_dir = tmp_path / ".mast_cache"

    with patch.object(mast_builder.Observations, "query_criteria", return_value=mock_data) as mock_query:
        # First call: network mock is queried and results are cached to disk
        results = mast_builder.query_mast_for_host(
            hostname="TRAPPIST-1",
            cache_dir=cache_dir,
            delay=0.0,
        )

        assert mock_query.call_count == 1
        assert len(results) == 2
        assert results[0]["proposal_id"] == "1201"
        assert results[0]["instrument_name"] == "NIRISS/SOSS"

        # Check cache file exists on disk
        cache_file = cache_dir / "TRAPPIST-1.json"
        assert cache_file.exists(), f"Cache file {cache_file} was not written"

    # Second call: network mock raises RuntimeError if called, verifying disk cache hit
    with patch.object(mast_builder.Observations, "query_criteria", side_effect=RuntimeError("Should not be called!")):
        cached_results = mast_builder.query_mast_for_host(
            hostname="TRAPPIST-1",
            cache_dir=cache_dir,
            delay=0.0,
        )
        assert len(cached_results) == 2
        assert cached_results[0]["proposal_id"] == "1201"


def test_process_mast_observations_filters_modes_and_formats_output(tmp_path: Path):
    """Test end-to-end processing of mocked MAST observations, filtering, and CSV schema."""
    # Mock observations containing 1 SOSS (valid), 1 PRISM (valid), 1 imaging (invalid)
    mock_observations = [
        {
            "proposal_id": "2589",
            "instrument_name": "NIRSPEC/SLIT",
            "filters": "CLEAR;PRISM",
            "target_name": "TRAPPIST-1",
            "t_min": 59800.0,
            "proposal_title": "Atmospheric reconnaissance of the TRAPPIST-1 planets in transmission",
        },
        {
            "proposal_id": "9999",
            "instrument_name": "NIRCAM/IMAGE",
            "filters": "F210M;WLP8",
            "target_name": "TRAPPIST-1",
            "t_min": 59805.0,
            "proposal_title": "Deep imaging survey",
        },
    ]

    cache_dir = tmp_path / ".mast_cache"

    hosts_to_query = {"TRAPPIST-1": ["TRAPPIST-1 b", "TRAPPIST-1 c", "TRAPPIST-1 d"]}

    with patch.object(mast_builder, "query_mast_for_host", return_value=mock_observations):
        candidates, hosts_found, proposals_found = mast_builder.process_mast_observations(
            hosts_to_query=hosts_to_query,
            cache_dir=cache_dir,
            delay=0.0,
        )

    # Assert non-spectroscopic mode was filtered out
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand["hostname"] == "TRAPPIST-1"
    assert cand["proposal_id"] == "2589"
    assert cand["instrument"] == "NIRSPEC/SLIT"
    assert cand["filters"] == "CLEAR;PRISM"
    assert cand["likely_type"] == "transmission"
    assert cand["proposal_url"] == "https://www.stsci.edu/jwst/science-execution/program-information?id=2589"
    assert cand["candidate_planets"] == "TRAPPIST-1 b; TRAPPIST-1 c; TRAPPIST-1 d"
    assert cand["obs_date"] == "2022-08-09"

    assert "TRAPPIST-1" in hosts_found
    assert "2589" in proposals_found


def test_reference_targets_csv_is_not_modified(tmp_path: Path):
    """Assert jwst_transmission_targets.csv is never written to or modified by the script."""
    ref_csv = Path(__file__).resolve().parent.parent / "data" / "reference" / "jwst_transmission_targets.csv"
    assert ref_csv.exists(), f"Reference CSV missing at {ref_csv}"
    original_content = ref_csv.read_text(encoding="utf-8")

    # Run mast_builder main flow with a temporary output
    cache_dir = tmp_path / ".cache"

    with patch.object(mast_builder, "query_mast_for_host", return_value=[]):
        mast_builder.process_mast_observations(
            hosts_to_query={"TRAPPIST-1": ["TRAPPIST-1 b"]},
            cache_dir=cache_dir,
            delay=0.0,
        )

    current_content = ref_csv.read_text(encoding="utf-8")
    assert current_content == original_content, "jwst_transmission_targets.csv was modified!"
