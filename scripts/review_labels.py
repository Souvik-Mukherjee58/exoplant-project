#!/usr/bin/env python3
"""Interactive human review of JWST label candidates. The script never decides by itself.

Reads reports/jwst_mast_candidates.csv (from scripts/build_jwst_labels_from_mast.py), groups rows by
(planet, proposal), shows `transit_in_window` groups first and `ambiguous` ones after, and asks the
reviewer for a decision:

    [a]pprove transmission / [e]mission / [p]hase curve / [r]eject / [s]kip / [q]uit

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
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_data_integrity import has_approval_row, table_cells  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
STSCI_PROGRAM_URL = "https://www.stsci.edu/jwst/science-execution/program-information?id={pid}"
MAST_PORTAL_URL = "https://mast.stsci.edu/portal/Mashup/Clients/Mast/Portal.html"
MIN_APPROVED_PLANETS = 15

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


def decision_rows(review_text: str) -> List[Dict[str, str]]:
    """Rows of the table written by this script (identified by its exact header)."""
    out: List[Dict[str, str]] = []
    header: Optional[List[str]] = None
    for line in review_text.splitlines():
        cells = table_cells(line)
        if not cells:
            header = None
            continue
        if line.strip() == REVIEW_HEADER:
            header = cells
            continue
        if header and not set(line.strip()) <= set("|:- "):
            out.append(dict(zip(header, cells)))
    return out


def is_decided(group: Group, decided: Sequence[Dict[str, str]]) -> bool:
    for d in decided:
        if d.get("program_id") != group.proposal_id:
            continue
        if group.planet and d.get("planet") == group.planet:
            return True
        if not group.planet and (d.get("planet") == group.host or d.get("planet", "").startswith(group.host + " ")):
            return True
    return False


# ---------------------------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------------------------


def md_escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


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
    url = STSCI_PROGRAM_URL.format(pid=group.proposal_id)
    # Review log first, then the label CSV. If the process dies in between, the worst case is a logged
    # decision with no label row (safe), never a verified=True row without its approval.
    append_review_row(
        review_path,
        [planet, group.proposal_id, url, reviewer, date_iso, decision, "; ".join(group.obs_ids), note],
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


def ask_planet(group: Group, input_fn: Optional[InputFn]) -> str:
    while True:
        planet = ask(f"   Planet name exactly as in the catalog (e.g. '{group.host} b'): ", input_fn=input_fn)
        if planet.startswith(group.host + " ") and len(planet) > len(group.host) + 1:
            return planet
        print(f"   The planet name must start with '{group.host} '.")


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
        if group.planet:
            planet = group.planet
        elif choice == "a":
            planet = ask_planet(group, input_fn)
        else:
            planet = group.host
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
    approved = sum(1 for d in decided if d.get("decision", "").startswith("APPROVED"))
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
    args = p.parse_args(argv)
    candidates = REPO_ROOT / args.candidates
    targets = REPO_ROOT / args.targets
    review = REPO_ROOT / args.review
    if args.summary:
        s = summarize(candidates, targets, review)
        print_summary(s)
        return 1 if s["problems"] else 0
    run_review(candidates, targets, review)
    print_summary(summarize(candidates, targets, review))
    return 0


if __name__ == "__main__":
    sys.exit(main())
