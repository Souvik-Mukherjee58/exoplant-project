"""Tests for the MAST label-candidate builder and the live cache checker.

All observation/ephemeris data used here is SYNTHETIC TEST DATA (fictional hosts SYN-1..SYN-4) from
backend/tests/fixtures/fixture_mast_timeseries.ecsv and fixture_nasa_ephemerides.csv, or built inline.
No network access: MAST/NASA calls are patched.
"""

import importlib
import io
import json
import math
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from astropy.table import Table

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_jwst_labels_from_mast as mast_builder  # noqa: E402

check_mast_cache = importlib.import_module("check_mast_cache")

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MAST_FIXTURE = FIXTURES / "fixture_mast_timeseries.ecsv"
EPHEM_FIXTURE = FIXTURES / "fixture_nasa_ephemerides.csv"


def _cache_from_fixtures(cache_dir: Path) -> None:
    """Install the synthetic fixtures as a valid cache (raw bytes + .meta.json with SHA-256)."""
    mast_builder.write_raw_cache(
        cache_dir,
        mast_builder.MAST_CACHE_STEM,
        ".ecsv",
        MAST_FIXTURE.read_bytes(),
        {"query": mast_builder.MAST_QUERY, "fetched_at": "SYNTHETIC", "row_count": 8},
    )
    mast_builder.write_raw_cache(
        cache_dir,
        mast_builder.EPHEM_CACHE_STEM,
        ".csv",
        EPHEM_FIXTURE.read_bytes(),
        {"query": "SYNTHETIC", "fetched_at": "SYNTHETIC", "row_count": 4},
    )


@pytest.fixture
def frames(tmp_path):
    cache = tmp_path / "cache"
    _cache_from_fixtures(cache)
    obs, _ = mast_builder.fetch_jwst_timeseries(cache, force_refresh=False, offline=True)
    ephem, _ = mast_builder.fetch_ephemerides(cache, force_refresh=False, offline=True)
    return obs, ephem


