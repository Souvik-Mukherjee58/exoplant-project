"""What can become a verified label, and who may use one.

SYNTHETIC TEST DATA: fictional hosts SYN-1/SYN-2 from the fixtures. The raw cache is written to a temporary directory. The
tests that need an approvable row pretend that a time system has been validated; the program itself validates none.
"""

import csv
import datetime as dt
import importlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from app.config import settings
from app.ml import ground_truth

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

review_labels = importlib.import_module("review_labels")
integrity = importlib.import_module("check_data_integrity")
builder = importlib.import_module("build_jwst_labels_from_mast")

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TODAY = dt.date(2026, 11, 25)
HEAD = review_labels.REVIEW_HEADER + "\n" + review_labels.REVIEW_ALIGN + "\n"
APPROVE = ["SYNTHETIC REVIEWER", "a", "1", "y", "", "q"]


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """The fixtures as cached raw archive responses, and a time system that is (only here) validated."""
    d = tmp_path / "cache"
    meta = {"row_count": 0, "fetched_at": "SYNTHETIC"}
    mast, ephem = FIXTURES / "fixture_mast_timeseries.ecsv", FIXTURES / "fixture_nasa_ephemerides.csv"
    builder.write_raw_cache(d, builder.MAST_CACHE_STEM, ".ecsv", mast.read_bytes(), meta)
    builder.write_raw_cache(d, builder.EPHEM_CACHE_STEM, ".csv", ephem.read_bytes(), meta)
    monkeypatch.setattr(review_labels, "CACHE_DIR", d)
    monkeypatch.setattr(builder, "VALIDATED_TIME_SYSTEMS", frozenset({"BJD-TDB"}))
    return d


def genuine(cache):
    """The one fixture row with a transit in its window, exactly as the builder writes it."""
    (row,) = [r for r in review_labels.rebuild_from_cache(cache).values() if r["match_status"] == "transit_in_window"]
    return dict(row)


def session(tmp_path, rows, answers=APPROVE, review_text="# SYNTHETIC TEST DATA\n"):
    cand, targets, review = tmp_path / "c.csv", tmp_path / "t.csv", tmp_path / "R.md"
    with open(cand, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=builder.CANDIDATE_FIELDS)
        w.writeheader()
        w.writerows(rows)
    review.write_text(review_text, encoding="utf-8")
    feed = iter(answers)
    counts = review_labels.run_review(cand, targets, review, input_fn=lambda _p: next(feed), today=TODAY)
    return counts, targets, review


def write_directly(
    tmp_path, row, planet=None, review_text="# SYNTHETIC TEST DATA\n", choice="a", reviewer="R", note=""
):
    """The writer alone, without the prompt."""
    targets, review = tmp_path / "wt.csv", tmp_path / "WR.md"
    review.write_text(review_text, encoding="utf-8")
    (group,) = review_labels.build_groups([row])
    args = (group, planet or group.planet, choice, reviewer, "2026-11-25", "1", note, targets, review)
    review_labels.record_decision(*args)
    return targets, review


# --- the candidate file ----------------------------------------------------------------------------------------------


def test_the_genuine_row_can_be_approved_once_a_time_system_is_validated(tmp_path, cache):
    counts, targets, _ = session(tmp_path, [genuine(cache)])
    assert counts["approved"] == 1 and ",transmission,True," in targets.read_text(encoding="utf-8")


def test_the_genuine_row_cannot_be_approved_today(tmp_path, cache, monkeypatch):
    row = genuine(cache)
    monkeypatch.setattr(builder, "VALIDATED_TIME_SYSTEMS", frozenset())
    counts, targets, _ = session(tmp_path, [row])
    assert counts["approved"] == 0 and not targets.exists()
    with pytest.raises(review_labels.ApprovalRefused, match="not validated"):
        write_directly(tmp_path, row)


EDITABLE = [f for f in builder.CANDIDATE_FIELDS if f != "in_eligible_catalog"]


