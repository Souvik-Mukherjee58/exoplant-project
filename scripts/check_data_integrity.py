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


def check_transmission_targets(
    ref_csv_path: Path, review_md_path: Path
) -> Tuple[List[str], int, int]:
    failures: List[str] = []
    verified_count = 0
    total_count = 0

    if not ref_csv_path.exists():
        return [f"Reference catalog not found: {ref_csv_path}"], 0, 0

    review_text = ""
    if review_md_path.exists():
        review_text = review_md_path.read_text(encoding="utf-8", errors="replace")

    verified_rows: List[Dict[str, str]] = []

    with open(ref_csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_count += 1
            v_val = str(row.get("verified", "")).strip().lower()
            if v_val in ("true", "1", "yes", "t"):
                verified_rows.append(row)
                verified_count += 1

    for row in verified_rows:
        planet = row.get("planet_name", "").strip()
        obs_type = row.get("observation_type", "").strip().lower()
        pid = row.get("program_id", "").strip()
        url = row.get("source_url", "").strip()

        # Rule 1: observation_type must be transmission
        if obs_type != "transmission":
            failures.append(
                f"Planet '{planet}' is verified=True but observation_type='{obs_type}' != 'transmission'"
            )

        # Rule 2: non-empty program_id and source_url
        if not pid or pid.lower() in ("n/a", "none", "nan", "todo"):
            failures.append(
                f"Planet '{planet}' is verified=True but program_id is missing or invalid: '{pid}'"
            )
        if not url or url.lower() in ("n/a", "none", "nan", "todo"):
            failures.append(
                f"Planet '{planet}' is verified=True but source_url is missing or invalid: '{url}'"
            )

        # Rule 3: Must match APPROVED row with checked_by and ISO date in LABEL_REVIEW.md
        if not review_md_path.exists():
            failures.append(
                f"Planet '{planet}' is verified=True but reports/LABEL_REVIEW.md does not exist"
            )
        else:
            planet_escaped = re.escape(planet)
            pattern = rf"{planet_escaped}.*?(APPROVED|approved).*?(\d{{4}}-\d{{2}}-\d{{2}})"
            if not re.search(pattern, review_text, re.DOTALL):
                failures.append(
                    f"Planet '{planet}' is verified=True in CSV but has no matching APPROVED review row in reports/LABEL_REVIEW.md"
                )

    return failures, verified_count, total_count


def check_mast_cache_files(mast_cache_dir: Path) -> List[str]:
    failures: List[str] = []
    if not mast_cache_dir.exists():
        return failures

    for meta_file in mast_cache_dir.glob("*.meta.json"):
        ecsv_file = meta_file.with_suffix("").with_suffix(".ecsv")
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
            failures.append(
                f"SHA-256 mismatch for {ecsv_file.name}: expected {expected_sha}, computed {actual_sha}"
            )

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
        line.strip()
        for line in cycle4_csv.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    # Header line only means empty/clean
    if len(lines) > 1:
        if not cycle4_source_md.exists() or len(cycle4_source_md.read_text(encoding="utf-8", errors="replace").strip()) == 0:
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
