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
            "uncertainty_status": "known",
            "time_system": "BJD-TDB",
            "mast_row_sha256": "a" * 64,
            "mast_cache_sha256": "b" * 64,
            "ephemeris_cache_sha256": "c" * 64,
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


@pytest.fixture
def validated(monkeypatch):
    """Pretend that a time system has been validated and that the cached archive data confirm every row.

    The program itself validates none. The comparison with the archive data is tested in test_label_evidence.py.
    """
    monkeypatch.setattr(builder, "VALIDATED_TIME_SYSTEMS", frozenset({"BJD-TDB"}))
    monkeypatch.setattr(review_labels, "evidence_problems", lambda rows: [[] for _ in rows])
    monkeypatch.setattr(review_labels, "obsolete_approval", lambda decision, rebuilt: None)


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


def test_approve_writes_review_row_then_verified_target(monkeypatch, paths, validated):
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


def test_approval_needs_explicit_confirmation(monkeypatch, paths, validated):
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


def test_invalid_choice_and_cycle_are_reasked(monkeypatch, paths, validated):
    cand, targets, review = paths
    prompts = _feed(monkeypatch, ["Reviewer A", "x", "a", "one", "2", "y", "", "q"])
    review_labels.run_review(cand, targets, review, today=TODAY)
    assert sum("Please" in p or "[a]pprove" in p for p in prompts) >= 2
    assert [r for r in _targets(targets) if r["program_id"] == "90001"][0]["cycle"] == "2"


def test_review_is_resumable(monkeypatch, paths, capsys, validated):
    cand, targets, review = paths
    _feed(monkeypatch, ["Reviewer A", "a", "1", "y", "", "q"])
    review_labels.run_review(cand, targets, review, today=TODAY)
    capsys.readouterr()
    _feed(monkeypatch, ["Reviewer A", "q"])
    review_labels.run_review(cand, targets, review, today=TODAY)
    out = capsys.readouterr().out
    assert "3 candidate groups, 1 already decided, 2 pending." in out
    assert "SYN-1 b   host SYN-1   proposal 90001" not in out


def test_host_level_group_cannot_be_approved_but_can_be_rejected(monkeypatch, paths, validated, capsys):
    """Without an assigned planet there is nothing to approve; typing a planet name was enough before."""
    cand, targets, review = paths
    _feed(monkeypatch, ["Reviewer A", "s", "s", "a", "q"])
    before = targets.read_bytes(), review.read_bytes()
    assert review_labels.run_review(cand, targets, review, today=TODAY)["approved"] == 0
    assert (targets.read_bytes(), review.read_bytes()) == before
    assert "no planet is assigned" in capsys.readouterr().out
    _feed(monkeypatch, ["Reviewer A", "s", "s", "r", "", "q"])
    review_labels.run_review(cand, targets, review, today=TODAY)
    groups = review_labels.build_groups(review_labels.load_candidates(cand))
    assert review_labels.is_decided(groups[2], review_labels.decision_rows(review.read_text(encoding="utf-8")))


def test_summary_counts_and_threshold(monkeypatch, paths, validated):
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


# --- Phase 2 compatibility: eclipse and uncertainty information is shown, never decided on ---

ORBIT = {
    "eclipse_status": "requires_review",
    "eclipse_reasons": "omega_convention_not_confirmed;prediction_deferred",
    "ecc": "0.05",
    "ecc_err1": "0.01",
    "ecc_err2": "-0.01",
    "ecc_limit_flag": "0",
    "ecc_reference": "SYNTHETIC ref A",
    "omega_deg": "350.0",
    "time_system": "BJD-TDB",
}


def _write_candidates(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=builder.CANDIDATE_FIELDS)
        w.writeheader()
        w.writerows(rows)


def test_eclipse_list_shows_every_row_also_without_a_time(capsys, monkeypatch, tmp_path):
    cand = tmp_path / "c.csv"
    rows = [
        _row(),
        _row(obs_id="syn-a", match_status="ambiguous", **ORBIT),
        _row(obs_id="syn-b", match_status="ambiguous", eclipse_status="indeterminate", predicted_mid_transit=""),
        _row(obs_id="syn-c", match_status="no_event_in_window", eclipse_status="insufficient_parameters"),
        _row(obs_id="syn-d", eclipse_status="excluded"),
    ]
    _write_candidates(cand, rows)
    before = cand.read_bytes()
    monkeypatch.setattr(builtins, "input", lambda *a: (_ for _ in ()).throw(AssertionError("must not ask")))
    assert review_labels.main(["--eclipses", "--candidates", str(cand)]) == 0
    text = capsys.readouterr().out
    assert "4 row(s)" in text
    for name in ("syn-o1", "syn-a", "syn-b", "syn-c"):
        assert name in text
    assert "syn-d" not in text
    assert text.count("no predicted time") == 4
    assert cand.read_bytes() == before and sorted(p.name for p in tmp_path.iterdir()) == ["c.csv"]