@pytest.mark.parametrize("field", EDITABLE)
def test_no_edited_field_survives(tmp_path, cache, field):
    """Any change of any field: refused by the prompt and, independently, by the writer."""
    row = genuine(cache)
    row[field] = {"proposal_id": "90999", "assigned_planet": "SYN-1 c"}.get(field, (row[field] or "") + "1")
    counts, targets, review = session(tmp_path, [row])
    assert counts["approved"] == 0 and not targets.exists()
    assert "APPROVED" not in review.read_text(encoding="utf-8")
    if row["match_status"] in review_labels.REVIEWABLE:
        with pytest.raises(review_labels.ApprovalRefused):
            write_directly(tmp_path, row)
        assert not (tmp_path / "wt.csv").exists()


@pytest.mark.parametrize("value", ["", "not a hash", "a" * 64])
@pytest.mark.parametrize("field", review_labels.PROVENANCE_FIELDS)
def test_made_up_hashes_are_refused(tmp_path, cache, field, value):
    row = genuine(cache)
    row[field] = value
    with pytest.raises(review_labels.ApprovalRefused):
        write_directly(tmp_path, row)


def test_an_ambiguous_row_edited_into_a_transit_is_refused(tmp_path, cache):
    rows = review_labels.rebuild_from_cache(cache).values()
    row = dict(next(r for r in rows if r["match_status"] == "ambiguous"))
    row.update(match_status="transit_in_window", uncertainty_status="known", time_system="BJD-TDB", match_note="")
    counts, targets, _ = session(tmp_path, [row])
    assert counts["approved"] == 0 and not targets.exists()


def test_without_the_archive_data_nothing_can_be_approved(tmp_path, cache, monkeypatch):
    row = genuine(cache)
    monkeypatch.setattr(review_labels, "CACHE_DIR", tmp_path / "missing")
    with pytest.raises(review_labels.ApprovalRefused, match="cannot confirm"):
        write_directly(tmp_path, row)


def test_modified_archive_data_confirm_nothing(tmp_path, cache):
    row = genuine(cache)
    path = cache / f"{builder.EPHEM_CACHE_STEM}.csv"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(review_labels.ApprovalRefused, match="CacheIntegrityError"):
        write_directly(tmp_path, row)


def test_a_new_cache_does_not_confirm_rows_of_an_old_one(tmp_path, cache):
    """Same numbers, other file: the recorded hash no longer matches."""
    row = genuine(cache)
    raw = (cache / f"{builder.EPHEM_CACHE_STEM}.csv").read_bytes()
    builder.write_raw_cache(cache, builder.EPHEM_CACHE_STEM, ".csv", raw + b"\n", {"row_count": 0})
    assert json.loads((cache / f"{builder.EPHEM_CACHE_STEM}.meta.json").read_text())["sha256"]
    with pytest.raises(review_labels.ApprovalRefused, match="ephemeris_cache_sha256"):
        write_directly(tmp_path, row)


def test_forged_rows_of_a_genuine_group_are_not_recorded(tmp_path, cache):
    row = genuine(cache)
    counts, _, review = session(tmp_path, [row, dict(row, obs_id="syn-forged")])
    assert counts["approved"] == 1
    assert "syn-forged" not in review.read_text(encoding="utf-8")


def test_prompt_and_writer_each_check(tmp_path, cache, monkeypatch):
    """Switching one of them off must leave the other one in force."""
    row = dict(genuine(cache), t_min="1")
    calls = []
    original = review_labels.why_not_approvable

    def first_call_says_yes(*args):
        calls.append(args)
        return [] if len(calls) == 1 else original(*args)

    monkeypatch.setattr(review_labels, "why_not_approvable", first_call_says_yes)
    with pytest.raises(review_labels.ApprovalRefused):
        session(tmp_path, [row])
    assert len(calls) == 2 and not (tmp_path / "t.csv").exists()


# --- approvals and later archive data ----------------------------------------------------------------------------------


def problems(tmp_path):
    return review_labels.summarize(tmp_path / "none.csv", tmp_path / "t.csv", tmp_path / "R.md")["problems"]


