#!/usr/bin/env python3
"""
scripts/check_data_integrity.py

Enforces scientific ground-truth data integrity rules:
1. Every verified=True target in jwst_transmission_targets.csv must have a matching
   APPROVED entry (with reviewer and ISO date) in reports/LABEL_REVIEW.md.
2. Every verified=True target must have observation_type == 'transmission' and non-empty program_id and source_url.
3. No files under reports/.mast_cache/ may be committed or staged in git.
4. Any cached MAST file (.ecsv) must match the SHA-256 recorded in its companion .meta.json,
   and must not contain all whole-number MJD dates (signature of fabricated timestamps).
5. If jwst_cycle4_targets.csv contains data rows, reports/CYCLE4_SOURCE.md must exist and be non-empty.

Exit code 0 on PASS, 1 on FAIL.
"""

import csv
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def check_staged_mast_cache(repo_root: Path) -> List[str]:
    failures: List[str] = []
    # Check staged additions or modifications (deletions are allowed during purge)
    res = subprocess.run(
        ["git", "diff", "--cached", "--diff-filter=ACMR", "--name-only"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    for line in res.stdout.splitlines():
        path_str = line.strip().replace("\\", "/")
        if path_str.startswith("reports/.mast_cache/"):
            failures.append(f"Staged file under reports/.mast_cache/: {path_str}")

    return failures


def check_transmission_targets(ref_csv_path: Path, review_md_path: Path) -> Tuple[List[str], int, int]:
    failures: List[str] = []
    verified_count = 0
    total_count = 0

    if not ref_csv_path.exists():
        return [f"Reference catalog not found: {ref_csv_path}"], 0, 0

    review_text = ""
    if review_md_path.exists():
        review_text = review_md_path.read_text(encoding="utf-8", errors="replace")

    verified_rows: List[Dict[str, str]] = []

    with open(ref_csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        if "verified" not in (reader.fieldnames or []):
            return [f"{ref_csv_path.name} has no 'verified' column"], 0, 0
        for row in reader:
            total_count += 1
            v_val = str(row.get("verified", "")).strip().lower()
            # anything that is not an explicit 'false' counts as verified, so odd spellings cannot slip through
            if v_val not in ("false", "0", "no", "f", "n", ""):
                verified_rows.append(row)
                verified_count += 1

    for row in verified_rows:
        planet = row.get("planet_name", "").strip()
        obs_type = row.get("observation_type", "").strip().lower()
        pid = row.get("program_id", "").strip()
        url = row.get("source_url", "").strip()

        # Rule 1: observation_type must be transmission
        if obs_type != "transmission":
            failures.append(f"Planet '{planet}' is verified=True but observation_type='{obs_type}' != 'transmission'")

        # Rule 2: non-empty program_id and source_url
        if not pid or pid.lower() in ("n/a", "none", "nan", "todo"):
            failures.append(f"Planet '{planet}' is verified=True but program_id is missing or invalid: '{pid}'")
        if not url or url.lower() in ("n/a", "none", "nan", "todo"):
            failures.append(f"Planet '{planet}' is verified=True but source_url is missing or invalid: '{url}'")

        # Rule 3: Must match APPROVED row with checked_by and ISO date in LABEL_REVIEW.md
        if not review_md_path.exists():
            failures.append(f"Planet '{planet}' is verified=True but reports/LABEL_REVIEW.md does not exist")
        elif not has_approval_row(review_text, planet, pid):
            failures.append(
                f"Planet '{planet}' (program {pid}) is verified=True in CSV but has no matching APPROVED review row "
                "in reports/LABEL_REVIEW.md (one table line with planet, program_id, APPROVED, reviewer and ISO date)"
            )

    return failures, verified_count, total_count


APPROVED_DECISION = "approved: transmission"


DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212"), "-")
MARKUP = dict.fromkeys(map(ord, "*`_"))


def plain(text: str) -> str:
    """Cell text without Markdown emphasis and with ordinary digits, letters and hyphens."""
    return unicodedata.normalize("NFKC", text).translate(DASHES).translate(MARKUP).strip()


def same_planet(text: str) -> str:
    """Planet name for comparisons: letter case, spaces, hyphen style and emphasis do not make another planet."""
    return "".join(plain(text).casefold().split())


def same_program(text: str) -> str:
    """Program number for comparisons: '01366' and ' 1366 ' are program 1366."""
    t = plain(text)
    return (t.lstrip("0") or "0") if t.isascii() and t.isdigit() else t.casefold()


def review_lines(review_text: str) -> List[str]:
    """Lines of the review log. Only a line feed ends a line: str.splitlines() also splits at form feeds, U+2028 and other
    characters that may be inside a cell, so that the row of a rejection could fall apart and be missed."""
    return review_text.replace("\r\n", "\n").split("\n")


def split_cells(inner: str) -> List[str]:
    cells = re.split(r"(?<!\\)\|", inner)  # an escaped pipe belongs to its cell
    return [c.replace("\\|", "|").strip() for c in cells]


def table_cells(line: str) -> List[str]:
    """Cells of a markdown table line ('| a | b |' -> ['a', 'b']); [] for non-table lines."""
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")) or s.endswith("\\|") or len(s) < 2:
        return []
    return split_cells(s[1:-1])


def loose_cells(line: str) -> List[str]:
    """Cells of any line with a pipe, also without the outer pipes. Only for finding rejections."""
    s = line.strip()
    if "|" not in s:
        return []
    s = s.removeprefix("|")
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return split_cells(s)


REVIEW_COLUMNS = {"planet", "program_id", "checked_by", "date", "decision"}


def review_header(cells: List[str]) -> List[str]:
    """Column names if this row is the header of a review table, else []. A repeated name makes columns ambiguous."""
    names = [c.casefold() for c in cells]
    return names if "planet" in names and "decision" in names and len(set(names)) == len(names) else []


def has_rejection_row(review_text: str, planet: str, program_id: str) -> bool:
    """True if any table row rejects this (planet, program_id). REJECTED overrides APPROVED.

    Deliberately lenient (outer pipes, emphasis, wording and column order may differ): a doubtful row counts as a rejection.
    In a regular row only the decision cell decides, so a note may mention an earlier rejection.
    """
    want_planet, want_pid = same_planet(planet), same_program(program_id)
    columns: List[str] = []
    for line in review_lines(review_text):
        cells = loose_cells(line)
        if not cells:
            columns = []
            continue
        header = review_header(cells)
        if header:
            columns = header
            continue
        if want_planet not in map(same_planet, cells) or want_pid not in map(same_program, cells):
            continue
        # a row with a different number of cells than its header cannot be trusted column by column
        regular = bool(columns) and len(cells) == len(columns)
        looked_at = [cells[columns.index("decision")]] if regular else cells
        if any("rejected" in x.casefold() for x in looked_at):
            return True
    return False


def has_approval_row(review_text: str, planet: str, program_id: str) -> bool:
    """True if ONE table line approves this (planet, program_id) and no line rejects it, whatever the order.

    Strict: the line needs both outer pipes, a header with planet, program_id, checked_by, date and decision, and as many cells
    as that header. The decision must be 'APPROVED: transmission', the date must exist and the reviewer must be named, each in
    its own column. Matching is per line on purpose: an approval of another planet elsewhere in the file must never count (an
    earlier DOTALL regex let any later APPROVED row validate every planet above it).
    """
    want = (same_planet(planet), same_program(program_id))
    if not all(want) or has_rejection_row(review_text, planet, program_id):
        return False
    columns: List[str] = []
    for line in review_lines(review_text):
        cells = table_cells(line)
        if not cells:
            columns = []
            continue
        header = review_header(cells)
        if header:
            columns = header
            continue
        if len(cells) != len(columns) or not set(columns) >= REVIEW_COLUMNS:
            continue
        row = dict(zip(columns, cells, strict=True))
        if (same_planet(row["planet"]), same_program(row["program_id"])) != want:
            continue
        if not row["checked_by"] or row["decision"].casefold() != APPROVED_DECISION:
            continue
        try:
            date.fromisoformat(row["date"])
        except ValueError:
            continue
        return True
    return False


def check_mast_cache_files(mast_cache_dir: Path) -> List[str]:
    failures: List[str] = []
    if not mast_cache_dir.exists():
        return failures

    for data_file in sorted(p for p in mast_cache_dir.rglob("*") if p.is_file()):
        if data_file.name.endswith(".meta.json"):
            if not any(data_file.with_name(data_file.name[:-10] + ext).exists() for ext in (".ecsv", ".csv")):
                failures.append(f"Metadata without a data file: {data_file.name}")
        elif not data_file.with_name(data_file.stem + ".meta.json").exists():
            failures.append(f"Cache file without metadata: {data_file.name}")

    for meta_file in mast_cache_dir.glob("*.meta.json"):
        ecsv_file = meta_file.with_suffix("").with_suffix(".ecsv")
        if not ecsv_file.exists():
            ecsv_file = ecsv_file.with_suffix(".csv")
        if not ecsv_file.exists():
            continue

        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:
            failures.append(f"Corrupted meta JSON in {meta_file.name}: {e}")
            continue

        # Check SHA-256
        expected_sha = meta.get("sha256")
        actual_sha = hashlib.sha256(ecsv_file.read_bytes()).hexdigest()
        if not expected_sha or expected_sha.lower() != actual_sha.lower():
            failures.append(f"SHA-256 mismatch for {ecsv_file.name}: expected {expected_sha}, computed {actual_sha}")

        if ecsv_file.suffix != ".ecsv":
            continue

        # Check for round whole-number dates
        ecsv_text = ecsv_file.read_text(encoding="utf-8", errors="replace")
        found_mjd = 0
        all_round = True
        for line in ecsv_text.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            for match in re.finditer(r"\b(5\d{4}|6\d{4})(\.\d+)?\b", line):
                found_mjd += 1
                if match.group(2) and not match.group(2).startswith(".0000"):
                    all_round = False
        if found_mjd > 5 and all_round:
            failures.append(
                f"Fabricated dates signature: all {found_mjd} MJD dates in {ecsv_file.name} are whole integers"
            )

    return failures


def check_cycle4_targets(cycle4_csv: Path, cycle4_source_md: Path) -> List[str]:
    failures: List[str] = []
    if not cycle4_csv.exists():
        return failures

    lines = [
        line.strip() for line in cycle4_csv.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()
    ]
    # Header line only means empty/clean
    if len(lines) > 1:
        if (
            not cycle4_source_md.exists()
            or len(cycle4_source_md.read_text(encoding="utf-8", errors="replace").strip()) == 0
        ):
            failures.append(
                f"{cycle4_csv} contains {len(lines) - 1} data rows, but {cycle4_source_md} is missing or empty"
            )

    return failures


def main() -> int:
    repo_root = get_repo_root()
    ref_csv = repo_root / "backend" / "data" / "reference" / "jwst_transmission_targets.csv"
    review_md = repo_root / "reports" / "LABEL_REVIEW.md"
    mast_cache = repo_root / "reports" / ".mast_cache"
    cycle4_csv = repo_root / "backend" / "data" / "reference" / "jwst_cycle4_targets.csv"
    cycle4_source = repo_root / "reports" / "CYCLE4_SOURCE.md"

    all_failures: List[str] = []

    # 1. Staged / committed mast cache
    staged_mast = check_staged_mast_cache(repo_root)
    all_failures.extend(staged_mast)

    # 2. Reference transmission targets
    trans_fails, verified_cnt, total_cnt = check_transmission_targets(ref_csv, review_md)
    all_failures.extend(trans_fails)

    # 3. MAST cache files
    cache_fails = check_mast_cache_files(mast_cache)
    all_failures.extend(cache_fails)

    # 4. Cycle 4 targets
    cycle4_fails = check_cycle4_targets(cycle4_csv, cycle4_source)
    all_failures.extend(cycle4_fails)

    print("=" * 72)
    print(" ExoSignal Scientific Data Integrity Audit")
    print("=" * 72)
    print(f" Reference Targets: {verified_cnt} verified / {total_cnt} total rows")

    if all_failures:
        print(f"\n [FAIL] {len(all_failures)} integrity failure(s) detected:")
        for fail in all_failures:
            print(f"   * {fail}")
        print("=" * 72)
        return 1
    else:
        print("\n [PASS] All scientific data integrity rules satisfied.")
        print("=" * 72)
        return 0


if __name__ == "__main__":
    sys.exit(main())