def test_both_omega_conventions_are_shown_and_differ_by_180():
    (group,) = review_labels.build_groups([_row(match_status="ambiguous", **ORBIT)])
    text = review_labels.format_group(group, 1, 1)
    assert "star's omega is 350.0" in text and "star's omega is 170" in text
    assert "convention unconfirmed" in text and "e = 0.05" in text
    assert "omega_convention_not_confirmed" in text


def test_eclipse_status_never_creates_or_changes_a_decision_group():
    """Approving a transit must not record other observations because of their eclipse status."""
    plain = review_labels.build_groups([_row()])
    mixed = review_labels.build_groups([_row(**ORBIT), _row(obs_id="syn-e", match_status="eclipse_in_window", **ORBIT)])
    assert [g.obs_ids for g in plain] == [g.obs_ids for g in mixed] == [["syn-o1"]]


def test_review_prompt_shows_uncertainty_flag():
    (group,) = review_labels.build_groups([_row(match_status="ambiguous", uncertainty_status="missing_t0_and_period")])
    assert "UNVERIFIED TIMING: missing_t0_and_period" in review_labels.format_group(group, 1, 1)


def test_old_candidate_files_without_new_columns_still_display():
    new = {"uncertainty_status", "time_system", "eclipse_status", "eclipse_reasons", "ecc", "omega_deg"}
    row = {k: v for k, v in _row().items() if k not in new}
    (group,) = review_labels.build_groups([row])
    text = review_labels.format_group(group, 1, 1)
    assert "UNVERIFIED" not in text and "eclipse: unknown, no predicted time" in text


@pytest.mark.parametrize("order", ["approved-first", "rejected-first"])
def test_rejected_overrides_approved(tmp_path, order):
    head = review_labels.REVIEW_HEADER + "\n" + review_labels.REVIEW_ALIGN + "\n"
    ok = "| SYN-1 b | 90001 | u | rev | 2026-11-01 | APPROVED: transmission | o | |\n"
    no = "| SYN-1 b | 90001 | u | rev | 2026-11-02 | REJECTED: emission | o | |\n"
    text = head + (ok + no if order == "approved-first" else no + ok)
    assert integrity.has_approval_row(head + ok, "SYN-1 b", "90001")
    assert not integrity.has_approval_row(text, "SYN-1 b", "90001")
    assert integrity.has_approval_row(head + ok + no.replace("90001", "90002"), "SYN-1 b", "90001")
    review = tmp_path / "R.md"
    review.write_text(text)
    summary = review_labels.summarize(tmp_path / "none.csv", tmp_path / "none2.csv", review)
    assert any("REJECTED overrides" in p for p in summary["problems"])


def test_filled_note_is_not_a_reviewer():
    head = review_labels.REVIEW_HEADER + "\n" + review_labels.REVIEW_ALIGN + "\n"
    assert not integrity.has_approval_row(
        head + "| SYN-1 b | 90001 | u | | 2026-11-01 | APPROVED: transmission | o | a note |\n", "SYN-1 b", "90001"
    )


# --- R1: what can become a verified label -------------------------------------------------------------------------


def _review(tmp_path, rows, answers, review_text="# SYNTHETIC TEST DATA\n"):
    """Run one review session; returns (counts, targets text, review text, was anything written)."""
    cand, targets, review = tmp_path / "c.csv", tmp_path / "t.csv", tmp_path / "R.md"
    _write_candidates(cand, rows)
    targets.write_text(",".join(review_labels.TARGET_FIELDS) + "\n", encoding="utf-8")
    review.write_text(review_text, encoding="utf-8")
    before = targets.read_bytes(), review.read_bytes()
    feed = iter(answers)
    counts = review_labels.run_review(cand, targets, review, input_fn=lambda _prompt: next(feed), today=TODAY)
    return counts, targets.read_text(encoding="utf-8"), review, (targets.read_bytes(), review.read_bytes()) != before


APPROVE = ["SYNTHETIC REVIEWER", "a", "1", "y", "", "q"]
BLOCKING = [
    {"match_status": "ambiguous"},
    {"uncertainty_status": "missing_period"},
    {"uncertainty_status": ""},
    {"time_system": "unknown"},
    {"time_system": ""},
    {"time_system": "bjd-tdb"},
    {"obs_id": ""},
    {"mast_row_sha256": ""},
    {"mast_cache_sha256": ""},
    {"ephemeris_cache_sha256": ""},
]


def test_nothing_can_be_approved_by_default(tmp_path, capsys):
    """H2 is blocked: the program validates no time system, whatever the candidate file says."""
    assert builder.VALIDATED_TIME_SYSTEMS == frozenset()
    counts, targets, _, written = _review(tmp_path, [_row()], APPROVE)
    assert counts == {"approved": 0, "rejected": 0, "skipped": 1} and not written
    assert "True" not in targets
    assert "time system 'BJD-TDB' is not validated" in capsys.readouterr().out