def change_ephemerides(cache, old, new):
    raw = (cache / f"{builder.EPHEM_CACHE_STEM}.csv").read_bytes()
    assert old in raw
    builder.write_raw_cache(cache, builder.EPHEM_CACHE_STEM, ".csv", raw.replace(old, new, 1), {"row_count": 0})


def test_an_approval_is_confirmed_by_the_data_it_rests_on(tmp_path, cache):
    session(tmp_path, [genuine(cache)])
    assert problems(tmp_path) == []
    assert review_labels.EVIDENCE.search((tmp_path / "R.md").read_text(encoding="utf-8"))


def test_an_approval_does_not_outlive_its_archive_data(tmp_path, cache):
    session(tmp_path, [genuine(cache)])
    change_ephemerides(cache, b"\n", b"\n\n")  # same numbers, another file
    (problem,) = problems(tmp_path)
    assert "have changed since the approval" in problem


def test_an_approval_is_not_confirmed_without_archive_data_or_validated_time_system(tmp_path, cache, monkeypatch):
    session(tmp_path, [genuine(cache)])
    monkeypatch.setattr(builder, "VALIDATED_TIME_SYSTEMS", frozenset())
    assert "have changed" in problems(tmp_path)[0]
    monkeypatch.setattr(review_labels, "CACHE_DIR", tmp_path / "missing")
    assert "cannot be confirmed" in problems(tmp_path)[0]


@pytest.mark.parametrize("edit", ["remove", "other", "obs", "extra", "planet"])
def test_an_edited_approval_is_not_confirmed(tmp_path, cache, edit):
    session(tmp_path, [genuine(cache)])
    log = tmp_path / "R.md"
    text = log.read_text(encoding="utf-8")
    mark = review_labels.EVIDENCE.search(text).group(0)
    change = {
        "remove": (mark, ""),
        "other": (mark, "[evidence 0123456789abcdef]"),
        "obs": ("syn-o001", "syn-o002"),
        "extra": ("syn-o001-transit |", "syn-o001-transit; syn-forged |"),
        "planet": ("| SYN-1 b |", "| SYN-1 c |"),
    }
    log.write_text(text.replace(*change[edit]), encoding="utf-8")
    assert any("approval not confirmed" in p for p in problems(tmp_path))


def test_a_typed_note_cannot_bring_its_own_mark(tmp_path, cache):
    fake = "[evidence 0123456789abcdef]"
    session(tmp_path, [genuine(cache)], ["SYNTHETIC REVIEWER", "a", "1", "y", f"seen {fake}", "q"])
    text = (tmp_path / "R.md").read_text(encoding="utf-8")
    assert fake not in text and "seen" in text and problems(tmp_path) == []


# --- spelling and order ------------------------------------------------------------------------------------------------

REJECTION = HEAD + "| {planet} | {pid} | u | rev | 2026-11-01 | REJECTED: emission | o | |\n"


@pytest.mark.parametrize(
    "planet,pid",
    [
        ("SYN-1 b", "090001"),
        ("SYN-1  b", "90001"),
        ("SYN-1\u00a0b", "90001"),
        ("SYN-1b", "90001"),
        ("syn-1 B", "090001"),
    ],
)
def test_another_spelling_is_not_another_planet_or_program(tmp_path, cache, planet, pid):
    row = genuine(cache)
    assert (row["assigned_planet"], row["proposal_id"]) == ("SYN-1 b", "90001")
    text = REJECTION.format(planet=planet, pid=pid)
    assert integrity.has_rejection_row(text, "SYN-1 b", "90001")
    with pytest.raises(review_labels.ApprovalRefused, match="rejected before"):
        write_directly(tmp_path, row, review_text=text)


@pytest.mark.parametrize("pid", ["090001", "90001 ", "\uff19\uff10\uff10\uff10\uff11", "90001-x", ""])
def test_only_a_plain_program_number_can_be_approved(tmp_path, cache, pid):
    with pytest.raises(review_labels.ApprovalRefused, match="not a plain program number"):
        write_directly(tmp_path, dict(genuine(cache), proposal_id=pid))