def _planet(**kw):
    base = {
        "pl_name": "SYN-1 b",
        "pl_tranmid": 2459000.65,  # MJD 59000.15
        "pl_tranmiderr1": 0.0001,
        "pl_tranmiderr2": -0.0001,
        "pl_orbper": 2.0,
        "pl_orbpererr1": 0.00001,
        "pl_orbpererr2": -0.00001,
        "pl_orbeccen": 0.0,
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------------------------
# Mode filtering and title hints
# ---------------------------------------------------------------------------------------------


def test_is_time_series_spectroscopy_positive_modes():
    assert mast_builder.is_time_series_spectroscopy("NIRISS/SOSS", "CLEAR;GR700XD")
    assert mast_builder.is_time_series_spectroscopy("NIRISS", "GR700XD")
    assert mast_builder.is_time_series_spectroscopy("NIRISS/SOSS", "SUBSTRIP256")
    assert mast_builder.is_time_series_spectroscopy("NIRSPEC/SLIT", "CLEAR;PRISM")
    assert mast_builder.is_time_series_spectroscopy("NIRSPEC/SLIT", "F290LP;G395H")
    assert mast_builder.is_time_series_spectroscopy("NIRSPEC/BOTS", "CLEAR;PRISM")
    assert mast_builder.is_time_series_spectroscopy("NIRSPEC/SLIT", "F100LP;G140H")
    assert mast_builder.is_time_series_spectroscopy("NIRCAM/GRISM", "F322W2;GRISMR")
    assert mast_builder.is_time_series_spectroscopy("NIRCAM/GRISM", "F444W;GRISMC")
    assert mast_builder.is_time_series_spectroscopy("MIRI/SLITLESS", "P750L")
    assert mast_builder.is_time_series_spectroscopy("MIRI", "LRS;P750L")


def test_is_time_series_spectroscopy_negative_modes():
    assert not mast_builder.is_time_series_spectroscopy("NIRCAM/IMAGE", "F210M;WLP8")
    assert not mast_builder.is_time_series_spectroscopy("MIRI/TARGACQ", "F1000W")
    assert not mast_builder.is_time_series_spectroscopy("NIRISS/IMAGE", "F150W")
    assert not mast_builder.is_time_series_spectroscopy("NIRSPEC/IFU", "CLEAR;PRISM")
    assert not mast_builder.is_time_series_spectroscopy("MIRI/CORON", "F1065C")


def test_miri_slitless_target_acquisition_filter_is_rejected():
    """MIRI/SLITLESS rows with an imaging filter (e.g. F1000W) are target acquisition, not LRS spectra."""
    assert not mast_builder.is_time_series_spectroscopy("MIRI/SLITLESS", "F1000W")
    assert not mast_builder.is_time_series_spectroscopy("MIRI/SLITLESS", "")


def test_classify_likely_type_from_title():
    f = mast_builder.classify_likely_type_from_title
    assert f("Unlocking the Mysteries of the Archetype Sub-Neptune with a Full-Orbit Phase Curve") == "phase_curve"
    assert f("NIRSpec Phase Curve for WASP-121b") == "phase_curve"
    assert f("Determining the Atmospheric Composition via Secondary Eclipse Emission") == "eclipse"
    assert f("Dayside Thermal Occultation of Hot Jupiter") == "eclipse"
    assert f("NIRSpec PRISM transmission spectroscopy of temperate sub-Neptune") == "transmission"
    assert f("Transit Reconnaissance of TRAPPIST-1 System") == "transmission"
    assert f("Atmospheric Characterization of Transiting Planet") == "transmission"
    assert f("General calibration and flux monitoring") == "unknown"
    assert f("") == "unknown"


def test_combine_likely_type_surfaces_conflicts():
    f = mast_builder.combine_likely_type
    assert f("transit_in_window", "transmission") == "transmission"
    assert f("transit_in_window", "unknown") == "transmission"
    assert f("transit_in_window", "eclipse") == "conflict"
    assert f("eclipse_in_window", "phase_curve") == "phase_curve"
    assert f("eclipse_in_window", "transmission") == "conflict"
    assert f("ambiguous", "transmission") == "needs_review"
    assert f("no_event_in_window", "transmission") == "no_event"


# ---------------------------------------------------------------------------------------------
# Time conversion and ephemeris prediction
# ---------------------------------------------------------------------------------------------


def test_to_mjd_converts_jd_and_keeps_mjd():
    assert mast_builder.to_mjd(2459000.65) == pytest.approx(59000.15)
    assert mast_builder.to_mjd(59000.15) == pytest.approx(59000.15)
    with pytest.raises(ValueError):
        mast_builder.to_mjd(1234.5)


def test_transit_in_window_with_propagated_uncertainty():
    ev = mast_builder.assign_planet_event(59200.0123, 59200.2877, _planet())
    assert ev["match_status"] == "transit_in_window"
    assert ev["transit_epoch"] == 100
    assert ev["predicted_mid_transit"] == pytest.approx(59200.15)
    expected_sigma_h = math.sqrt(0.0001**2 + (100 * 0.00001) ** 2) * 24
    assert ev["timing_uncertainty_hours"] == pytest.approx(expected_sigma_h, abs=1e-4)


def test_eclipse_in_window():
    ev = mast_builder.assign_planet_event(59201.0123, 59201.2877, _planet())
    assert ev["match_status"] == "eclipse_in_window"


def test_no_event_in_window():
    ev = mast_builder.assign_planet_event(59202.5123, 59202.6877, _planet())
    assert ev["match_status"] == "no_event_in_window"


def test_event_at_window_edge_is_ambiguous():
    # transit at 59200.15, window ends 2 minutes after it
    ev = mast_builder.assign_planet_event(59199.9, 59200.1514, _planet())
    assert ev["match_status"] == "ambiguous"
    assert "event_near_window_edge" in ev["match_note"]


def test_missing_uncertainty_is_never_confident():
    ev = mast_builder.assign_planet_event(59200.0123, 59200.2877, _planet(pl_tranmiderr1=None, pl_tranmiderr2=None))
    assert ev["match_status"] == "ambiguous"
    assert "ephemeris_uncertainty_missing" in ev["match_note"]


def test_stale_ephemeris_is_ambiguous():
    # sigma_P of 0.01 d over 100 epochs = 1 d > P/4
    ev = mast_builder.assign_planet_event(59200.0123, 59200.2877, _planet(pl_orbpererr1=0.01, pl_orbpererr2=-0.01))
    assert ev["match_status"] == "ambiguous"
    assert "ephemeris_stale" in ev["match_note"]


def test_missing_ephemeris_is_ambiguous():
    ev = mast_builder.assign_planet_event(59200.0, 59200.3, _planet(pl_tranmid=None))
    assert ev["match_status"] == "ambiguous"
    assert ev["match_note"] == "no_ephemeris"


def test_window_covering_transit_and_eclipse_is_ambiguous():
    ev = mast_builder.assign_planet_event(59199.9, 59201.4, _planet())
    assert ev["match_status"] == "ambiguous"
    assert "window_covers_transit_and_eclipse" in ev["match_note"]


def test_eccentric_orbit_eclipse_away_from_phase_half_is_not_dropped():
    """An eccentric planet's eclipse can sit far from phase 0.5 (e.g. GJ 436 b): never report no_event."""
    planet = _planet(pl_orbeccen=0.3)
    # phase 0.62: outside a +/-0.25 h circular-orbit eclipse window, inside 0.5 +/- (2/pi)*0.3
    centre = 59000.15 + 100.62 * 2.0
    ev = mast_builder.assign_planet_event(centre - 0.1, centre + 0.1, planet)
    assert ev["match_status"] == "ambiguous"
    assert "eccentric_orbit_eclipse_possible" in ev["match_note"]
    circular = mast_builder.assign_planet_event(centre - 0.1, centre + 0.1, _planet())
    assert circular["match_status"] == "no_event_in_window"


def test_window_with_two_transits_picks_epoch_nearest_centre():
    ev = mast_builder.assign_planet_event(59199.0, 59202.0, _planet(pl_orbper=1.0, pl_tranmid=2459000.65))
    assert ev["predicted_mid_transit"] in (pytest.approx(59200.15), pytest.approx(59201.15))
    assert abs(ev["predicted_mid_transit"] - 59200.5) <= 0.65


# ---------------------------------------------------------------------------------------------
# Host matching
# ---------------------------------------------------------------------------------------------


def test_match_host_by_name_suffix_and_coordinates():
    ephem = pd.read_csv(EPHEM_FIXTURE)
    idx = mast_builder.build_host_index(ephem)
    assert mast_builder.match_host("SYN-1", None, None, idx, 30) == ("SYN-1", "name", None)
    assert mast_builder.match_host("syn 1", None, None, idx, 30)[0:2] == ("SYN-1", "name")
    assert mast_builder.match_host("SYN2B", None, None, idx, 30)[0:2] == ("SYN-2", "name_planet_suffix")
    host, method, sep = mast_builder.match_host("ALIAS-STAR", 150.2503, -20.5002, idx, 30)
    assert (host, method) == ("SYN-1", "coordinates")
    assert 0 < sep < 2
    assert mast_builder.match_host("NOBODY", 10.0, 10.0, idx, 30) == (None, "none", None)


def test_ambiguous_coordinates_are_not_matched():
    ephem = pd.DataFrame({"pl_name": ["A b", "B b"], "hostname": ["A", "B"], "ra": [10.0, 10.0025], "dec": [5.0, 5.0]})
    idx = mast_builder.build_host_index(ephem)
    assert mast_builder.match_host("X", 10.001, 5.0, idx, 30)[0:2] == (None, "coordinates_ambiguous")


def test_normalised_host_name_collisions_are_excluded():
    ephem = pd.DataFrame(
        {"pl_name": ["K2-3 b", "K-23 b"], "hostname": ["K2-3", "K-23"], "ra": [1.0, 2.0], "dec": [1.0, 2.0]}
    )
    idx = mast_builder.build_host_index(ephem)
    assert "K23" in idx.collisions
    assert "K23" not in idx.by_norm


# ---------------------------------------------------------------------------------------------
# Raw cache integrity
# ---------------------------------------------------------------------------------------------


def test_cache_roundtrip_and_sha256(tmp_path):
    raw = b"col\n1.5\n"
    mast_builder.write_raw_cache(tmp_path, "x", ".csv", raw, {"fetched_at": "SYNTHETIC"})
    data, meta = mast_builder.read_raw_cache(tmp_path, "x", ".csv")
    assert data == raw
    assert meta["sha256"] == mast_builder.sha256_bytes(raw)


def test_tampered_cache_raises(tmp_path):
    mast_builder.write_raw_cache(tmp_path, "x", ".csv", b"col\n1.5\n", {})
    (tmp_path / "x.csv").write_bytes(b"col\n1.5 transmission\n")
    with pytest.raises(mast_builder.CacheIntegrityError):
        mast_builder.read_raw_cache(tmp_path, "x", ".csv")


def test_obs_title_is_stored_and_read_back_unmodified(frames):
    obs, _ = frames
    titles = set(obs["obs_title"])
    assert "Transmission spectroscopy of SYN-1 b: a test, with comma" in titles
    assert "Dayside emission of SYN-1 b" in titles


def test_live_fetch_is_cached_and_not_repeated(tmp_path):
    table = Table.read(MAST_FIXTURE.read_text(encoding="utf-8"), format="ascii.ecsv")
    with patch("astroquery.mast.Observations.query_criteria", return_value=table) as q:
        obs1, meta1 = mast_builder.fetch_jwst_timeseries(tmp_path, force_refresh=False, offline=False, retries=1)
        assert q.call_count == 1
    assert (tmp_path / "jwst_timeseries.ecsv").exists()
    assert meta1["row_count"] == len(table)
    with patch("astroquery.mast.Observations.query_criteria", side_effect=RuntimeError("network must not be used")):
        obs2, _ = mast_builder.fetch_jwst_timeseries(tmp_path, force_refresh=False, offline=False)
    assert obs1["obs_title"].tolist() == obs2["obs_title"].tolist()
    assert obs1["t_min"].tolist() == obs2["t_min"].tolist()


def test_offline_without_cache_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        mast_builder.fetch_jwst_timeseries(tmp_path, force_refresh=False, offline=True)


# ---------------------------------------------------------------------------------------------
# End-to-end candidate building on synthetic fixtures
# ---------------------------------------------------------------------------------------------


def test_build_candidates_on_synthetic_fixtures(frames):
    obs, ephem = frames
    rows, stats = mast_builder.build_candidates(obs, ephem)
    by_obs = {r["obs_id"]: r for r in rows}

    assert stats["dropped_not_tso_spectroscopy"] == 2  # imaging + MIRI F1000W target acquisition
    assert "syn-o004-image" not in by_obs and "syn-o005-ta" not in by_obs
    assert stats["unmatched_targets"] == {"SOME-BROWN-DWARF": 1}

    t = by_obs["syn-o001-transit"]
    assert (t["assigned_planet"], t["match_status"], t["likely_type"]) == (
        "SYN-1 b",
        "transit_in_window",
        "transmission",
    )
    assert t["stsci_url"].endswith("?id=90001")
    assert t["t_min"] == repr(59200.0123)

    e = by_obs["syn-o002-eclipse"]
    assert (e["host_match_method"], e["match_status"], e["likely_type"]) == ("name", "eclipse_in_window", "eclipse")

    n = by_obs["syn-o003-noevent"]
    assert (n["host_match_method"], n["match_status"], n["assigned_planet"]) == (
        "coordinates",
        "no_event_in_window",
        "",
    )

    u = by_obs["syn-o007-nouncert"]
    assert u["match_status"] == "ambiguous" and "ephemeris_uncertainty_missing" in u["match_note"]

    ecc = by_obs["syn-o008-eccentric"]
    assert ecc["host_match_method"] == "name_planet_suffix"
    assert ecc["match_status"] == "ambiguous" and "eccentric_orbit_eclipse_possible" in ecc["match_note"]

    order = [mast_builder.MATCH_STATUSES.index(r["match_status"]) for r in rows]
    assert order == sorted(order)


def test_hosts_filter_restricts_output(frames):
    obs, ephem = frames
    rows, _ = mast_builder.build_candidates(obs, ephem, hosts_filter=["SYN-3"])
    assert {r["hostname"] for r in rows} == {"SYN-3"}


def _cluster_obs(proposals, phase, period=5.0, t0_mjd=59000.6, half=0.1):
    recs = []
    for k, pid in enumerate(proposals):
        centre = t0_mjd + (40 + 3 * k + phase) * period
        recs.append(
            {
                "proposal_id": pid,
                "obs_id": f"syn-cluster-{k}",
                "target_name": "SYN-4",
                "instrument_name": "NIRSPEC/SLIT",
                "filters": "CLEAR;PRISM",
                "t_min": centre - half,
                "t_max": centre + half,
                "obs_title": "SYNTHETIC",
                "s_ra": 300.0,
                "s_dec": 10.0,
            }
        )
    return pd.DataFrame(recs)


def test_phase_cluster_across_programs_flags_possible_ephemeris_error():
    ephem = pd.read_csv(EPHEM_FIXTURE)
    rows, stats = mast_builder.build_candidates(_cluster_obs(["91001", "91002", "91001"], 0.3), ephem)
    assert {r["match_status"] for r in rows} == {"ambiguous"}
    assert all(r["assigned_planet"] == "SYN-4 b" for r in rows)
    assert all("possible_ephemeris_error" in r["match_note"] for r in rows)
    (cluster,) = stats["phase_clusters"]
    assert cluster["attributable"] is True
    assert cluster["mean_phase"] == pytest.approx(0.3, abs=1e-3)
    assert cluster["offset_hours_from_transit"] == pytest.approx(0.3 * 5.0 * 24, abs=0.2)


def test_phase_cluster_from_single_program_is_not_flagged():
    ephem = pd.read_csv(EPHEM_FIXTURE)
    rows, stats = mast_builder.build_candidates(_cluster_obs(["91001", "91001", "91001"], 0.3), ephem)
    assert stats["phase_clusters"] == []
    assert {r["match_status"] for r in rows} == {"no_event_in_window"}


def test_circular_phase_stats_wraps_around_zero():
    mean, std = mast_builder.circular_phase_stats([0.99, 0.01])
    assert mast_builder.phase_distance(mean, 0.0) < 1e-9
    assert std < 0.02


# ---------------------------------------------------------------------------------------------
# Outputs and safety
# ---------------------------------------------------------------------------------------------


def test_refuses_to_write_into_reference_directory():
    with pytest.raises(ValueError):
        mast_builder.assert_safe_output(mast_builder.REPO_ROOT / "backend" / "data" / "reference" / "x.csv")


def test_main_offline_writes_outputs_and_never_touches_reference_csv(tmp_path):
    ref_csv = Path(__file__).resolve().parent.parent / "data" / "reference" / "jwst_transmission_targets.csv"
    before = ref_csv.read_bytes()
    cache = tmp_path / "cache"
    _cache_from_fixtures(cache)
    out, summary = tmp_path / "cand.csv", tmp_path / "summary.md"
    code = mast_builder.main(["--cache-dir", str(cache), "--output", str(out), "--summary", str(summary), "--offline"])
    assert code == 0
    df = pd.read_csv(out)
    assert list(df.columns) == mast_builder.CANDIDATE_FIELDS
    assert (df["match_status"] == "transit_in_window").sum() == 1
    text = summary.read_text(encoding="utf-8")
    assert "| transit_in_window | 1 |" in text
    assert "SOME-BROWN-DWARF" in text
    assert ref_csv.read_bytes() == before


def test_dry_run_writes_nothing(tmp_path):
    cache = tmp_path / "cache"
    _cache_from_fixtures(cache)
    out = tmp_path / "cand.csv"
    code = mast_builder.main(
        ["--cache-dir", str(cache), "--output", str(out), "--summary", str(tmp_path / "s.md"), "--offline", "--dry-run"]
    )
    assert code == 0
    assert not out.exists()


# ---------------------------------------------------------------------------------------------
# check_mast_cache.py
# ---------------------------------------------------------------------------------------------


def _live_from_fixture(pid):
    table = Table.read(MAST_FIXTURE.read_text(encoding="utf-8"), format="ascii.ecsv")
    frame = mast_builder.mast_table_to_frame(table)
    return frame[frame["proposal_id"].astype(str) == pid].reset_index(drop=True)


def test_cache_check_passes_when_live_matches(tmp_path):
    _cache_from_fixtures(tmp_path)
    assert check_mast_cache.run_check(tmp_path, 3, 0, _live_from_fixture) == 0


def test_cache_check_fails_on_modified_title(tmp_path):
    """The v1 fabrication appended 'transmission' to a real title; any title difference must fail."""
    _cache_from_fixtures(tmp_path)

    def live(pid):
        f = _live_from_fixture(pid)
        f["obs_title"] = f["obs_title"] + " transmission"
        return f

    assert check_mast_cache.run_check(tmp_path, 1, 0, live, ["90001"]) == 1


def test_cache_check_fails_when_cached_obs_missing_live(tmp_path):
    _cache_from_fixtures(tmp_path)
    assert check_mast_cache.run_check(tmp_path, 1, 0, lambda pid: _live_from_fixture(pid).iloc[0:0], ["90002"]) == 1


def test_cache_check_fails_on_changed_time(tmp_path):
    _cache_from_fixtures(tmp_path)

    def live(pid):
        f = _live_from_fixture(pid)
        f["t_min"] = f["t_min"].astype(float) + 0.001
        return f

    assert check_mast_cache.run_check(tmp_path, 1, 0, live, ["90002"]) == 1


def test_cache_check_only_warns_on_new_live_rows():
    cached = _live_from_fixture("90002")
    extra = cached.copy()
    extra["obs_id"] = "syn-new-visit"
    failures, warnings = check_mast_cache.compare_proposal("90002", cached, pd.concat([cached, extra]))
    assert failures == []
    assert len(warnings) == 1


def test_cache_check_fails_on_tampered_sha(tmp_path):
    _cache_from_fixtures(tmp_path)
    path = tmp_path / "jwst_timeseries.ecsv"
    path.write_bytes(path.read_bytes().replace(b"Dayside emission", b"Dayside transmission"))
    assert check_mast_cache.run_check(tmp_path, 1, 0, _live_from_fixture) == 1


def test_cache_check_fails_on_whole_number_dates(tmp_path):
    table = Table.read(MAST_FIXTURE.read_text(encoding="utf-8"), format="ascii.ecsv")
    table["t_min"] = [float(round(v)) for v in table["t_min"]]
    table["t_max"] = [float(round(v)) for v in table["t_max"]]
    buf = io.StringIO()
    table.write(buf, format="ascii.ecsv")
    mast_builder.write_raw_cache(tmp_path, "jwst_timeseries", ".ecsv", buf.getvalue().encode(), {"query": {}})

    def live(pid):
        f = mast_builder.mast_table_to_frame(table)
        return f[f["proposal_id"].astype(str) == pid]

    assert check_mast_cache.run_check(tmp_path, 1, 0, live, ["90002"]) == 1


def test_fixture_files_are_marked_synthetic():
    for p in (MAST_FIXTURE, EPHEM_FIXTURE):
        assert "SYNTHETIC TEST DATA" in p.read_text(encoding="utf-8")


def test_meta_json_records_sha_and_query(tmp_path):
    _cache_from_fixtures(tmp_path)
    meta = json.loads((tmp_path / "jwst_timeseries.meta.json").read_text(encoding="utf-8"))
    assert meta["sha256"] == mast_builder.sha256_bytes(MAST_FIXTURE.read_bytes())
    assert meta["query"] == mast_builder.MAST_QUERY
