"""Tests for the MAST label-candidate builder and the live cache checker.

All observation/ephemeris data used here is SYNTHETIC TEST DATA (fictional hosts SYN-1..SYN-4) from
backend/tests/fixtures/fixture_mast_timeseries.ecsv and fixture_nasa_ephemerides.csv, or built inline.
No network access: MAST/NASA calls are patched.
"""

import importlib
import io
import json
import math
import os
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


# Tests of the window logic pass this; the program itself validates no time system (VALIDATED_TIME_SYSTEMS is empty).
VALID = frozenset({"BJD-TDB"})


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
        "pl_orbeccenerr1": 0.01,
        "pl_orbeccenerr2": -0.01,
        "pl_orbeccenlim": 0,
        "pl_orblper": 90.0,
        "pl_orblpererr1": 5.0,
        "pl_orblpererr2": -5.0,
        "pl_orblperlim": 0,
        "pl_tranmid_systemref": "BJD-TDB",
        "pl_tranmid_reflink": "SYNTHETIC ref A",
        "pl_orbper_reflink": "SYNTHETIC ref A",
        "pl_orbeccen_reflink": "SYNTHETIC ref A",
        "pl_orblper_reflink": "SYNTHETIC ref A",
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
    ev = mast_builder.assign_planet_event(59200.0123, 59200.2877, _planet(), VALID)
    assert ev["match_status"] == "transit_in_window"
    assert ev["transit_epoch"] == 100
    assert ev["predicted_mid_transit"] == pytest.approx(59200.15)
    expected_sigma_h = math.sqrt(0.0001**2 + (100 * 0.00001) ** 2) * 24
    assert ev["timing_uncertainty_hours"] == pytest.approx(expected_sigma_h, abs=1e-4)


def test_window_at_phase_half_is_not_called_an_eclipse():
    """No circular orbit is assumed, so a window at phase 0.5 is neither an eclipse nor 'no event' (P29, P30)."""
    ev = mast_builder.assign_planet_event(59201.0123, 59201.2877, _planet(), VALID)
    assert ev["match_status"] == "ambiguous"
    assert "eclipse_not_excluded" in ev["match_note"]
    assert ev["eclipse_status"] == "requires_review"


def test_window_without_transit_is_ambiguous_because_no_eclipse_is_excluded():
    ev = mast_builder.assign_planet_event(59202.5123, 59202.6877, _planet(), VALID)
    assert ev["match_status"] == "ambiguous"
    assert "eclipse_not_excluded" in ev["match_note"]


def test_event_at_window_edge_is_ambiguous():
    # transit at 59200.15, window ends 2 minutes after it
    ev = mast_builder.assign_planet_event(59199.9, 59200.1514, _planet(), VALID)
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


def test_long_window_keeps_the_transit_result_and_the_open_eclipse():
    """The eclipse field never changes a transit result; it stays open for review."""
    ev = mast_builder.assign_planet_event(59199.9, 59201.4, _planet(), VALID)
    assert ev["match_status"] == "transit_in_window"
    assert ev["eclipse_status"] == "requires_review"


def test_eccentric_orbit_eclipse_away_from_phase_half_is_not_dropped():
    """An eccentric planet's eclipse can sit far from phase 0.5 (e.g. GJ 436 b): never report no_event."""
    centre = 59000.15 + 100.62 * 2.0
    for ecc in (0.3, 0.1, 0.05, 0.0):
        ev = mast_builder.assign_planet_event(centre - 0.1, centre + 0.1, _planet(pl_orbeccen=ecc), VALID)
        assert ev["match_status"] == "ambiguous"
        assert "eclipse_not_excluded" in ev["match_note"]
        assert ev["eclipse_status"] == "requires_review"


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
    rows, stats = mast_builder.build_candidates(obs, ephem, validated_systems=VALID)
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
    assert (e["host_match_method"], e["match_status"], e["likely_type"]) == ("name", "ambiguous", "needs_review")
    assert "eclipse_not_excluded" in e["match_note"]

    n = by_obs["syn-o003-noevent"]
    assert (n["host_match_method"], n["match_status"], n["assigned_planet"]) == (
        "coordinates",
        "ambiguous",
        "SYN-1 b",
    )

    u = by_obs["syn-o007-nouncert"]
    assert u["match_status"] == "ambiguous" and "ephemeris_uncertainty_missing" in u["match_note"]

    ecc = by_obs["syn-o008-eccentric"]
    assert ecc["host_match_method"] == "name_planet_suffix"
    assert ecc["match_status"] == "ambiguous" and ecc["eclipse_status"] == "requires_review"

    order = [mast_builder.MATCH_STATUSES.index(r["match_status"]) for r in rows]
    assert order == sorted(order)
    assert all("transit_result" not in r for r in rows)