def test_a_planet_with_another_letter_or_number_stays_another_planet():
    text = REJECTION.format(planet="SYN-1 b", pid="90001")
    for planet, pid in (("SYN-1 c", "90001"), ("SYN-11 b", "90001"), ("SYN-1 b", "900010"), ("SYN-1 b", "9001")):
        assert not integrity.has_rejection_row(text, planet, pid)


@pytest.mark.parametrize("reviewer", ["A", "A | B", r"A \| B", "A\u2028B", "A\x0bB", "A\x85B", "A\rB", "A\\"])
@pytest.mark.parametrize("first", ["a", "e"])
def test_rejected_wins_in_both_orders_whatever_the_reviewer_is_called(tmp_path, cache, first, reviewer):
    row = genuine(cache)
    targets, review = tmp_path / "t.csv", tmp_path / "R.md"
    (group,) = review_labels.build_groups([row])

    def decide(choice):
        review_labels.record_decision(group, "SYN-1 b", choice, reviewer, "2026-11-25", "1", "", targets, review)

    if first == "a":
        decide("a")
        decide("e")
    else:
        decide("e")
        with pytest.raises(review_labels.ApprovalRefused, match="rejected before"):
            decide("a")
    text = review.read_text(encoding="utf-8")
    assert integrity.has_rejection_row(text, "SYN-1 b", "90001")
    assert not integrity.has_approval_row(text, "SYN-1 b", "90001")
    with open(targets, newline="", encoding="utf-8") as f:
        assert [r["verified"] for r in csv.DictReader(f)] == ["False"]


@pytest.mark.parametrize("order", [0, 1])
def test_rejected_wins_in_both_row_orders_of_a_hand_written_log(order):
    rows = [
        f"| SYN-1 b | 90001 | u | rev | 2026-11-01 | {d} | o | |\n"
        for d in ("APPROVED: transmission", "REJECTED: other")
    ]
    text = HEAD + "".join(rows[::-1] if order else rows)
    assert not integrity.has_approval_row(text, "SYN-1 b", "90001")
    assert integrity.has_approval_row(HEAD + rows[0], "SYN-1 b", "90001")


@pytest.mark.parametrize(
    "row",
    [
        "SYN-1 b | 90001 | u | rev | 2026-11-01 | REJECTED: emission | o |",
        "| SYN-1 b | 90001 | u | rev | 2026-11-01 | REJECTED: emission | o",
        "| SYN-1 b | 90001 | u | rev | 2026-11-01 | **REJECTED: emission** | o | |",
        "| **SYN-1 b** | `90001` | u | rev | 2026-11-01 | Rejected | o | |",
        "| SYN\u20111 b | 90001 | u | rev | 2026-11-01 | REJECTED: other | o | |",
        "| SYN-1 b | 90001 | REJECTED: other |",
        "| SYN-1 b | \uff19\uff10\uff10\uff10\uff11 | u | rev | 2026-11-01 | REJECTED: other | o | |",
        "| SYN-1 b | 90001 | u | rev | 2026-11-01 | REJECTED: other | o | x " + chr(92) + "|",
        "| broken row without end\n| SYN-1 b | 90001 | u | rev | 2026-11-01 | REJECTED: other | o | |",
        "\n| decision | planet | program_id |\n|-|-|-|\n| REJECTED: other | SYN-1 b | 90001 |",
        "\n| planet | program_id | checked_by | date | decision | decision |\n|-|-|-|-|-|-|\n"
        "| SYN-1 b | 90001 | rev | 2026-11-01 | APPROVED: transmission | REJECTED: other |",
        "| SYN-1 b | 90001 | u | rev | 2026-11-01 | decision: rejected | o | |",
    ],
)
@pytest.mark.parametrize("order", [0, 1])
def test_a_carelessly_written_rejection_still_counts(row, order):
    ok = "| SYN-1 b | 90001 | u | rev | 2026-11-01 | APPROVED: transmission | o | |"
    text = f"{HEAD}{row}\n\n{HEAD}{ok}\n" if order else f"{HEAD}{ok}\n{row}\n"
    assert integrity.has_rejection_row(text, "SYN-1 b", "90001")
    assert not integrity.has_approval_row(text, "SYN-1 b", "90001")


