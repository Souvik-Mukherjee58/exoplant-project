#!/usr/bin/env python3
"""
scripts/guard_changes.py

ExoSignal Automatic Change Guard
Python standard library only. Compatible with Windows and Linux.

Validates that code changes do not bypass protections:
- Protected paths (.guard.toml, .guard-allow)
- Ground-truth data integrity & review requirements
- Test suite integrity (no skips, deletions, or weakened assertions)
- Secrets detection
- Honesty warnings on unverified claims/metrics
- Full test and linter execution (--full)
"""

import argparse
import fnmatch
import hashlib
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_cmd(cmd: List[str] | str, cwd: Optional[Path] = None, shell: bool = False) -> Tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd or get_repo_root(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=shell,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def load_guard_toml(repo_root: Path) -> Dict[str, Any]:
    toml_path = repo_root / ".guard.toml"
    if not toml_path.exists():
        return {
            "protected": {
                "paths": [
                    "backend/data/reference/",
                    "reports/.mast_cache/",
                    "reports/*.csv",
                    "reports/LABEL_REVIEW.md",
                    "reports/CYCLE4_SOURCE.md",
                    "reports/k6_summary.json",
                    "docs/assets/**",
                    ".guard.toml",
                    ".guard-allow",
                    "scripts/guard_changes.py",
                    ".github/workflows/guard.yml",
                    ".pre-commit-config.yaml",
                    ".agent/PLAN.md",
                ],
                "guard_self_files": [
                    "scripts/guard_changes.py",
                    ".guard.toml",
                    ".guard-allow",
                    ".github/workflows/guard.yml",
                    ".pre-commit-config.yaml",
                ],
            }
        }
    with open(toml_path, "rb") as f:
        return tomllib.load(f)


def load_guard_allow(repo_root: Path) -> List[str]:
    allow_path = repo_root / ".guard-allow"
    if not allow_path.exists():
        return []
    allowed: List[str] = []
    with open(allow_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                allowed.append(line.replace("\\", "/"))
    return allowed


def match_path_rule(path_str: str, pattern: str) -> bool:
    norm_path = path_str.replace("\\", "/").lstrip("./")
    norm_pattern = pattern.replace("\\", "/").lstrip("./")

    # Directory match
    if norm_pattern.endswith("/"):
        if norm_path.startswith(norm_pattern) or norm_path == norm_pattern.rstrip("/"):
            return True

    # Glob match
    if fnmatch.fnmatch(norm_path, norm_pattern):
        return True

    # Subpath match for glob like docs/assets/**
    if "**" in norm_pattern:
        prefix = norm_pattern.split("**")[0]
        if norm_path.startswith(prefix):
            return True

    return norm_path == norm_pattern


class GuardRunner:
    def __init__(self, base: Optional[str] = None, staged_only: bool = False, full: bool = False):
        self.repo_root = get_repo_root()
        self.base = base
        self.staged_only = staged_only
        self.full = full
        self.config = load_guard_toml(self.repo_root)
        self.guard_allow = load_guard_allow(self.repo_root)

        self.failures: List[str] = []
        self.warnings: List[str] = []
        self.allow_used: List[Tuple[str, str]] = []

        self.changed_files: List[str] = []
        self.staged_files: List[str] = []
        self.untracked_files: List[str] = []
        self.deleted_files: List[str] = []
        self.added_files: List[str] = []
        self.diff_text: str = ""

    def collect_git_changes(self) -> None:
        # Collect porcelain status
        ret, out, _ = run_cmd(["git", "status", "--porcelain"])
        for line in out.splitlines():
            if len(line) < 4:
                continue
            status = line[:2]
            filepath = line[3:].strip().strip('"').replace("\\", "/")
            if " -> " in filepath:
                filepath = filepath.split(" -> ")[1].strip().strip('"')

            if status.startswith("??"):
                p = self.repo_root / filepath
                if p.is_dir():
                    for sub in p.rglob("*"):
                        if sub.is_file():
                            self.untracked_files.append(sub.relative_to(self.repo_root).as_posix())
                else:
                    self.untracked_files.append(filepath)
            else:
                if status[0] in ("M", "A", "R", "D"):
                    self.staged_files.append(filepath)
                if status[1] in ("M", "D"):
                    self.changed_files.append(filepath)
                if "D" in status:
                    self.deleted_files.append(filepath)
                if "A" in status or status.startswith("??"):
                    self.added_files.append(filepath)

        # Base comparison for CI or local branch
        if self.base:
            ret, out, _ = run_cmd(["git", "diff", "--name-only", f"{self.base}...HEAD"])
            for line in out.splitlines():
                p = line.strip().replace("\\", "/")
                if p and p not in self.changed_files:
                    self.changed_files.append(p)
            ret, diff_out, _ = run_cmd(["git", "diff", f"{self.base}...HEAD"])
            self.diff_text = diff_out
        elif self.staged_only:
            self.changed_files = list(set(self.staged_files))
            ret, diff_out, _ = run_cmd(["git", "diff", "--cached"])
            self.diff_text = diff_out
        else:
            # Combine tracked changes + untracked
            all_files = set(self.changed_files) | set(self.staged_files) | set(self.untracked_files)
            self.changed_files = sorted(list(all_files))
            ret, diff_cached, _ = run_cmd(["git", "diff", "--cached"])
            ret, diff_unstaged, _ = run_cmd(["git", "diff"])
            self.diff_text = diff_cached + "\n" + diff_unstaged

    def print_inspections(self) -> None:
        print("=" * 78)
        print(" ExoSignal Automatic Change Guard")
        print("=" * 78)

        # Print --stat
        diff_target = [f"{self.base}...HEAD"] if self.base else (["--cached"] if self.staged_only else ["HEAD"])
        ret, stat_out, _ = run_cmd(["git", "diff", "--stat"] + diff_target)
        if stat_out.strip():
            print("--- Git Diff Stat ---")
            print(stat_out.strip())
            print("-" * 78)

        # Print focused diffs for critical areas
        ret, crit_diff, _ = run_cmd(["git", "diff"] + diff_target + ["--", "backend/data/reference", "reports", "scripts"])
        if crit_diff.strip():
            print("--- Detailed Diff for Critical Paths (data/reports/scripts) ---")
            # Limit printing to first 200 lines to avoid log explosion
            diff_lines = crit_diff.strip().splitlines()
            for line_entry in diff_lines[:200]:
                print(line_entry)
            if len(diff_lines) > 200:
                print(f"... [truncated {len(diff_lines) - 200} lines] ...")
            print("-" * 78)

    def check_protected_paths(self) -> None:
        protected_rules: List[str] = self.config.get("protected", {}).get("paths", [])
        guard_self_files: List[str] = self.config.get("protected", {}).get("guard_self_files", [
            "scripts/guard_changes.py",
            ".guard.toml",
            ".guard-allow",
            ".github/workflows/guard.yml",
            ".pre-commit-config.yaml",
        ])

        for filepath in self.changed_files:
            # 1. Check if it matches a guard-self file: CAN NEVER BE ALLOWED
            is_guard_self = False
            for self_rule in guard_self_files:
                if match_path_rule(filepath, self_rule):
                    is_guard_self = True
                    # If this is .guard-allow itself being added or modified, check if allowed
                    # The prompt rule says: ".guard-allow can never allow the guard's own files."
                    # If guard file is changed, FAIL.
                    self.failures.append(
                        f"PROTECTED GUARD INFRASTRUCTURE MODIFIED: {filepath} cannot be modified or bypassed."
                    )
                    break
            if is_guard_self:
                continue

            # 2. Check if it matches any other protected path
            is_protected = False
            matching_rule = ""
            for rule in protected_rules:
                if match_path_rule(filepath, rule):
                    is_protected = True
                    matching_rule = rule
                    break

            if is_protected:
                # Check if covered by .guard-allow
                allowed = False
                for allow_rule in self.guard_allow:
                    if match_path_rule(filepath, allow_rule):
                        allowed = True
                        self.allow_used.append((filepath, allow_rule))
                        break

                if not allowed:
                    self.failures.append(
                        f"PROTECTED FILE MODIFIED: '{filepath}' matches protected rule '{matching_rule}'. "
                        f"Must be explicitly listed in .guard-allow by human reviewer to proceed."
                    )

    def check_data_integrity(self) -> None:
        ref_csv_path = self.repo_root / "backend" / "data" / "reference" / "jwst_transmission_targets.csv"
        review_md_path = self.repo_root / "reports" / "LABEL_REVIEW.md"
        cycle4_csv_path = self.repo_root / "backend" / "data" / "reference" / "jwst_cycle4_targets.csv"
        cycle4_source_path = self.repo_root / "reports" / "CYCLE4_SOURCE.md"
        mast_cache_dir = self.repo_root / "reports" / ".mast_cache"

        # 1. Check verified=True rows in jwst_transmission_targets.csv
        if ref_csv_path.exists():
            import csv
            verified_planets: List[Dict[str, str]] = []
            with open(ref_csv_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    v_str = str(row.get("verified", "")).strip().lower()
                    if v_str in ("true", "1", "yes"):
                        verified_planets.append(row)

            # Check matching review entries
            review_text = review_md_path.read_text(encoding="utf-8", errors="replace") if review_md_path.exists() else ""

            for row in verified_planets:
                planet = row.get("planet_name", "").strip()
                obs_type = row.get("observation_type", "").strip().lower()
                pid = row.get("program_id", "").strip()
                url = row.get("source_url", "").strip()

                if obs_type != "transmission":
                    self.failures.append(
                        f"DATA INTEGRITY FAIL: Planet '{planet}' has verified=True but observation_type='{obs_type}' != 'transmission'."
                    )
                if not pid or pid.lower() in ("n/a", "none", "nan", "todo"):
                    self.failures.append(
                        f"DATA INTEGRITY FAIL: Planet '{planet}' has verified=True but program_id is empty/invalid ('{pid}')."
                    )
                if not url or url.lower() in ("n/a", "none", "nan", "todo"):
                    self.failures.append(
                        f"DATA INTEGRITY FAIL: Planet '{planet}' has verified=True but source_url is empty/invalid ('{url}')."
                    )

                # Must have matching APPROVED row with checked_by and date in LABEL_REVIEW.md
                if not review_md_path.exists():
                    self.failures.append(
                        f"DATA INTEGRITY FAIL: Planet '{planet}' is verified=True but reports/LABEL_REVIEW.md does not exist."
                    )
                else:
                    # Match planet in review markdown with APPROVED
                    # Case insensitive check for planet and APPROVED
                    planet_escaped = re.escape(planet)
                    # Look for pattern where planet line has APPROVED, checked_by, and ISO date
                    pattern = rf"{planet_escaped}.*?(APPROVED|approved).*?(\d{{4}}-\d{{2}}-\d{{2}})"
                    if not re.search(pattern, review_text, re.DOTALL):
                        self.failures.append(
                            f"DATA INTEGRITY FAIL: Planet '{planet}' is verified=True in CSV but has no matching 'APPROVED' entry with date and reviewer in reports/LABEL_REVIEW.md."
                        )

        # 2. Check that no files under reports/.mast_cache/ are committed or staged
        for filepath in self.staged_files:
            if filepath.startswith("reports/.mast_cache/"):
                self.failures.append(
                    f"DATA INTEGRITY FAIL: File '{filepath}' under reports/.mast_cache/ cannot be committed or staged."
                )

        # 3. Check MAST cache integrity if cache exists
        if mast_cache_dir.exists():
            for meta_file in mast_cache_dir.glob("*.meta.json"):
                ecsv_file = meta_file.with_suffix("").with_suffix(".ecsv")
                if not ecsv_file.exists():
                    continue

                import json
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta_data = json.load(f)
                except Exception as e:
                    self.failures.append(f"DATA INTEGRITY FAIL: Corrupted MAST meta JSON '{meta_file}': {e}")
                    continue

                stored_sha = meta_data.get("sha256")
                actual_sha = hashlib.sha256(ecsv_file.read_bytes()).hexdigest()
                if not stored_sha or stored_sha.lower() != actual_sha.lower():
                    self.failures.append(
                        f"DATA INTEGRITY FAIL: SHA-256 mismatch in MAST cache '{ecsv_file.name}' (stored: {stored_sha}, actual: {actual_sha})."
                    )

                # Check all-whole-number t_min/t_max in cache file
                ecsv_content = ecsv_file.read_text(encoding="utf-8", errors="replace")
                all_round = True
                found_dates = 0
                for file_line in ecsv_content.splitlines():
                    if file_line.startswith("#") or not file_line.strip():
                        continue
                    # Check numbers in 50000-70000 range (MJD)
                    for m in re.finditer(r"\b(5\d{4}|6\d{4})(\.\d+)?\b", file_line):
                        found_dates += 1
                        if m.group(2) and not m.group(2).startswith(".0000"):
                            all_round = False
                if found_dates > 5 and all_round:
                    self.failures.append(
                        f"DATA INTEGRITY FAIL: MAST cache file '{ecsv_file.name}' has all whole-number MJD dates (fabricated data signature)."
                    )

        # 4. Check jwst_cycle4_targets.csv
        if cycle4_csv_path.exists():
            csv_lines = [
                row_line.strip()
                for row_line in cycle4_csv_path.read_text(encoding="utf-8", errors="replace").splitlines()
                if row_line.strip()
            ]
            has_data_rows = len(csv_lines) > 1  # header + data
            if has_data_rows:
                if not cycle4_source_path.exists() or len(cycle4_source_path.read_text(encoding="utf-8", errors="replace").strip()) == 0:
                    self.failures.append(
                        "DATA INTEGRITY FAIL: backend/data/reference/jwst_cycle4_targets.csv has data rows but reports/CYCLE4_SOURCE.md is missing or empty."
                    )

    def check_test_integrity(self) -> None:
        # 1. Deleted files under backend/tests/ or frontend/src/test/
        for deleted in self.deleted_files:
            if deleted.startswith("backend/tests/") or deleted.startswith("frontend/src/test/"):
                self.failures.append(
                    f"TEST INTEGRITY FAIL: Test file '{deleted}' was deleted. Tests must never be deleted."
                )

        # 2. Check diff text for skip/xfail and disabled checks on test files
        # Process diff per file
        file_diffs = re.split(r"^diff --git ", self.diff_text, flags=re.M)
        for fdiff in file_diffs:
            if not fdiff.strip():
                continue
            lines = fdiff.splitlines()
            header = lines[0] if lines else ""
            m = re.search(r"b/(\S+)", header)
            target_path = m.group(1) if m else ""

            is_test_file = target_path.startswith("backend/tests/") or target_path.startswith("frontend/src/test/")

            added_asserts = 0
            removed_asserts = 0

            for line in lines:
                if line.startswith("+++") or line.startswith("---"):
                    continue

                if line.startswith("+"):
                    added_content = line[1:].strip()
                    # Check skip patterns
                    if is_test_file:
                        if any(pattern in added_content for pattern in (
                            "pytest.mark.skip",
                            "pytest.mark.xfail",
                            "pytest.skip(",
                            "it.skip",
                            "describe.skip",
                            "test.skip",
                            "xit(",
                        )):
                            self.failures.append(
                                f"TEST INTEGRITY FAIL: Test skip marker added in {target_path}: '{added_content}'"
                            )

                        if "noqa" in added_content or "eslint-disable" in added_content:
                            self.failures.append(
                                f"TEST INTEGRITY FAIL: Linter disable comment added in test file {target_path}: '{added_content}'"
                            )

                        if re.search(r"\bassert\b|\bexpect\(", added_content):
                            added_asserts += 1

                elif line.startswith("-"):
                    removed_content = line[1:].strip()
                    if is_test_file:
                        if re.search(r"\bassert\b|\bexpect\(", removed_content):
                            removed_asserts += 1

            if is_test_file and removed_asserts > added_asserts and removed_asserts > 0:
                self.failures.append(
                    f"TEST INTEGRITY FAIL: Net loss of assertions in {target_path} (removed {removed_asserts}, added {added_asserts}). Never weaken tests."
                )

        # 3. Check fixtures for 'SYNTHETIC TEST DATA'
        fixture_dir = self.repo_root / "backend" / "tests" / "fixtures"
        if fixture_dir.exists():
            for fpath in fixture_dir.rglob("*"):
                if fpath.is_file():
                    rel_path = fpath.relative_to(self.repo_root).as_posix()
                    # If this fixture was added or modified
                    if rel_path in self.changed_files:
                        try:
                            content = fpath.read_text(encoding="utf-8", errors="replace")
                            if "SYNTHETIC TEST DATA" not in content:
                                self.failures.append(
                                    f"TEST INTEGRITY FAIL: Test fixture '{rel_path}' must explicitly contain the watermark 'SYNTHETIC TEST DATA'."
                                )
                        except Exception:
                            pass

    def check_secrets(self) -> None:
        secret_patterns = [
            (r"\bAKIA[0-9A-Z]{16}\b", "AWS Access Key ID"),
            (r"\bghp_[a-zA-Z0-9]{36}\b", "GitHub Personal Access Token"),
            (r"\bsk-[a-zA-Z0-9]{20,}\b", "Secret API Key"),
            (r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", "Private Key Block"),
            (r"(?i)\bpassword\s*=\s*['\"][^'\"]{4,}['\"]", "Hard-coded Password Literal"),
        ]

        for line in self.diff_text.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                for pattern, desc in secret_patterns:
                    if re.search(pattern, line):
                        self.failures.append(f"SECRETS FAIL: Potential {desc} detected in added diff line: {line[:50]}...")

    def check_honesty_warnings(self) -> None:
        watched_roots = ("frontend/src", "README.md", "docs", "reports")
        units_pattern = r"\b\d+(\.\d+)?\s*(%|ms|RPS|x faster)\b"
        buzzword_pattern = r"\b(verified|production-grade|real-time|state-of-the-art|guarantee)\b"

        # Check line by line in diff
        file_diffs = re.split(r"^diff --git ", self.diff_text, flags=re.M)
        for fdiff in file_diffs:
            if not fdiff.strip():
                continue
            lines = fdiff.splitlines()
            header = lines[0] if lines else ""
            m = re.search(r"b/(\S+)", header)
            target_path = m.group(1) if m else ""

            is_watched = any(target_path == r or target_path.startswith(r.rstrip("/") + "/") for r in watched_roots)
            if not is_watched:
                continue

            # Don't flag honesty inside tests, scripts/guard_changes.py, or markdown results tables
            if "test" in target_path or "guard" in target_path:
                continue

            line_num = 0
            for line_str in lines:
                if line_str.startswith("@@"):
                    # Extract new line start
                    match = re.search(r"\+(\d+)", line_str)
                    if match:
                        line_num = int(match.group(1))
                    continue
                elif line_str.startswith("+") and not line_str.startswith("+++"):
                    added_text = line_str[1:]
                    # Check numbers + units
                    m_unit = re.search(units_pattern, added_text, re.IGNORECASE)
                    if m_unit:
                        self.warnings.append(
                            f"{target_path}:{line_num}: Hard-coded metric added '{m_unit.group(0)}' (ensure derived from artifacts)."
                        )
                    # Check buzzwords
                    m_buzz = re.search(buzzword_pattern, added_text, re.IGNORECASE)
                    if m_buzz:
                        self.warnings.append(
                            f"{target_path}:{line_num}: Unsubstantiated buzzword added '{m_buzz.group(0)}' (verify empirical evidence)."
                        )
                    line_num += 1
                elif not line_str.startswith("-"):
                    line_num += 1

    def run_full_suite(self) -> None:
        print("\n--- Running Full Backend & Frontend Verification Suite (--full) ---")
        # 1. Backend pytest
        pytest_cmd = [sys.executable, "-m", "pytest", "-q"]
        print("  Running: python -m pytest -q (backend)...")
        ret, out, err = run_cmd(pytest_cmd, cwd=self.repo_root / "backend")
        if ret != 0:
            self.failures.append(f"FULL SUITE FAIL: Backend pytest returned non-zero ({ret}):\n{out}\n{err}")
        else:
            print("  [PASS] Backend pytest")

        # 2. Ruff
        ruff_bin = shutil.which("ruff") or (self.repo_root / "backend" / "venv" / "Scripts" / "ruff.exe").as_posix()
        if Path(ruff_bin).exists() or shutil.which("ruff"):
            print("  Running: ruff check . (backend)...")
            ret, out, err = run_cmd([ruff_bin, "check", "."], cwd=self.repo_root / "backend")
            if ret != 0:
                self.failures.append(f"FULL SUITE FAIL: Ruff check failed:\n{out}\n{err}")
            else:
                print("  [PASS] Ruff linter")
        else:
            print("  [SKIPPED (ruff not installed)]")

        # 3. Mypy
        mypy_bin = shutil.which("mypy") or (self.repo_root / "backend" / "venv" / "Scripts" / "mypy.exe").as_posix()
        if Path(mypy_bin).exists() or shutil.which("mypy"):
            print("  Running: mypy app/ml app/scoring (backend)...")
            ret, out, err = run_cmd([mypy_bin, "app/ml", "app/scoring"], cwd=self.repo_root / "backend")
            if ret != 0:
                self.failures.append(f"FULL SUITE FAIL: Mypy check failed:\n{out}\n{err}")
            else:
                print("  [PASS] Mypy typing")
        else:
            print("  [SKIPPED (mypy not installed)]")

        # 4. Frontend npm run lint
        npm_bin = shutil.which("npm") or shutil.which("npm.cmd")
        if npm_bin and (self.repo_root / "frontend" / "package.json").exists():
            print("  Running: npm run lint (frontend)...")
            ret, out, err = run_cmd([npm_bin, "run", "lint"], cwd=self.repo_root / "frontend")
            if ret != 0:
                self.failures.append(f"FULL SUITE FAIL: Frontend ESLint failed:\n{out}\n{err}")
            else:
                print("  [PASS] Frontend ESLint")

            print("  Running: npm test -- --run (frontend)...")
            ret, out, err = run_cmd([npm_bin, "test", "--", "--run"], cwd=self.repo_root / "frontend")
            if ret != 0:
                self.failures.append(f"FULL SUITE FAIL: Frontend vitest failed:\n{out}\n{err}")
            else:
                print("  [PASS] Frontend vitest")

            print("  Running: npm run build (frontend)...")
            ret, out, err = run_cmd([npm_bin, "run", "build"], cwd=self.repo_root / "frontend")
            if ret != 0:
                self.failures.append(f"FULL SUITE FAIL: Frontend build failed:\n{out}\n{err}")
            else:
                print("  [PASS] Frontend build")
        else:
            print("  [SKIPPED (npm not installed)]")

    def execute(self) -> int:
        self.collect_git_changes()
        self.print_inspections()

        self.check_protected_paths()
        self.check_data_integrity()
        self.check_test_integrity()
        self.check_secrets()
        self.check_honesty_warnings()

        if self.full:
            self.run_full_suite()

        # Write .guard/last_run.md
        guard_dir = self.repo_root / ".guard"
        guard_dir.mkdir(parents=True, exist_ok=True)
        last_run_path = guard_dir / "last_run.md"

        now_utc = datetime.now(timezone.utc).isoformat()
        is_pass = len(self.failures) == 0

        report_lines = [
            "# ExoSignal Change Guard Report",
            f"**Timestamp**: {now_utc}",
            f"**Verdict**: {'PASS' if is_pass else 'FAIL'}",
            f"**Failures Count**: {len(self.failures)}",
            f"**Warnings Count**: {len(self.warnings)}",
            "",
            "## Summary Table",
            "| Check Category | Status | Details |",
            "|:---|:---:|:---|",
            f"| Protected Paths | {'FAIL' if any('PROTECTED' in f for f in self.failures) else 'PASS'} | {len([f for f in self.failures if 'PROTECTED' in f])} violations |",
            f"| Data Integrity | {'FAIL' if any('DATA' in f for f in self.failures) else 'PASS'} | {len([f for f in self.failures if 'DATA' in f])} violations |",
            f"| Test Suite Integrity | {'FAIL' if any('TEST' in f for f in self.failures) else 'PASS'} | {len([f for f in self.failures if 'TEST' in f])} violations |",
            f"| Secrets Guard | {'FAIL' if any('SECRETS' in f for f in self.failures) else 'PASS'} | {len([f for f in self.failures if 'SECRETS' in f])} violations |",
            f"| Honesty Metrics | {'WARN' if self.warnings else 'PASS'} | {len(self.warnings)} advisory notes |",
        ]

        if self.failures:
            report_lines.extend(["", "## Failures"])
            for f in self.failures:
                report_lines.append(f"- [FAIL] {f}")

        if self.warnings:
            report_lines.extend(["", "## Advisory Warnings"])
            for w in self.warnings:
                report_lines.append(f"- [WARN] {w}")

        if self.allow_used:
            report_lines.extend(["", "## .guard-allow Exceptions Utilized"])
            for f, r in self.allow_used:
                report_lines.append(f"- `{f}` allowed by rule `{r}`")

        last_run_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

        # Print output to terminal
        print("\n" + "=" * 78)
        if self.failures:
            print(f" GUARD: FAIL ({len(self.failures)} failure(s) detected)")
            print("=" * 78)
            for f in self.failures:
                print(f" [FAIL] {f}")
        else:
            print(" GUARD: PASS")
            print("=" * 78)

        if self.warnings:
            print("\n --- Advisory Honesty Warnings ---")
            for w in self.warnings:
                print(f" [WARN] {w}")

        if self.allow_used:
            print("\n [REMINDER] .guard-allow was utilized during this check:")
            for f, r in self.allow_used:
                print(f"   * {f} (rule: {r})")
            print(" Please delete .guard-allow once changes are committed!")

        return 0 if is_pass else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="ExoSignal Automatic Change Guard")
    parser.add_argument("--base", type=str, default=None, help="Base commit or branch to compare against (e.g. origin/main)")
    parser.add_argument("--staged", action="store_true", help="Fast mode: inspect staged changes only")
    parser.add_argument("--full", action="store_true", help="Comprehensive mode: execute full test suites, linters, and build")
    args = parser.parse_args()

    runner = GuardRunner(base=args.base, staged_only=args.staged, full=args.full)
    sys.exit(runner.execute())


if __name__ == "__main__":
    main()