def test_program_default_validates_no_time_system(frames):
    """P26: until a time system is validated, nothing is confident, whatever the ephemeris says."""
    assert mast_builder.VALIDATED_TIME_SYSTEMS == frozenset()
    rows, _ = mast_builder.build_candidates(*frames)
    assert rows and {r["match_status"] for r in rows} == {"ambiguous"}
    assert all("time_system" in r["match_note"] or "uncertainty_missing" in r["match_note"] for r in rows)


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
    assert {r["match_status"] for r in rows} == {"ambiguous"}
    assert not any("possible_ephemeris_error" in r["match_note"] for r in rows)


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
    assert (df["match_status"] == "ambiguous").all() and len(df) == 5
    assert (df["assigned_planet"] != "").all() and df["eclipse_status"].notna().all()
    text = summary.read_text(encoding="utf-8")
    assert "| ambiguous | 5 |" in text
    assert "| transit_in_window | 0 |" in text
    assert "SOME-BROWN-DWARF" in text
    assert ref_csv.read_bytes() == before


def _tree(root):
    """Everything below root, directories included."""
    return {p.relative_to(root).as_posix(): p.read_bytes() if p.is_file() else None for p in root.rglob("*")}


def _no_network(*a, **k):
    raise AssertionError("network must not be used")


def test_dry_run_writes_nothing(tmp_path, capsys):
    cache = tmp_path / "cache"
    _cache_from_fixtures(cache)
    before = _tree(tmp_path)
    out, summary = tmp_path / "cand.csv", tmp_path / "s.md"
    with patch.object(mast_builder, "with_retries", _no_network):
        code = mast_builder.main(
            ["--cache-dir", str(cache), "--output", str(out), "--summary", str(summary), "--dry-run"]
        )
    assert code == 0
    assert not out.exists()
    assert not summary.exists()
    assert _tree(tmp_path) == before
    assert "JWST MAST candidate summary" in capsys.readouterr().out


@pytest.mark.parametrize("state", ["no-cache", "only-mast", "no-meta", "tampered", "old-columns"])
def test_dry_run_without_valid_cache_fails_clearly_and_creates_nothing(tmp_path, capsys, state):
    cache = tmp_path / "cache"
    if state != "no-cache":
        _cache_from_fixtures(cache)
    if state == "only-mast":
        (cache / "nasa_ephemerides.csv").unlink()
    if state == "no-meta":
        (cache / "jwst_timeseries.meta.json").unlink()
    if state == "tampered":
        (cache / "jwst_timeseries.ecsv").write_bytes(b"changed")
    if state == "old-columns":
        raw = EPHEM_FIXTURE.read_bytes().replace(b"pl_orbeccenlim", b"pl_other")
        mast_builder.write_raw_cache(cache, "nasa_ephemerides", ".csv", raw, {})
    before = _tree(tmp_path)
    with patch.object(mast_builder, "with_retries", _no_network):
        code = mast_builder.main(
            [
                "--cache-dir",
                str(cache),
                "--output",
                str(tmp_path / "c.csv"),
                "--summary",
                str(tmp_path / "s.md"),
                "--dry-run",
            ]
        )
    assert code == 2
    assert "[ERROR]" in capsys.readouterr().err
    assert _tree(tmp_path) == before
    assert cache.exists() is (state != "no-cache")


@pytest.mark.parametrize("other", ["--dry-run", "--offline"])
def test_force_refresh_cannot_be_combined_with_offline_modes(tmp_path, other):
    with patch.object(mast_builder, "with_retries", _no_network), pytest.raises(SystemExit) as err:
        mast_builder.main(["--cache-dir", str(tmp_path / "c"), "--force-refresh", other])
    assert err.value.code == 2


# ---------------------------------------------------------------------------------------------
# A. Write-path allow-list
# ---------------------------------------------------------------------------------------------


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """A stand-in repository root. If a path check ever regresses, these tests must not touch the real data."""
    root, temp = tmp_path / "repo", tmp_path / "tmp"
    for rel in ("backend/data/reference", "reports", "docs/assets", "scripts", ".git"):
        (root / rel).mkdir(parents=True)
    (root / "reports" / "LABEL_REVIEW.md").write_text("SYNTHETIC TEST DATA: human review log\n")
    temp.mkdir()
    monkeypatch.setattr(mast_builder, "REPO_ROOT", root)
    monkeypatch.setattr(mast_builder.tempfile, "gettempdir", lambda: str(temp))
    monkeypatch.delenv("RUNNER_TEMP", raising=False)
    return root, temp


FORBIDDEN_TARGETS = [
    "backend/data/reference",
    "backend/data/reference/x.csv",
    "BACKEND/Data/Reference/x.csv",
    "reports/.mast_cache/../../backend/data/reference/x.csv",
    "reports/LABEL_REVIEW.md",
    "reports/CYCLE4_SOURCE.md",
    "reports/k6_summary.json",
    "reports/other.csv",
    "reports",
    ".",
    "docs/assets/x.md",
    "scripts/guard_changes.py",
    ".guard.toml",
    ".git/config",
    "../another-repo/x.csv",
    ".github/workflows/x.yml",
    "docs/x.md",
    "frontend/x.js",
    "backend/app/x.py",
    ".agent/PLAN.md",
]


