"""Tests for scripts/review_labels.py (interactive label review).

SYNTHETIC TEST DATA: fictional hosts SYN-1/SYN-2/SYN-9 and proposals 90001-90003. input() is monkeypatched.
"""

import builtins
import csv
import datetime as dt
import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

review_labels = importlib.import_module("review_labels")
integrity = importlib.import_module("check_data_integrity")
builder = importlib.import_module("build_jwst_labels_from_mast")

TODAY = dt.date(2026, 11, 22)


def _row(**kw):
    base = {k: "" for k in builder.CANDIDATE_FIELDS}
    base.update(
        {
            "hostname": "SYN-1",
            "target_name": "SYN-1",
            "host_match_method": "name",
            "assigned_planet": "SYN-1 b",
            "in_eligible_catalog": "True",
            "proposal_id": "90001",
            "obs_id": "syn-o1",
            "instrument_name": "NIRSPEC/SLIT",
            "filters": "CLEAR;PRISM",
            "t_min": "59200.0123",
            "t_max": "59200.2877",
            "window_hours": "6.61",
            "predicted_mid_transit": "59200.15",
            "timing_uncertainty_hours": "0.0241",
            "match_status": "transit_in_window",
            "obs_title": "Transmission spectroscopy of SYN-1 b",
            "likely_type": "transmission",
        }
    )
    base.update(kw)
    return base


@pytest.fixture
def paths(tmp_path):
    rows = [
        _row(),
        _row(obs_id="syn-o2", instrument_name="NIRISS/SOSS", filters="CLEAR;GR700XD"),
        _row(
            assigned_planet="SYN-2 b",
            hostname="SYN-2",
            proposal_id="90002",
            obs_id="syn-o3",
            match_status="ambiguous",
            match_note="event_near_window_edge",
            likely_type="needs_review",
        ),
        _row(
            assigned_planet="",
            hostname="SYN-9",
            proposal_id="90003",
            obs_id="syn-o4",
            match_status="ambiguous",
            match_note="unexplained_window_phase_clusters_in_multi_planet_system",
        ),
        _row(assigned_planet="SYN-1 b", proposal_id="90009", obs_id="syn-o5", match_status="eclipse_in_window"),
        _row(assigned_planet="", proposal_id="90010", obs_id="syn-o6", match_status="no_event_in_window"),
    ]
    cand = tmp_path / "cand.csv"
    with open(cand, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=builder.CANDIDATE_FIELDS)
        w.writeheader()
        w.writerows(rows)
    targets = tmp_path / "targets.csv"
    targets.write_text(
        ",".join(review_labels.TARGET_FIELDS) + "\n"
        "SYN-1 b,,1,NIRSpec,,unknown,False,True,old AI-era row without a valid ID\n"
        "SYN-7 b,1111,1,NIRSpec,https://example.invalid/1111,unknown,False,True,untouched\n",
        encoding="utf-8",
    )
    review = tmp_path / "REVIEW.md"
    review.write_text("# SYNTHETIC TEST DATA review log\n", encoding="utf-8")
    return cand, targets, review


def _feed(monkeypatch, answers):
    it = iter(answers)
    prompts = []

    def fake_input(prompt=""):
        prompts.append(prompt)
        return next(it)

    monkeypatch.setattr(builtins, "input", fake_input)
    return prompts