@pytest.mark.parametrize("ch", ["\u2028", "\u2029", "\x0b", "\x0c", "\x1c", "\x85", "\r"])
def test_a_line_break_inside_a_cell_neither_hides_nor_creates_a_row(tmp_path, cache, ch):
    text = HEAD + f"| SYN-1 b | 90001 | u | re{ch}v | 2026-11-01 | REJECTED: emission | o | |\n"
    assert integrity.has_rejection_row(text, "SYN-1 b", "90001")
    forged = f"x{ch}| SYN-7 b | 777 | u | rev | 2026-11-01 | APPROVED: transmission | o | n |{ch}"
    _, review = write_directly(tmp_path, dict(genuine(cache), obs_id=forged), choice="r", reviewer=forged, note=forged)
    written = review.read_bytes().decode("utf-8")
    assert len(written.splitlines()) == len(written.split("\n")) - 1
    assert not integrity.has_approval_row(written, "SYN-7 b", "777")


@pytest.mark.parametrize(
    "row",
    [
        "| SYN-1 b | 90001 | u | rev | 2026-11-01 | pending | o | APPROVED: transmission |",
        "| SYN-1 b | 90001 | u | rev | 2026-11-01 | | o | APPROVED: transmission |",
        "| SYN-1 b | 90001 | u | rev | x | 2026-11-01 | APPROVED: transmission | o | n |",
        "| SYN-1 b | 90001 | u | rev | 2026-11-01 | APPROVED? not yet | o | |",
        "| SYN-1 b | 90001 | u | rev | 2026-11-01 | APPROVED: emission | o | |",
        "| SYN-1 b | 777 | u | rev | 2026-11-01 | APPROVED: transmission | 90001 | |",
        "| SYN-1 b | 90001 | u | rev | pending | APPROVED: transmission | 2026-11-01 | |",
        "| SYN-1 b | 90001 | u | | 2026-11-01 | APPROVED: transmission | o | |",
        "| SYN-1 b | 90001 | u | rev | 2026-13-01 | APPROVED: transmission | o | |",
        "| SYN-1 b | 90001 | u | rev | 2026-11-01 | APPROVED: transmission | o | | extra |",
        "| SYN-1 c | 90001 | u | rev | 2026-11-01 | APPROVED: transmission | SYN-1 b | |",
        "| SYN-1 b | 90001 | u | rev | 2026-11-01 | APPROVED: transmission | o | x " + chr(92) + "|",
        "\n| planet | program_id | checked_by | date | decision | decision |\n|-|-|-|-|-|-|\n"
        "| SYN-1 b | 90001 | rev | 2026-11-01 | pending | APPROVED: transmission |",
        "\n| planet | program_id | date | decision |\n|-|-|-|-|\n| SYN-1 b | 90001 | 2026-11-01 | APPROVED: transmission |",
        "| SYN-1 b | 90001 | u | rev | 2026-11-01 | APPROVED: transmission |",
        "SYN-1 b | 90001 | u | rev | 2026-11-01 | APPROVED: transmission | o |",
        "| SYN-1 b | 90001 | u | rev | 2026-11-01 | APPROVED: transmission | o | n",
        r"| SYN-1 b | 90001 | u | rev | 2026-11-01 | APPROVED: transmission \| o | n |",
    ],
)
def test_malformed_or_undecided_rows_approve_nothing(row):
    assert not integrity.has_approval_row(HEAD + row + "\n", "SYN-1 b", "90001")


@pytest.mark.parametrize(
    "line,cells",
    [
        ("| a | x \\| y | b |", ["a", "x | y", "b"]),
        ("a | b", ["a", "b"]),
        ("| a | b", ["a", "b"]),
        ("a | b |", ["a", "b"]),
        ("| a | b \\|", ["a", "b |"]),
        ("no pipe", []),
    ],
)
def test_cells_of_a_line(line, cells):
    assert integrity.loose_cells(line) == cells