@pytest.mark.parametrize("flag", ["--cache-dir", "--output", "--summary"])
@pytest.mark.parametrize("target", FORBIDDEN_TARGETS)
def test_forbidden_write_paths_are_refused_before_any_fetch(flag, target, fake_repo):
    root, _ = fake_repo
    before = _tree(root)
    with (
        patch.object(mast_builder, "fetch_jwst_timeseries", _no_network),
        patch.object(mast_builder, "with_retries", _no_network),
        pytest.raises(SystemExit) as err,
    ):
        mast_builder.main([flag, target])
    assert err.value.code == 2
    assert _tree(root) == before


@pytest.mark.parametrize(
    "flag,target",
    [
        ("--cache-dir", "reports/jwst_mast_candidates.csv"),
        ("--output", "reports/jwst_mast_summary.md"),
        ("--summary", "reports/jwst_mast_candidates.csv"),
        ("--output", "reports/.mast_cache/x.csv"),
    ],
)
def test_each_flag_has_its_own_location(flag, target, fake_repo):
    root, _ = fake_repo
    with pytest.raises(ValueError):
        mast_builder.assert_safe_output(root / target, flag)


def test_default_locations_and_temp_directories_are_allowed(fake_repo):
    root, temp = fake_repo
    for flag, rel in mast_builder.ALLOWED_REPO_PATHS.items():
        assert mast_builder.assert_safe_output(root / rel, flag) == (root / rel).resolve()
        assert mast_builder.assert_safe_output(temp / "x", flag) == (temp / "x").resolve()


def test_write_targets_must_be_separate_and_of_the_right_kind(fake_repo):
    _, temp = fake_repo
    same = temp / "x"
    with pytest.raises(ValueError):
        mast_builder.check_write_paths(temp / "c", same, same)
    with pytest.raises(ValueError):
        mast_builder.check_write_paths(temp / "c", temp / "c" / "o.csv", temp / "s.md")
    (temp / "dir").mkdir()
    with pytest.raises(ValueError):
        mast_builder.check_write_paths(temp / "c", temp / "dir", temp / "s.md")


def test_low_level_writers_check_their_path_too(fake_repo):
    root, _ = fake_repo
    before = _tree(root)
    with pytest.raises(ValueError):
        mast_builder.write_raw_cache(root / "backend" / "data" / "reference", "x", ".csv", b"x", {})
    with pytest.raises(ValueError):
        mast_builder.write_candidates_csv([], root / "reports" / "LABEL_REVIEW.md")
    assert _tree(root) == before


