#!/usr/bin/env python3
"""Interactive human review of JWST label candidates. The script never decides by itself.

Reads reports/jwst_mast_candidates.csv (from scripts/build_jwst_labels_from_mast.py), groups rows by
(planet, proposal), shows `transit_in_window` groups first and `ambiguous` ones after, and asks the
reviewer for a decision:

    [a]pprove transmission / [e]mission / [p]hase curve / [r]eject / [s]kip / [q]uit

An approval is only possible when `approval_blockers` finds nothing against at least one row of the group: ambiguous rows,
missing uncertainties, time systems the builder has not validated, missing provenance and earlier rejections all block it.
A row must also equal the row that the builder computes again from the cached archive responses, so editing the candidate
file cannot create an approvable row.
Checkpoint H2 therefore stays blocked while VALIDATED_TIME_SYSTEMS is empty.

Every decision is appended to reports/LABEL_REVIEW.md (reviewer, ISO date, decision, obs_ids) FIRST and
then upserted into backend/data/reference/jwst_transmission_targets.csv. Only an approval sets
verified=True and observation_type=transmission. Skips are not recorded, so a skipped group comes back
next session. Decided groups are not shown again (the review is resumable).

    python scripts/review_labels.py            # review
    python scripts/review_labels.py --summary  # counts, and whether >= 15 planets are approved
"""

from __future__ import annotations