def test_rows_without_a_header_approve_nothing():
    row = "| SYN-1 b | 90001 | u | rev | 2026-11-01 | APPROVED: transmission | o | |\n"
    for text in (row, row + row, HEAD + "text\n" + row, HEAD + "\n" + row):
        assert not integrity.has_approval_row(text, "SYN-1 b", "90001")
    assert integrity.has_approval_row(HEAD + row, "SYN-1 b", "90001")


@pytest.mark.parametrize("planet,pid", [("", "90001"), ("SYN-1 b", ""), ("", "")])
def test_nothing_is_approved_without_planet_and_program(planet, pid):
    assert not integrity.has_approval_row(
        HEAD + "| | | u | rev | 2026-11-01 | APPROVED: transmission | o | |\n", planet, pid
    )


def test_a_note_may_mention_an_earlier_rejection():
    row = "| SYN-1 b | 90001 | u | rev | 2026-11-01 | APPROVED: transmission | o | an earlier version was rejected |\n"
    assert integrity.has_approval_row(HEAD + row, "SYN-1 b", "90001")


# --- who uses a verified label ------------------------------------------------------------------------------------------

CSV_HEAD = "planet_name,program_id,source_url,observation_type,verified\n"
CSV_ROW = "SYN-1 b,90001,https://x,transmission,True\nSYN-2 b,,https://x,transmission,False\n"
OK_ROW = HEAD + "| SYN-1 b | 90001 | u | rev | 2026-11-01 | APPROVED: transmission | o | |\n"


@pytest.mark.parametrize(
    "log,expected",
    [
        (None, set()),
        ("# empty\n", set()),
        (OK_ROW, {"SYN-1 b"}),
        (OK_ROW + REJECTION.format(planet="SYN-1 b", pid="90001"), set()),
    ],
    ids=["no-log", "no-approval", "approved", "approved-and-rejected"],
)
def test_training_labels_need_the_review_log(tmp_path, monkeypatch, log, expected):
    """verified=True in the CSV alone is never a label, also when the path comes from the environment."""
    path, review = tmp_path / "live.csv", tmp_path / "REVIEW.md"
    path.write_text(CSV_HEAD + CSV_ROW, encoding="utf-8")
    if log is not None:
        review.write_text(log, encoding="utf-8")
    monkeypatch.setattr(settings, "JWST_TARGETS_PATH", path)
    monkeypatch.setattr(ground_truth, "REVIEW_LOG", review)
    assert ground_truth.get_verified_jwst_targets() == expected
    labelled = ground_truth.generate_ground_truth_labels(pd.DataFrame({"planet_name": ["SYN-1 b", "SYN-2 b"]}))
    assert labelled["ground_truth_binary"].sum() == len(expected)


def test_the_live_file_is_checked_also_when_named_explicitly(tmp_path, monkeypatch):
    path = tmp_path / "live.csv"
    path.write_text(CSV_HEAD + CSV_ROW, encoding="utf-8")
    monkeypatch.setattr(ground_truth, "LIVE_REFERENCE", path)
    monkeypatch.setattr(ground_truth, "REVIEW_LOG", tmp_path / "missing.md")
    assert ground_truth.get_verified_jwst_targets(path) == set()


def test_without_the_rules_nothing_is_approved(tmp_path, monkeypatch):
    path, review = tmp_path / "live.csv", tmp_path / "REVIEW.md"
    path.write_text(CSV_HEAD + CSV_ROW, encoding="utf-8")
    review.write_text(OK_ROW, encoding="utf-8")
    monkeypatch.setattr(settings, "JWST_TARGETS_PATH", path)
    monkeypatch.setattr(ground_truth, "REVIEW_LOG", review)
    monkeypatch.setattr(ground_truth, "REVIEW_RULES", tmp_path / "missing.py")
    assert ground_truth.get_verified_jwst_targets() == set()


def test_no_label_is_verified_in_the_repository():
    assert ground_truth.get_verified_jwst_targets(ground_truth.LIVE_REFERENCE) == set()