def test_old_candidate_files_without_the_new_columns_cannot_be_approved(tmp_path, validated):
    old = {k: v for k, v in _row().items() if k not in {"uncertainty_status", "time_system"}}
    counts, _, _, written = _review(tmp_path, [old], APPROVE)
    assert counts["approved"] == 0 and not written


@pytest.mark.parametrize("change", BLOCKING, ids=lambda c: "-".join(f"{k}={v}" for k, v in c.items()))
def test_one_blocker_is_enough(tmp_path, validated, change):
    counts, _, _, written = _review(tmp_path, [_row(**change)], APPROVE)
    assert counts["approved"] == 0 and not written


def test_approval_still_works_for_a_complete_row(tmp_path, validated):
    counts, targets, review, _ = _review(tmp_path, [_row()], APPROVE)
    assert counts["approved"] == 1
    assert ",transmission,True," in targets
    assert "APPROVED: transmission | syn-o1 |" in review.read_text(encoding="utf-8")


def test_ambiguous_rows_of_an_approved_group_are_not_recorded_as_approved(tmp_path, validated):
    rows = [_row(), _row(obs_id="syn-amb", match_status="ambiguous")]
    counts, _, review, _ = _review(tmp_path, rows, APPROVE)
    assert counts["approved"] == 1
    assert "syn-o1" in review.read_text(encoding="utf-8")
    assert "syn-amb" not in review.read_text(encoding="utf-8")


REJECTED = "\n".join(
    [
        review_labels.REVIEW_HEADER,
        review_labels.REVIEW_ALIGN,
        "| SYN-1 b | 90001 | u | %s | 2026-11-01 | REJECTED: emission | o | |",
        "",
    ]
)
HAND_WRITTEN = "| planet | program_id | source_url | checked_by | date | decision |\n|---|---|---|---|---|---|\n"


@pytest.mark.parametrize(
    "text",
    [
        REJECTED % "rev",
        REJECTED % r"A \| B",
        REJECTED % "A | B",
        HAND_WRITTEN + "| SYN-1 b | 90001 | u | rev | 2026-11-01 | REJECTED: emission |\n",
        HAND_WRITTEN + "| syn-1 B | 90001 | u | rev | 2026-11-01 | rejected: other |\n",
    ],
    ids=["own-table", "escaped-pipe", "raw-pipe", "hand-written", "letter-case"],
)
def test_a_rejection_blocks_every_later_approval(tmp_path, validated, text):
    """Also below the prompt: the writer itself refuses, so no order of events ends with verified=True."""
    _write_candidates(tmp_path / "c.csv", [_row()])
    targets, review = tmp_path / "t.csv", tmp_path / "R.md"
    targets.write_text(",".join(review_labels.TARGET_FIELDS) + "\n", encoding="utf-8")
    review.write_text(text, encoding="utf-8")
    (group,) = review_labels.build_groups(review_labels.load_candidates(tmp_path / "c.csv"))
    with pytest.raises(review_labels.ApprovalRefused, match="rejected before"):
        review_labels.record_decision(group, "SYN-1 b", "a", "rev", "2026-11-02", "1", "", targets, review)
    assert "True" not in targets.read_text(encoding="utf-8")
    assert review.read_text(encoding="utf-8") == text


def test_a_later_rejection_withdraws_the_label(tmp_path, validated):
    _write_candidates(tmp_path / "c.csv", [_row()])
    targets, review = tmp_path / "t.csv", tmp_path / "R.md"
    (group,) = review_labels.build_groups(review_labels.load_candidates(tmp_path / "c.csv"))
    review_labels.record_decision(group, "SYN-1 b", "a", "rev", "2026-11-02", "1", "", targets, review)
    review_labels.record_decision(group, "SYN-1 b", "e", "rev", "2026-11-03", "", "", targets, review)
    (row,) = _targets(targets)
    assert (row["verified"], row["observation_type"]) == ("False", "emission")
    assert not integrity.has_approval_row(review.read_text(encoding="utf-8"), "SYN-1 b", "90001")


def test_the_writer_refuses_what_the_prompt_would_refuse(tmp_path, validated):
    _write_candidates(tmp_path / "c.csv", [_row(match_status="ambiguous")])
    targets, review = tmp_path / "t.csv", tmp_path / "R.md"
    (group,) = review_labels.build_groups(review_labels.load_candidates(tmp_path / "c.csv"))
    with pytest.raises(review_labels.ApprovalRefused):
        review_labels.record_decision(group, "SYN-1 b", "a", "rev", "2026-11-02", "1", "", targets, review)
    (good,) = review_labels.build_groups([_row()])
    with pytest.raises(review_labels.ApprovalRefused, match="not the one assigned"):
        review_labels.record_decision(good, "SYN-1 c", "a", "rev", "2026-11-02", "1", "", targets, review)
    assert not targets.exists() and not review.exists()


def test_escaped_pipes_stay_in_their_cell():
    assert integrity.table_cells(r"| a | x \| y | b |") == ["a", "x | y", "b"]