import argparse
import builtins
import csv
import datetime as dt
import io
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_jwst_labels_from_mast as builder  # noqa: E402
from check_data_integrity import (  # noqa: E402
    has_approval_row,
    has_rejection_row,
    review_lines,
    same_planet,
    same_program,
    table_cells,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
STSCI_PROGRAM_URL = "https://www.stsci.edu/jwst/science-execution/program-information?id={pid}"
MAST_PORTAL_URL = "https://mast.stsci.edu/portal/Mashup/Clients/Mast/Portal.html"
MIN_APPROVED_PLANETS = 15
CACHE_DIR = REPO_ROOT / "reports" / ".mast_cache"

REVIEW_SECTION = "## 3. Decisions recorded by scripts/review_labels.py"
REVIEW_HEADER = "| planet | program_id | source_url | checked_by | date | decision | obs_ids | note |"
REVIEW_ALIGN = "|:---|:---:|:---|:---:|:---:|:---|:---|:---|"

TARGET_FIELDS = [
    "planet_name",
    "program_id",
    "cycle",
    "mode",
    "source_url",
    "observation_type",
    "verified",
    "needs_review",
    "notes",
]

# key -> (decision text, observation_type, verified)
DECISIONS: Dict[str, Tuple[str, str, bool]] = {
    "a": ("APPROVED: transmission", "transmission", True),
    "e": ("REJECTED: emission", "emission", False),
    "p": ("REJECTED: phase_curve", "phase_curve", False),
    "r": ("REJECTED: other", "rejected", False),
}
REVIEWABLE = ("transit_in_window", "ambiguous")

InputFn = Callable[[str], str]


@dataclass
class Group:
    planet: str  # "" for host-level groups (planet not attributable)
    host: str
    proposal_id: str
    status: str
    rows: List[Dict[str, str]] = field(default_factory=list)

    @property
    def obs_ids(self) -> List[str]:
        return sorted({r["obs_id"] for r in self.rows})

    @property
    def mode(self) -> str:
        return "; ".join(sorted({f"{r['instrument_name']} {r['filters']}".strip() for r in self.rows}))


# ---------------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------------


def load_candidates(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run scripts/build_jwst_labels_from_mast.py first (checkpoint H1).")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_groups(rows: Sequence[Dict[str, str]]) -> List[Group]:
    groups: Dict[Tuple[str, str, str], Group] = {}
    for r in rows:
        if r.get("match_status") not in REVIEWABLE:
            continue
        key = (r.get("assigned_planet", ""), r["hostname"], r["proposal_id"])
        g = groups.setdefault(key, Group(key[0], key[1], key[2], r["match_status"]))
        g.rows.append(r)
        if r["match_status"] == "transit_in_window":
            g.status = "transit_in_window"
    return sorted(
        groups.values(),
        key=lambda g: (REVIEWABLE.index(g.status), g.planet == "", g.planet or g.host, g.proposal_id),
    )


PROVENANCE_FIELDS = ("mast_row_sha256", "mast_cache_sha256", "ephemeris_cache_sha256")


class ApprovalRefused(ValueError):
    """The group must not become a verified label."""


def approval_blockers(row: Dict[str, str]) -> List[str]:
    """Every reason why this candidate row cannot support a transmission label. Missing values are reasons too.

    The time system is checked against the builder's own list, so an old, edited or foreign candidate file that merely
    says 'transit_in_window' is not enough.
    """
    reasons: List[str] = []
    if row.get("match_status") != "transit_in_window":
        reasons.append(f"match_status is '{row.get('match_status', '')}', not 'transit_in_window'")
    if row.get("uncertainty_status") != "known":
        reasons.append(f"uncertainty_status is '{row.get('uncertainty_status', '')}', not 'known'")
    if row.get("time_system") not in builder.VALIDATED_TIME_SYSTEMS:
        reasons.append(f"time system '{row.get('time_system', '')}' is not validated")
    if not row.get("assigned_planet"):
        reasons.append("no planet is assigned")
    if not row.get("obs_id"):
        reasons.append("no obs_id")
    reasons += [f"{name} is missing" for name in PROVENANCE_FIELDS if not row.get(name)]
    return reasons


RowKey = Tuple[str, str, str]


def row_key(row: Dict[str, str]) -> RowKey:
    return row.get("obs_id", ""), row.get("assigned_planet", ""), row.get("proposal_id", "")


def rebuild_from_cache(cache_dir: Path) -> Dict[RowKey, Dict[str, str]]:
    """Candidate rows computed again from the cached raw archive responses (no network), as the CSV would contain them."""
    obs, mast_meta = builder.fetch_jwst_timeseries(cache_dir, force_refresh=False, offline=True)
    ephem, ephem_meta = builder.fetch_ephemerides(cache_dir, force_refresh=False, offline=True)
    rows, _ = builder.build_candidates(
        obs,
        ephem,
        provenance={"mast": mast_meta["sha256"], "ephemeris": ephem_meta["sha256"]},
        validated_systems=builder.VALIDATED_TIME_SYSTEMS,
    )
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=builder.CANDIDATE_FIELDS)
    writer.writeheader()
    writer.writerows({k: r.get(k, "") for k in builder.CANDIDATE_FIELDS} for r in rows)
    return {row_key(r): r for r in csv.DictReader(io.StringIO(text.getvalue(), newline=""))}


def evidence_problems(rows: Sequence[Dict[str, str]]) -> List[List[str]]:
    """For each row, why it is not the row that the cached archive data give. Read again for every decision."""
    try:
        rebuilt = rebuild_from_cache(CACHE_DIR)
    except Exception as err:  # no cache, modified cache, unreadable data: nothing can be confirmed
        return [[f"the cached archive data cannot confirm this row ({type(err).__name__})"] for _ in rows]
    out: List[List[str]] = []
    for r in rows:
        want = rebuilt.get(row_key(r))
        if want is None:
            out.append(["the cached archive data do not give this row"])
            continue
        # in_eligible_catalog depends on our own catalog and is not evidence
        wrong = [k for k in builder.CANDIDATE_FIELDS if k != "in_eligible_catalog" and (r.get(k) or "") != want[k]]
        out.append([f"differs from the cached archive data: {', '.join(wrong)}"] if wrong else [])
    return out


EVIDENCE = re.compile(r"\[evidence ([0-9a-f]{16})\]")


def evidence_mark(rows: Sequence[Dict[str, str]]) -> str:
    """Fingerprint of the archive data behind an approval: the observations and the ephemerides used."""
    parts = sorted({f"{r['obs_id']} {r['mast_row_sha256']} {r['ephemeris_cache_sha256']}" for r in rows})
    return f"[evidence {builder.sha256_bytes(chr(10).join(parts).encode('utf-8'))[:16]}]"


def obsolete_approval(decision: Dict[str, str], rebuilt: Optional[Dict[RowKey, Dict[str, str]]]) -> Optional[str]:
    """Why a recorded approval no longer rests on the current archive data; None if it does."""
    mark = EVIDENCE.search(decision.get("note", ""))
    if not mark:
        return "no evidence mark (not recorded by this tool, or edited)"
    if rebuilt is None:
        return "the cached archive data are not available, so it cannot be confirmed"
    wanted = {o.strip() for o in decision.get("obs_ids", "").split(";")}
    rows = [
        r
        for r in rebuilt.values()
        if r["obs_id"] in wanted
        and same_planet(r["assigned_planet"]) == same_planet(decision.get("planet", ""))
        and same_program(r["proposal_id"]) == same_program(decision.get("program_id", ""))
        and not approval_blockers(r)
    ]
    if {r["obs_id"] for r in rows} != wanted or evidence_mark(rows) != mark.group(0):
        return "the archive data have changed since the approval"
    return None


def row_blockers(rows: Sequence[Dict[str, str]]) -> List[List[str]]:
    """Reasons against each row. The archive data are only read when a row has no other blocker."""
    reasons = [approval_blockers(r) for r in rows]
    if any(not x for x in reasons):
        reasons = [a + b for a, b in zip(reasons, evidence_problems(rows), strict=True)]
    return reasons


def approvable_rows(group: Group) -> List[Dict[str, str]]:
    return [r for r, reasons in zip(group.rows, row_blockers(group.rows), strict=True) if not reasons]


def why_not_approvable(group: Group, planet: str, review_text: str) -> List[str]:
    """Reasons that block an approval of this group; empty means that a person may approve it."""
    reasons: List[str] = []
    if has_rejection_row(review_text, planet, group.proposal_id):
        reasons.append("this planet and program were rejected before; REJECTED overrides APPROVED")
    if planet != group.planet or not planet:
        reasons.append("the planet is not the one assigned by the builder")
    if not (group.proposal_id.isascii() and group.proposal_id.isdigit() and not group.proposal_id.startswith("0")):
        reasons.append(f"program '{group.proposal_id}' is not a plain program number")
    if not approvable_rows(group):
        reasons += sorted({reason for blockers in row_blockers(group.rows) for reason in blockers})
    return reasons


def decision_rows(review_text: str) -> List[Dict[str, str]]:
    """Rows of the table written by this script (identified by its exact header)."""
    out: List[Dict[str, str]] = []
    header: Optional[List[str]] = None
    for line in review_lines(review_text):
        cells = table_cells(line)
        if not cells:
            header = None
            continue
        if line.strip() == REVIEW_HEADER:
            header = cells
            continue
        if header and not set(line.strip()) <= set("|:- "):
            out.append(dict(zip(header, cells, strict=False)))
    return out


def is_decided(group: Group, decided: Sequence[Dict[str, str]]) -> bool:
    for d in decided:
        if same_program(d.get("program_id", "")) != same_program(group.proposal_id):
            continue
        if group.planet and same_planet(d.get("planet", "")) == same_planet(group.planet):
            return True
        if not group.planet and (d.get("planet") == group.host or d.get("planet", "").startswith(group.host + " ")):
            return True
    return False


# ---------------------------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------------------------


def md_escape(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")  # every kind of line break becomes a space


def append_review_row(review_path: Path, cells: Sequence[str]) -> None:
    text = review_path.read_text(encoding="utf-8") if review_path.exists() else "# JWST label review log\n"
    if REVIEW_HEADER not in text:
        if not text.endswith("\n"):
            text += "\n"
        text += f"\n{REVIEW_SECTION}\n\n{REVIEW_HEADER}\n{REVIEW_ALIGN}\n"
    elif not text.endswith("\n"):
        text += "\n"
    text += "| " + " | ".join(md_escape(c) for c in cells) + " |\n"
    atomic_write(review_path, text)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def upsert_target(targets_path: Path, values: Dict[str, str]) -> None:
    """Update the (planet, program_id) row; an approval may fill an existing unverified row with no ID."""
    rows: List[Dict[str, str]] = []
    fields = list(TARGET_FIELDS)
    if targets_path.exists():
        with open(targets_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fields += [c for c in (reader.fieldnames or []) if c not in fields]
            rows = list(reader)

    planet, pid = values["planet_name"], values["program_id"]
    target = next((r for r in rows if r.get("planet_name") == planet and r.get("program_id", "").strip() == pid), None)
    if target is None and values["verified"] == "True":
        target = next(
            (
                r
                for r in rows
                if r.get("planet_name") == planet
                and not r.get("program_id", "").strip()
                and str(r.get("verified", "")).strip().lower() != "true"
            ),
            None,
        )
    if target is None:
        target = {k: "" for k in fields}
        rows.append(target)
    for k, v in values.items():
        if v != "" or k not in ("cycle", "notes"):
            target[k] = v

    lines: List[str] = []

    class _Sink:
        def write(self, s: str) -> int:
            lines.append(s)
            return len(s)

    writer = csv.DictWriter(_Sink(), fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in fields})
    atomic_write(targets_path, "".join(lines))


def record_decision(
    group: Group,
    planet: str,
    choice: str,
    reviewer: str,
    date_iso: str,
    cycle: str,
    note: str,
    targets_path: Path,
    review_path: Path,
) -> None:
    decision, obs_type, verified = DECISIONS[choice]
    obs_ids = group.obs_ids
    if verified:  # checked here too, so that no other caller can write a verified label
        review_text = review_path.read_text(encoding="utf-8") if review_path.exists() else ""
        blockers = why_not_approvable(group, planet, review_text)
        if blockers:
            raise ApprovalRefused("; ".join(blockers))
        approved = approvable_rows(group)  # never the ambiguous ones
        obs_ids = sorted({r["obs_id"] for r in approved})
        note = f"{EVIDENCE.sub('', note)} {evidence_mark(approved)}".strip()
    url = STSCI_PROGRAM_URL.format(pid=group.proposal_id)
    # Review log first, then the label CSV. If the process dies in between, the worst case is a logged
    # decision with no label row (safe), never a verified=True row without its approval.
    append_review_row(
        review_path,
        [planet, group.proposal_id, url, reviewer, date_iso, decision, "; ".join(obs_ids), note],
    )
    upsert_target(
        targets_path,
        {
            "planet_name": planet,
            "program_id": group.proposal_id,
            "cycle": cycle,
            "mode": group.mode,
            "source_url": url,
            "observation_type": obs_type,
            "verified": "True" if verified else "False",
            "needs_review": "False",
            "notes": note,
        },
    )


# ---------------------------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------------------------


def mjd_to_iso(value: str) -> str:
    try:
        mjd = float(value)
    except (TypeError, ValueError):
        return "?"
    return (dt.datetime(1858, 11, 17) + dt.timedelta(days=mjd)).strftime("%Y-%m-%d %H:%M UTC")


def timing_lines(r: Dict[str, str]) -> List[str]:
    """Uncertainty flags and eclipse inputs of one candidate row (display only, no prediction)."""
    out: List[str] = []
    if r.get("uncertainty_status", "").startswith("missing"):
        out.append(f"     UNVERIFIED TIMING: {r['uncertainty_status']} - the archive gives no usable uncertainty")
    if r.get("time_system"):
        out.append(f"     predicted times: archive time system {r['time_system']}, not converted and not validated")
    out.append(f"     eclipse: {r.get('eclipse_status') or 'unknown'}, no predicted time")
    if r.get("eclipse_reasons"):
        out.append(f"       reasons: {r['eclipse_reasons'].replace(';', ', ')}")
    if r.get("ecc"):
        out.append(
            f"       e = {r['ecc']} (+{r.get('ecc_err1') or '?'} {r.get('ecc_err2') or '?'}, limit flag "
            f"{r.get('ecc_limit_flag') or '?'}), source {r.get('ecc_reference') or '?'}"
        )
    if r.get("omega_deg"):
        try:
            other = f"{(float(r['omega_deg']) + 180.0) % 360.0:g}"
        except ValueError:
            other = "?"
        out.append(
            f"       omega = {r['omega_deg']} deg, convention unconfirmed: if it is the star's orbit, the star's omega is "
            f"{r['omega_deg']}; if it is the planet's orbit, the star's omega is {other}"
        )
    return out


def format_eclipses(rows: Sequence[Dict[str, str]]) -> str:
    """Every row whose eclipse is not excluded, for information. No decision is asked for or recorded here."""
    listed = [r for r in rows if r.get("eclipse_status") != "excluded"]
    lines = [f"{len(listed)} row(s) whose eclipse is not excluded (information only; no decision is recorded):"]
    for r in listed:
        lines.append(
            f"   - {r.get('assigned_planet') or '(host-level)'}  proposal {r.get('proposal_id', '?')}  "
            f"{r.get('obs_id', '?')}  start {mjd_to_iso(r.get('t_min', ''))}  note {r.get('match_note') or '-'}"
        )
        lines += timing_lines(r)
    return "\n".join(lines)


def format_group(group: Group, index: int, total: int) -> str:
    title = group.rows[0].get("obs_title", "")
    planet = group.planet or f"(host-level: {group.host}; planet not attributable)"
    lines = [
        "",
        "=" * 78,
        f" [{index}/{total}] {planet}   host {group.host}   proposal {group.proposal_id}   status {group.status}",
        "=" * 78,
        f" Title (raw, from MAST): {title}",
        f" STScI program page   : {STSCI_PROGRAM_URL.format(pid=group.proposal_id)}",
        f" MAST portal          : {MAST_PORTAL_URL}  (search an obs_id below)",
    ]
    eligible = {r.get("in_eligible_catalog", "") for r in group.rows}
    if "False" in eligible:
        lines.append(
            " NOTE: this planet is not transmission-eligible in our catalog; approving it does not add a label."
        )
    lines.append(" Observations:")
    for r in sorted(group.rows, key=lambda r: r["t_min"]):
        lines.append(
            f"   - {r['obs_id']}  {r['instrument_name']} {r['filters']}  start {mjd_to_iso(r['t_min'])}  "
            f"window {r['window_hours']} h"
        )
        lines.append(
            f"     match {r['match_status']}  predicted mid-transit MJD {r.get('predicted_mid_transit') or '-'}  "
            f"timing sigma {r.get('timing_uncertainty_hours') or '-'} h  note {r.get('match_note') or '-'}  "
            f"hint {r.get('likely_type', '')}"
        )
        lines += timing_lines(r)
    lines += [
        " Check on the STScI page before approving:",
        "   1. The host star is listed as a target of this program.",
        "   2. The program is transit / transmission spectroscopy (not only eclipse, emission or phase curve).",
        "   3. match_status shows a transit of THIS planet in the window (TRAPPIST-1: b is not e).",
        "   If you are not sure, press [s] to skip.",
    ]
    return "\n".join(lines)


def ask(prompt: str, valid: Optional[Set[str]] = None, input_fn: Optional[InputFn] = None) -> str:
    fn = input_fn or builtins.input
    while True:
        answer = fn(prompt).strip()
        if valid is None or answer.lower() in valid:
            return answer.lower() if valid is not None else answer
        print(f"   Please enter one of: {', '.join(sorted(valid))}")


def run_review(
    candidates_path: Path,
    targets_path: Path,
    review_path: Path,
    input_fn: Optional[InputFn] = None,
    today: Optional[dt.date] = None,
) -> Dict[str, int]:
    groups = build_groups(load_candidates(candidates_path))
    review_text = review_path.read_text(encoding="utf-8") if review_path.exists() else ""
    decided = decision_rows(review_text)
    pending = [g for g in groups if not is_decided(g, decided)]
    print(f"{len(groups)} candidate groups, {len(groups) - len(pending)} already decided, {len(pending)} pending.")
    counts = {"approved": 0, "rejected": 0, "skipped": 0}
    if not pending:
        return counts

    reviewer = ""
    while not reviewer:
        reviewer = ask("Your name (recorded as checked_by): ", input_fn=input_fn)
    date_iso = (today or dt.date.today()).isoformat()

    for i, group in enumerate(pending, start=1):
        print(format_group(group, i, len(pending)))
        choice = ask(
            " [a]pprove transmission / [e]mission / [p]hase curve / [r]eject / [s]kip / [q]uit: ",
            {"a", "e", "p", "r", "s", "q"},
            input_fn,
        )
        if choice == "q":
            break
        if choice == "s":
            counts["skipped"] += 1
            continue
        planet = group.planet or group.host
        if choice == "a":
            current = review_path.read_text(encoding="utf-8") if review_path.exists() else ""
            blockers = why_not_approvable(group, planet, current)
            if blockers:
                print("   Not recorded: this group cannot be approved (see docs/SCIENTIFIC_LIMITATIONS.md):")
                for reason in blockers:
                    print(f"     - {reason}")
                counts["skipped"] += 1
                continue
        cycle = ""
        if choice == "a":
            cycle = ask("   JWST cycle as shown on the STScI program page (blank = unknown): ", input_fn=input_fn)
            while cycle and not cycle.isdigit():
                cycle = ask("   Cycle must be a number or blank: ", input_fn=input_fn)
            confirm = ask(
                f"   Confirm APPROVE '{planet}' in program {group.proposal_id} as TRANSMISSION? [y/N]: ",
                input_fn=input_fn,
            )
            if confirm.lower() != "y":
                print("   Not recorded.")
                counts["skipped"] += 1
                continue
        note = ask("   Optional note (Enter to skip): ", input_fn=input_fn)
        record_decision(group, planet, choice, reviewer, date_iso, cycle, note, targets_path, review_path)
        counts["approved" if choice == "a" else "rejected"] += 1
        print(f"   Recorded: {DECISIONS[choice][0]} for {planet} / {group.proposal_id}")
    print(f"Session: {counts['approved']} approved, {counts['rejected']} rejected, {counts['skipped']} skipped.")
    return counts


# ---------------------------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------------------------


def summarize(candidates_path: Path, targets_path: Path, review_path: Path) -> Dict[str, object]:
    review_text = review_path.read_text(encoding="utf-8") if review_path.exists() else ""
    decided = decision_rows(review_text)
    groups = build_groups(load_candidates(candidates_path)) if candidates_path.exists() else []
    pending = [g for g in groups if not is_decided(g, decided)]

    verified_planets: Set[str] = set()
    problems: List[str] = []
    if targets_path.exists():
        with open(targets_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if str(r.get("verified", "")).strip().lower() != "true":
                    continue
                if r.get("observation_type", "").strip().lower() != "transmission":
                    problems.append(f"{r['planet_name']}: verified but observation_type={r.get('observation_type')}")
                    continue
                if not has_approval_row(review_text, r["planet_name"], r.get("program_id", "")):
                    problems.append(f"{r['planet_name']} / {r.get('program_id')}: verified without an APPROVED row")
                    continue
                verified_planets.add(r["planet_name"])
    for d in decided:
        if d.get("decision", "").startswith("APPROVED") and has_rejection_row(
            review_text, d.get("planet", ""), d.get("program_id", "")
        ):
            problems.append(f"{d.get('planet')} / {d.get('program_id')}: approved and rejected; REJECTED overrides")
    approvals = [d for d in decided if d.get("decision", "").startswith("APPROVED")]
    if approvals:
        try:
            rebuilt: Optional[Dict[RowKey, Dict[str, str]]] = rebuild_from_cache(CACHE_DIR)
        except Exception:  # reported for every approval below
            rebuilt = None
        for d in approvals:
            reason = obsolete_approval(d, rebuilt)
            if reason:
                problems.append(f"{d.get('planet')} / {d.get('program_id')}: approval not confirmed: {reason}")
    approved = len(approvals)
    rejected = sum(1 for d in decided if d.get("decision", "").startswith("REJECTED"))
    return {
        "candidate_groups": len(groups),
        "pending_groups": len(pending),
        "approved_decisions": approved,
        "rejected_decisions": rejected,
        "verified_transmission_planets": len(verified_planets),
        "enough_for_training": len(verified_planets) >= MIN_APPROVED_PLANETS,
        "missing_for_training": max(0, MIN_APPROVED_PLANETS - len(verified_planets)),
        "problems": problems,
    }


def print_summary(s: Dict[str, object]) -> None:
    print("=" * 60)
    print(" Label review summary")
    print("=" * 60)
    print(f" Candidate groups (planet x proposal) : {s['candidate_groups']}")
    print(f" Pending groups                       : {s['pending_groups']}")
    print(f" Approved decisions                   : {s['approved_decisions']}")
    print(f" Rejected decisions                   : {s['rejected_decisions']}")
    print(f" Verified transmission planets        : {s['verified_transmission_planets']}")
    if s["enough_for_training"]:
        print(f" >= {MIN_APPROVED_PLANETS} approved planets: YES (training can run)")
    else:
        print(f" >= {MIN_APPROVED_PLANETS} approved planets: NO ({s['missing_for_training']} more needed)")
    for p in s["problems"]:  # type: ignore[attr-defined]
        print(f" [PROBLEM] {p}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Human review of JWST label candidates")
    p.add_argument("--candidates", default="reports/jwst_mast_candidates.csv")
    p.add_argument("--targets", default="backend/data/reference/jwst_transmission_targets.csv")
    p.add_argument("--review", default="reports/LABEL_REVIEW.md")
    p.add_argument("--summary", action="store_true", help="print counts and exit")
    p.add_argument(
        "--eclipses", action="store_true", help="list every row whose eclipse is not excluded (display only) and exit"
    )
    args = p.parse_args(argv)
    candidates = REPO_ROOT / args.candidates
    targets = REPO_ROOT / args.targets
    review = REPO_ROOT / args.review
    if args.eclipses:
        print(format_eclipses(load_candidates(candidates)))
        return 0
    if args.summary:
        s = summarize(candidates, targets, review)
        print_summary(s)
        return 1 if s["problems"] else 0
    run_review(candidates, targets, review)
    print_summary(summarize(candidates, targets, review))
    return 0


if __name__ == "__main__":
    sys.exit(main())