def _targets(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_groups_only_reviewable_rows_with_transits_first(paths):
    cand, _, _ = paths
    groups = review_labels.build_groups(review_labels.load_candidates(cand))
    assert [(g.planet, g.proposal_id, g.status) for g in groups] == [
        ("SYN-1 b", "90001", "transit_in_window"),
        ("SYN-2 b", "90002", "ambiguous"),
        ("", "90003", "ambiguous"),
    ]
    assert groups[0].obs_ids == ["syn-o1", "syn-o2"]
    assert groups[0].mode == "NIRISS/SOSS CLEAR;GR700XD; NIRSPEC/SLIT CLEAR;PRISM"


def test_approve_writes_review_row_then_verified_target(monkeypatch, paths):
    cand, targets, review = paths
    _feed(monkeypatch, ["Reviewer A", "a", "1", "y", "checked program page", "q"])
    counts = review_labels.run_review(cand, targets, review, today=TODAY)
    assert counts["approved"] == 1

    rows = _targets(targets)
    syn1 = [r for r in rows if r["planet_name"] == "SYN-1 b"]
    assert len(syn1) == 1, "approval must fill the existing unverified row that had no program id"
    r = syn1[0]
    assert (r["program_id"], r["verified"], r["observation_type"], r["cycle"]) == ("90001", "True", "transmission", "1")
    assert r["source_url"].endswith("?id=90001")
    assert r["needs_review"] == "False"
    assert [x for x in rows if x["planet_name"] == "SYN-7 b"][0]["notes"] == "untouched"

    text = review.read_text(encoding="utf-8")
    assert review_labels.REVIEW_HEADER in text
    assert "| SYN-1 b | 90001 |" in text and "Reviewer A | 2026-11-22 | APPROVED: transmission | syn-o1; syn-o2" in text
    failures, verified, _ = integrity.check_transmission_targets(targets, review)
    assert failures == [] and verified == 1


def test_approval_needs_explicit_confirmation(monkeypatch, paths):
    cand, targets, review = paths
    before = targets.read_bytes()
    _feed(monkeypatch, ["Reviewer A", "a", "", "n", "q"])
    counts = review_labels.run_review(cand, targets, review, today=TODAY)
    assert counts == {"approved": 0, "rejected": 0, "skipped": 1}
    assert targets.read_bytes() == before
    assert "APPROVED" not in review.read_text(encoding="utf-8")


def test_reject_as_emission_is_logged_unverified(monkeypatch, paths):
    cand, targets, review = paths
    _feed(monkeypatch, ["Reviewer A", "e", "eclipse only | per STScI page", "q"])
    review_labels.run_review(cand, targets, review, today=TODAY)
    row = [r for r in _targets(targets) if r["program_id"] == "90001"][0]
    assert (row["verified"], row["observation_type"]) == ("False", "emission")
    text = review.read_text(encoding="utf-8")
    assert "REJECTED: emission" in text
    assert "eclipse only \\| per STScI page" in text  # pipe escaped, table stays valid


def test_skip_and_quit_write_nothing(monkeypatch, paths):
    cand, targets, review = paths
    before_t, before_r = targets.read_bytes(), review.read_bytes()
    _feed(monkeypatch, ["Reviewer A", "s", "q"])
    counts = review_labels.run_review(cand, targets, review, today=TODAY)
    assert counts["skipped"] == 1
    assert targets.read_bytes() == before_t and review.read_bytes() == before_r


def test_invalid_choice_and_cycle_are_reasked(monkeypatch, paths):
    cand, targets, review = paths
    prompts = _feed(monkeypatch, ["Reviewer A", "x", "a", "one", "2", "y", "", "q"])
    review_labels.run_review(cand, targets, review, today=TODAY)
    assert sum("Please" in p or "[a]pprove" in p for p in prompts) >= 2
    assert [r for r in _targets(targets) if r["program_id"] == "90001"][0]["cycle"] == "2"


def test_review_is_resumable(monkeypatch, paths, capsys):
    cand, targets, review = paths
    _feed(monkeypatch, ["Reviewer A", "a", "1", "y", "", "q"])
    review_labels.run_review(cand, targets, review, today=TODAY)
    capsys.readouterr()
    _feed(monkeypatch, ["Reviewer A", "q"])
    review_labels.run_review(cand, targets, review, today=TODAY)
    out = capsys.readouterr().out
    assert "3 candidate groups, 1 already decided, 2 pending." in out
    assert "SYN-1 b   host SYN-1   proposal 90001" not in out


def test_host_level_group_asks_for_a_valid_planet(monkeypatch, paths):
    cand, targets, review = paths
    _feed(monkeypatch, ["Reviewer A", "s", "s", "a", "SYN-1 b", "SYN-9 c", "", "y", "", "q"])
    review_labels.run_review(cand, targets, review, today=TODAY)
    row = [r for r in _targets(targets) if r["program_id"] == "90003"][0]
    assert (row["planet_name"], row["verified"]) == ("SYN-9 c", "True")
    groups = review_labels.build_groups(review_labels.load_candidates(cand))
    decided = review_labels.decision_rows(review.read_text(encoding="utf-8"))
    assert review_labels.is_decided(groups[2], decided)


def test_summary_counts_and_threshold(monkeypatch, paths):
    cand, targets, review = paths
    _feed(monkeypatch, ["Reviewer A", "a", "1", "y", "", "r", "not a transit", "q"])
    review_labels.run_review(cand, targets, review, today=TODAY)
    s = review_labels.summarize(cand, targets, review)
    assert s["approved_decisions"] == 1
    assert s["rejected_decisions"] == 1
    assert s["pending_groups"] == 1
    assert s["verified_transmission_planets"] == 1
    assert s["enough_for_training"] is False
    assert s["missing_for_training"] == review_labels.MIN_APPROVED_PLANETS - 1
    assert s["problems"] == []


def test_summary_flags_verified_row_without_approval(paths):
    cand, targets, review = paths
    targets.write_text(
        ",".join(review_labels.TARGET_FIELDS) + "\nSYN-5 b,5555,1,x,https://x/5555,transmission,True,False,\n",
        encoding="utf-8",
    )
    s = review_labels.summarize(cand, targets, review)
    assert s["verified_transmission_planets"] == 0
    assert len(s["problems"]) == 1


def test_missing_candidates_file_explains_next_step(tmp_path):
    with pytest.raises(FileNotFoundError, match="build_jwst_labels_from_mast"):
        review_labels.load_candidates(tmp_path / "missing.csv")


def test_mjd_to_iso_matches_astropy():
    from astropy.time import Time

    for mjd in ("59200.0", "59782.783412233795"):
        expected = Time(float(mjd), format="mjd").datetime.strftime("%Y-%m-%d %H:%M UTC")
        assert review_labels.mjd_to_iso(mjd) == expected
    assert review_labels.mjd_to_iso("59200.0") == "2020-12-17 00:00 UTC"
    assert review_labels.mjd_to_iso("not a number") == "?"