def _link_directory(target, link):
    """Directory link that needs no special rights: a junction on Windows, a symlink elsewhere."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


def test_link_at_the_allowed_cache_location_cannot_redirect_writes(fake_repo):
    root, _ = fake_repo
    reference = root / "backend" / "data" / "reference"
    _link_directory(reference, root / "reports" / ".mast_cache")
    with pytest.raises(ValueError):
        mast_builder.write_raw_cache(root / "reports" / ".mast_cache", "x", ".csv", b"x", {})
    assert list(reference.iterdir()) == []


def test_link_in_the_temp_directory_cannot_redirect_writes(fake_repo):
    root, temp = fake_repo
    reference = root / "backend" / "data" / "reference"
    _link_directory(reference, temp / "cache")
    with pytest.raises(ValueError):
        mast_builder.write_raw_cache(temp / "cache", "x", ".csv", b"x", {})
    assert list(reference.iterdir()) == []


@pytest.mark.parametrize("name", ["jwst_mast_candidates.csv", ".mast_cache/x.csv", ".mast_cache/x.meta.json"])
def test_hard_links_to_protected_files_are_refused(name, fake_repo):
    root, _ = fake_repo
    review = root / "reports" / "LABEL_REVIEW.md"
    link = root / "reports" / name
    link.parent.mkdir(exist_ok=True)
    os.link(review, link)
    before = review.read_bytes()
    with pytest.raises(ValueError):
        if name.startswith(".mast_cache"):
            mast_builder.write_raw_cache(root / "reports" / ".mast_cache", "x", ".csv", b"x", {})
        else:
            mast_builder.write_candidates_csv([], link)
    assert review.read_bytes() == before


@pytest.mark.parametrize("flag", ["--cache-dir", "--output", "--summary"])
@pytest.mark.parametrize("target", ["reports/LABEL_REVIEW.md", "backend/data/reference/x.csv", ".github/x.yml"])
def test_absolute_forbidden_paths_are_refused(flag, target, fake_repo):
    root, _ = fake_repo
    before = _tree(root)
    with patch.object(mast_builder, "with_retries", _no_network), pytest.raises(SystemExit) as err:
        mast_builder.main([flag, str((root / target).resolve())])
    assert err.value.code == 2
    assert _tree(root) == before


def test_refusal_creates_no_directory(fake_repo):
    root, temp = fake_repo
    with patch.object(mast_builder, "with_retries", _no_network), pytest.raises(SystemExit):
        mast_builder.main(["--cache-dir", str(temp / "new" / "cache"), "--output", "reports/new/x.csv"])
    assert not (temp / "new").exists() and not (root / "reports" / "new").exists()


@pytest.mark.parametrize(
    "name", ["jwst_timeseries.ecsv", "jwst_timeseries.meta.json", "nasa_ephemerides.csv", "nasa_ephemerides.meta.json"]
)
def test_linked_cache_file_is_refused_before_any_request(name, fake_repo):
    root, _ = fake_repo
    cache = root / "reports" / ".mast_cache"
    cache.mkdir()
    os.link(root / "reports" / "LABEL_REVIEW.md", cache / name)
    with (
        patch.object(mast_builder, "fetch_jwst_timeseries", _no_network),
        patch.object(mast_builder, "with_retries", _no_network),
        pytest.raises(SystemExit) as err,
    ):
        mast_builder.main(["--force-refresh"])
    assert err.value.code == 2


def test_temp_directory_that_contains_the_repository_is_not_trusted(fake_repo, monkeypatch):
    root, _ = fake_repo
    monkeypatch.setattr(mast_builder.tempfile, "gettempdir", lambda: str(root.parent))
    with pytest.raises(ValueError):
        mast_builder.assert_safe_output(root.parent / "sibling" / "x.csv")
    monkeypatch.setenv("RUNNER_TEMP", str(root.parent))
    with pytest.raises(ValueError):
        mast_builder.assert_safe_output(root.parent / "sibling" / "x.csv")


def test_output_below_a_file_is_refused(fake_repo):
    _, temp = fake_repo
    (temp / "file").write_text("x")
    with pytest.raises(ValueError):
        mast_builder.check_write_paths(temp / "c", temp / "file" / "o.csv", temp / "s.md")


def test_default_run_writes_only_the_three_allowed_places(fake_repo):
    root, _ = fake_repo
    _cache_from_fixtures(root / "reports" / ".mast_cache")
    (root / "reports" / "jwst_mast_candidates.csv").write_text("old output\n")
    before = _tree(root)
    with patch.object(mast_builder, "with_retries", _no_network):
        assert mast_builder.main(["--offline"]) == 0
    changed = {k for k, v in _tree(root).items() if before.get(k) != v}
    assert changed == {"reports/jwst_mast_candidates.csv", "reports/jwst_mast_summary.md"}


def test_dry_run_changes_nothing_with_default_paths(fake_repo):
    root, _ = fake_repo
    _cache_from_fixtures(root / "reports" / ".mast_cache")
    before = _tree(root)
    with patch.object(mast_builder, "with_retries", _no_network):
        assert mast_builder.main(["--dry-run"]) == 0
    assert _tree(root) == before


@pytest.mark.parametrize("flag", ["--output", "--summary"])
def test_link_at_an_output_file_is_refused(flag, fake_repo):
    """A real link on every platform: a junction on Windows (needs no rights), a symlink elsewhere."""
    root, temp = fake_repo
    victim = root / "backend" / "data" / "reference"
    _link_directory(victim, temp / "link")
    o, s = (temp / "link", temp / "s.md") if flag == "--output" else (temp / "o.csv", temp / "link")
    with pytest.raises(ValueError, match=f"Refusing {flag}"):
        mast_builder.check_write_paths(temp / "c", o, s)
    assert list(victim.iterdir()) == []


def test_file_symlink_is_refused(fake_repo, monkeypatch):
    """With a real symlink where the platform allows one; otherwise the check itself is exercised."""
    root, temp = fake_repo
    link, victim = temp / "o.csv", root / "reports" / "LABEL_REVIEW.md"
    before = victim.read_bytes()
    try:
        os.symlink(victim, link)
    except OSError:  # Windows without the symlink right: make the same file answer 'yes' to is_symlink()
        link.write_text("plain file")
        monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == "o.csv")
        with pytest.raises(ValueError, match="it is a link"):
            mast_builder.write_candidates_csv([], link)
        assert link.read_text() == "plain file"
    else:
        with pytest.raises(ValueError):
            mast_builder.write_candidates_csv([], link)
    assert victim.read_bytes() == before


# ---------------------------------------------------------------------------------------------
# C. Missing ephemeris uncertainty is never zero
# ---------------------------------------------------------------------------------------------

T0_GONE = {"pl_tranmiderr1": None, "pl_tranmiderr2": None}
P_GONE = {"pl_orbpererr1": None, "pl_orbpererr2": None}
WINDOWS = {
    "hit": (59200.0123, 59200.2877),
    "near": (59200.25, 59200.45),
    "far": (59200.6, 59200.8),
    "eclipse": (59201.0123, 59201.2877),
}


@pytest.mark.parametrize("window", sorted(WINDOWS))
@pytest.mark.parametrize(
    "missing,label",
    [
        (T0_GONE, "t0"),
        (P_GONE, "period"),
        ({**T0_GONE, **P_GONE}, "t0_and_period"),
        ({"pl_tranmiderr1": 0.0, "pl_tranmiderr2": 0.0}, "t0"),
        ({"pl_orbpererr1": float("nan"), "pl_orbpererr2": float("nan")}, "period"),
        ({"pl_orbpererr1": float("inf"), "pl_orbpererr2": None}, "period"),
    ],
)
def test_missing_uncertainty_is_ambiguous_in_every_window(window, missing, label):
    ev = mast_builder.assign_planet_event(*WINDOWS[window], _planet(**missing))
    assert ev["match_status"] == "ambiguous"
    assert ev["uncertainty_status"] == f"missing_{label}"
    assert f"ephemeris_uncertainty_missing_{label}" in ev["match_note"]
    assert ev["timing_uncertainty_hours"] == ""
    assert ev["predicted_mid_transit"] != ""


def test_known_uncertainty_is_labelled():
    for name, status in (("hit", "transit_in_window"), ("far", "ambiguous"), ("eclipse", "ambiguous")):
        ev = mast_builder.assign_planet_event(*WINDOWS[name], _planet(), VALID)
        assert (ev["match_status"], ev["uncertainty_status"]) == (status, "known")


def _obs(**kw):
    base = {c: None for c in mast_builder.MAST_COLUMNS}
    base.update(
        proposal_id="90001", obs_id="syn-a", target_name="SYN-1", instrument_name="NIRSPEC/SLIT", filters="CLEAR;PRISM",
        t_min=59200.0123, t_max=59200.2877, obs_title="SYNTHETIC", s_ra=150.25, s_dec=-20.5, calib_level=3,
    )  # fmt: skip
    base.update(kw)
    return base


def _build(*recs, ephem=None, **kw):
    ephem = pd.read_csv(EPHEM_FIXTURE) if ephem is None else ephem
    return mast_builder.build_candidates(pd.DataFrame(list(recs)), ephem, **kw)


def test_missing_uncertainty_reaches_csv_summary_and_reviewer(tmp_path):
    ephem = pd.read_csv(EPHEM_FIXTURE)
    ephem.loc[ephem["pl_name"] == "SYN-1 b", ["pl_orbpererr1", "pl_orbpererr2"]] = float("nan")
    rows, stats = _build(_obs(t_min=59200.6, t_max=59200.8), ephem=ephem)
    assert [(r["assigned_planet"], r["match_status"]) for r in rows] == [("SYN-1 b", "ambiguous")]
    assert stats["uncertainty_missing_rows"] == 1
    out = tmp_path / "c.csv"
    mast_builder.write_candidates_csv(rows, out)
    review = importlib.import_module("review_labels")
    (group,) = review.build_groups(review.load_candidates(out))
    assert "UNVERIFIED TIMING: missing_period" in review.format_group(group, 1, 1)


# ---------------------------------------------------------------------------------------------
# D. No margin, no bound, no pretended conversion
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("seconds,status", [(-1, "ambiguous"), (1, "transit_in_window")])
def test_only_three_sigma_decides_the_window_edge(seconds, status):
    sigma = math.sqrt(0.0001**2 + (100 * 0.00001) ** 2)
    end = 59200.15 + 3 * sigma + seconds / 86400
    assert mast_builder.assign_planet_event(59199.9, end, _planet(), VALID)["match_status"] == status


@pytest.mark.parametrize("system", [None, "", float("nan"), "BJD-TDB", "BJD_TDB", "BJD", "HJD", "JD-UTC", "local"])
@pytest.mark.parametrize("window", ["hit", "far", "eclipse"])
def test_no_time_system_is_confident_by_default(system, window):
    ev = mast_builder.assign_planet_event(*WINDOWS[window], _planet(pl_tranmid_systemref=system))
    assert ev["match_status"] == "ambiguous"
    assert "time_system" in ev["match_note"]


@pytest.mark.parametrize("system", ["bjd-tdb", "BJD-TDB ", "BJD_TDB", "BJD"])
def test_validated_system_must_match_exactly(system):
    ev = mast_builder.assign_planet_event(*WINDOWS["hit"], _planet(pl_tranmid_systemref=system), VALID)
    assert (ev["match_status"] == "transit_in_window") is (system.strip() == "BJD-TDB")


def test_raw_times_are_preserved_and_margin_flag_is_gone(tmp_path):
    rows, _ = _build(_obs(t_min=59200.01234567891, t_max=59200.2877))
    assert rows[0]["t_min"] == repr(59200.01234567891)
    with pytest.raises(SystemExit):
        mast_builder.main(["--margin-hours", "0.25", "--cache-dir", str(tmp_path / "c")])
    for name in ("DEFAULT_MARGIN_HOURS", "TIME_REFERENCE_BOUND_S", "ECCENTRIC_LIMIT"):
        assert not hasattr(mast_builder, name)


# ---------------------------------------------------------------------------------------------
# E. Identity, host/planet assignment, provenance
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, "", "  ", float("nan")])
def test_rows_without_obs_id_are_dropped_and_counted(value):
    rows, stats = _build(_obs(obs_id=value), _obs(obs_id=value, proposal_id="2"), _obs())
    assert [r["obs_id"] for r in rows] == ["syn-a"]
    assert stats["dropped_missing_obs_id"] == 2


def test_identical_duplicates_merge_and_conflicting_ones_abort():
    rows, stats = _build(_obs(), _obs())
    assert len(rows) == 1 and stats["merged_identical_rows"] == 1
    for change in ({"proposal_id": "2"}, {"obs_title": "other"}, {"t_min": 59200.02}, {"target_name": "SYN-3"}):
        with pytest.raises(mast_builder.ObservationIdentityError):
            _build(_obs(), _obs(**change))


def test_conflicting_duplicates_make_main_fail_without_output(tmp_path, capsys):
    cache = tmp_path / "cache"
    _cache_from_fixtures(cache)
    raw = MAST_FIXTURE.read_text(encoding="utf-8").replace("syn-o002-eclipse", "syn-o001-transit").encode()
    mast_builder.write_raw_cache(cache, "jwst_timeseries", ".ecsv", raw, {})
    out = tmp_path / "c.csv"
    assert (
        mast_builder.main(
            ["--cache-dir", str(cache), "--output", str(out), "--summary", str(tmp_path / "s.md"), "--offline"]
        )
        == 2
    )
    assert "syn-o001-transit" in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize(
    "change,note",
    [
        ({"s_ra": 160.0}, "host_position_disagree"),
        ({"s_ra": None, "s_dec": None}, "host_position_missing"),
        ({"target_name": "SYN-1 B", "s_ra": 160.0}, "host_position_disagree"),
    ],
)
def test_name_match_needs_agreeing_position(change, note):
    rows, _ = _build(_obs(**change))
    assert [r["match_status"] for r in rows] == ["ambiguous"]
    assert note in rows[0]["match_note"]


def test_suffix_must_be_a_known_planet_of_the_host():
    assert len(_build(_obs(target_name="SYN-1 b"))[0]) == 1
    rows, stats = _build(_obs(target_name="SYN-1 z", s_ra=10.0))
    assert rows == [] and stats["unmatched_targets"] == {"SYN-1 z": 1}


def test_target_named_after_another_planet_is_ambiguous():
    ephem = pd.read_csv(EPHEM_FIXTURE)
    second = ephem[ephem["pl_name"] == "SYN-1 b"].assign(pl_name="SYN-1 c", pl_tranmid=2459000.1, pl_orbper=7.0)
    rows, _ = _build(_obs(target_name="SYN-1 c"), ephem=pd.concat([ephem, second]))
    (b_row,) = [r for r in rows if r["assigned_planet"] == "SYN-1 b"]
    assert b_row["match_status"] == "ambiguous" and "target_name_gives_another_planet" in b_row["match_note"]


def test_several_planets_in_one_window_are_noted():
    ephem = pd.read_csv(EPHEM_FIXTURE)
    second = ephem[ephem["pl_name"] == "SYN-1 b"].assign(pl_name="SYN-1 c")
    rows, _ = _build(_obs(), ephem=pd.concat([ephem, second]), validated_systems=VALID)
    assert len(rows) == 2 and all("several_planets" in r["match_note"] for r in rows)


def test_planned_observations_are_not_candidates():
    rows, stats = _build(_obs(calib_level=-1))
    assert rows == [] and stats["dropped_not_executed"] == 1


def test_mixed_references_are_noted_and_recorded():
    ephem = pd.read_csv(EPHEM_FIXTURE)
    ephem["pl_orbper_reflink"] = "SYNTHETIC ref B"
    (row,) = _build(_obs(), ephem=ephem)[0]
    assert "t0_and_period_from_different_references" in row["match_note"]
    assert (row["tranmid_reference"], row["period_reference"]) == ("SYNTHETIC ref A", "SYNTHETIC ref B")


def test_every_row_carries_its_provenance(tmp_path):
    cache, out = tmp_path / "cache", tmp_path / "c.csv"
    _cache_from_fixtures(cache)
    assert (
        mast_builder.main(
            ["--cache-dir", str(cache), "--output", str(out), "--summary", str(tmp_path / "s.md"), "--offline"]
        )
        == 0
    )
    df = pd.read_csv(out)
    assert set(df["mast_cache_sha256"]) == {mast_builder.sha256_bytes(MAST_FIXTURE.read_bytes())}
    assert set(df["ephemeris_cache_sha256"]) == {mast_builder.sha256_bytes(EPHEM_FIXTURE.read_bytes())}
    assert df["mast_row_sha256"].str.fullmatch(r"[0-9a-f]{64}").all()


def test_completeness_check():
    check = importlib.import_module("check_mast_completeness")
    bulk = pd.DataFrame([_obs()])
    extra = _obs(obs_id="syn-only-spectrum")
    image = _obs(obs_id="syn-image", instrument_name="NIRCAM/IMAGE", filters="F210M")
    assert check.run(bulk, ["SYN-1"], lambda names: pd.DataFrame([_obs(), image])) == 0
    assert check.run(bulk, ["SYN-1"], lambda names: pd.DataFrame([_obs(), extra])) == 1
    assert check.run(bulk, [], lambda names: bulk) == 1
    assert check.run(bulk, ["SYN-1"], _no_network) == 1
    assert {"WASP-39", "WASP39", "WASP 39"} <= set(check.name_variants("WASP-39"))


# ---------------------------------------------------------------------------------------------
# F. check_mast_cache: any difference fails
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case,message",
    [
        ("missing", "cached obs_id syn-o002-eclipse does not exist in live MAST"),
        ("extra", "live obs_id syn-other is not in the cache"),
        ("extra", "row count differs: cache 1, live MAST 2"),
        ("swapped", "cached obs_id syn-o002-eclipse does not exist in live MAST"),
        ("swapped", "live obs_id syn-other is not in the cache"),
        ("dup-live", "obs_id syn-o002-eclipse appears 2 times in live MAST"),
        ("dup-both", "obs_id syn-o002-eclipse appears 2 times in cache"),
        ("no-id", "row(s) without obs_id in cache"),
        ("no-id", "row(s) without obs_id in live MAST"),
        ("conflict", "obs_title differs"),
    ],
)
def test_cache_check_fails_on_any_record_difference(case, message):
    cached = _live_from_fixture("90002")
    other = cached.assign(obs_id="syn-other")
    live = {
        "missing": cached.iloc[0:0],
        "extra": pd.concat([cached, other]),
        "swapped": other,
        "dup-live": pd.concat([cached, cached]),
        "dup-both": pd.concat([cached, cached]),
        "no-id": cached.assign(obs_id=None),
        "conflict": pd.concat([cached, cached.assign(obs_title="changed")]),
    }[case]
    if case == "dup-both":
        cached = pd.concat([cached, cached])
    if case == "no-id":
        cached = cached.assign(obs_id=None)
    failures, _ = check_mast_cache.compare_proposal("90002", cached, live)
    assert any(message in f for f in failures), failures


def test_cache_check_verifies_candidate_provenance(tmp_path):
    cache, out = tmp_path / "cache", tmp_path / "c.csv"
    _cache_from_fixtures(cache)
    mast_builder.main(
        ["--cache-dir", str(cache), "--output", str(out), "--summary", str(tmp_path / "s.md"), "--offline"]
    )

    def check():
        return check_mast_cache.run_check(cache, 3, 0, _live_from_fixture, None, out)

    assert check() == 0
    good = out.read_text(encoding="utf-8")
    df = pd.read_csv(out, dtype=str, keep_default_na=False)
    for column in ("mast_row_sha256", "mast_cache_sha256", "obs_id"):
        df.assign(**{column: "0" * 64}).to_csv(out, index=False)
        assert check() == 1, column
    df.drop(columns=["mast_row_sha256"]).to_csv(out, index=False)
    assert check() == 1
    out.write_text(good, encoding="utf-8")
    assert check() == 0


# ---------------------------------------------------------------------------------------------
# G. Eclipses: inputs and status only (E01-E22 of the eclipse design)
# ---------------------------------------------------------------------------------------------

ECLIPSE_TIME_WORDS = ("predicted_mid_eclipse", "eclipse_epoch", "eclipse_window", "eclipse_uncertainty")


@pytest.mark.parametrize(
    "change,status,reason",
    [
        ({}, "requires_review", "omega_convention_not_confirmed"),
        ({"pl_orbeccen": 0.05}, "requires_review", "prediction_deferred"),
        ({"pl_orbeccen": 0.1}, "requires_review", "prediction_deferred"),
        ({"pl_orbeccen": None}, "indeterminate", "eccentricity_unknown"),
        ({"pl_orbeccen": float("nan")}, "indeterminate", "eccentricity_unknown"),
        ({"pl_orbeccen": ""}, "indeterminate", "eccentricity_unknown"),
        ({"pl_orbeccen": -0.1}, "requires_review", "eccentricity_invalid"),
        ({"pl_orbeccen": 1.0}, "requires_review", "eccentricity_invalid"),
        ({"pl_orbeccen": float("inf")}, "requires_review", "eccentricity_invalid"),
        ({"pl_orbeccenlim": 1}, "requires_review", "eccentricity_is_limit_or_flag_not_understood"),
        ({"pl_orbeccenlim": -1}, "requires_review", "eccentricity_is_limit_or_flag_not_understood"),
        ({"pl_orbeccenlim": "upper"}, "requires_review", "eccentricity_is_limit_or_flag_not_understood"),
        ({"pl_orbeccenlim": None}, "requires_review", "eccentricity_is_limit_or_flag_not_understood"),
        (
            {"pl_orbeccen": 0.0, "pl_orbeccenerr1": None, "pl_orbeccenerr2": None},
            "requires_review",
            "eccentricity_zero_may_be_assumed",
        ),
        ({"pl_orbeccenerr1": None, "pl_orbeccenerr2": None}, "requires_review", "eccentricity_uncertainty_missing"),
        ({"pl_orbeccenerr1": 0.0, "pl_orbeccenerr2": 0.0}, "requires_review", "eccentricity_uncertainty_missing"),
        ({"pl_orblper": None}, "requires_review", "omega_missing"),
        ({"pl_orblper": 0.0}, "requires_review", "omega_convention_not_confirmed"),
        ({"pl_orblper": -10.0}, "requires_review", "omega_convention_not_confirmed"),
        ({"pl_orblperlim": 1}, "requires_review", "omega_is_limit_or_flag_not_understood"),
        ({"pl_orblpererr1": None, "pl_orblpererr2": None}, "requires_review", "omega_uncertainty_missing"),
        ({"pl_tranmid": None}, "insufficient_parameters", "missing_t0"),
        ({"pl_orbper": None}, "insufficient_parameters", "missing_period"),
        ({"pl_orbper": -1.0}, "insufficient_parameters", "missing_period"),
        ({"pl_tranmiderr1": None, "pl_tranmiderr2": None}, "requires_review", "t0_uncertainty_missing"),
        ({"pl_orbpererr1": None, "pl_orbpererr2": None}, "requires_review", "period_uncertainty_missing"),
        ({"pl_orblper_reflink": "SYNTHETIC ref B"}, "requires_review", "references_missing_or_mixed"),
        ({"pl_orbeccen_reflink": None}, "requires_review", "references_missing_or_mixed"),
        ({"pl_tranmid_systemref": None}, "requires_review", "time_system_not_validated"),
        ({"pl_tranmid_systemref": "BJD-TDB"}, "requires_review", "time_system_not_validated"),
    ],
)
@pytest.mark.parametrize("window", ["hit", "eclipse"])
def test_eclipse_status_and_reason(change, status, reason, window):
    ev = mast_builder.assign_planet_event(*WINDOWS[window], _planet(**change), VALID)
    assert ev["eclipse_status"] == status
    assert reason in ev["eclipse_reasons"].split(";")
    assert "prediction_deferred" in ev["eclipse_reasons"]
    assert ev["match_status"] in ("ambiguous", "transit_in_window")
    assert not [k for k in ev if any(w in k for w in ECLIPSE_TIME_WORDS)]


def test_all_reasons_are_listed_not_only_the_first():
    _, reasons = mast_builder.eclipse_status({})
    for r in ("missing_t0", "missing_period", "eccentricity_unknown", "omega_missing", "references_missing_or_mixed"):
        assert r in reasons


def test_no_output_column_can_hold_an_eclipse_time():
    assert not [c for c in mast_builder.CANDIDATE_FIELDS if any(w in c for w in ECLIPSE_TIME_WORDS)]
    assert "transit_result" not in mast_builder.CANDIDATE_FIELDS


def test_eclipse_inputs_never_change_the_transit_result():
    reference = mast_builder.assign_planet_event(*WINDOWS["hit"], _planet(), VALID)
    for change in ({"pl_orbeccen": None}, {"pl_orbeccen": 0.9}, {"pl_orblper": None}, {"pl_orbeccenlim": 1}):
        ev = mast_builder.assign_planet_event(*WINDOWS["hit"], _planet(**change), VALID)
        for key in ("match_status", "transit_epoch", "predicted_mid_transit", "timing_uncertainty_hours"):
            assert ev[key] == reference[key]


def test_every_pair_is_listed_and_raw_orbit_values_are_kept():
    rows, stats = _build(_obs(t_min=59200.6, t_max=59200.8))
    assert [r["assigned_planet"] for r in rows] == ["SYN-1 b"]
    assert (rows[0]["ecc"], rows[0]["omega_deg"], rows[0]["omega_convention"]) == ("0.0", "90.0", "unconfirmed")
    assert stats["eclipse_status"] == {"requires_review": 1}


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


def test_cache_check_fails_on_new_live_rows():
    """PLAN.md Phase 2: FAIL if the row count differs, including when live MAST has more rows."""
    cached = _live_from_fixture("90002")
    extra = cached.copy()
    extra["obs_id"] = "syn-new-visit"
    failures, warnings = check_mast_cache.compare_proposal("90002", cached, pd.concat([cached, extra]))
    assert any("row count differs" in f for f in failures)
    assert any("syn-new-visit is not in the cache" in f for f in failures)
    assert warnings == []


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
