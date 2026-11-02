"""Tests for scripts/guard_changes.py.

SYNTHETIC TEST DATA.
Validates all Change Guard security, data integrity, test integrity, and honesty invariants.
"""

from pathlib import Path

import pytest
from scripts.guard_changes import GuardRunner, match_path_rule


@pytest.fixture
def repo_root():
    return Path(__file__).resolve().parent.parent.parent


def test_match_path_rule():
    """Verify prefix, exact, and glob path matching."""
    assert match_path_rule("backend/data/reference/file.csv", "backend/data/reference/")
    assert match_path_rule("reports/test.csv", "reports/*.csv")
    assert match_path_rule("docs/assets/sub/img.png", "docs/assets/**")
    assert match_path_rule(".guard.toml", ".guard.toml")
    assert not match_path_rule("frontend/src/App.jsx", "backend/data/reference/")


def test_guard_protected_path_fails_without_allow(monkeypatch, repo_root):
    """Protected file modifications must fail unless listed in .guard-allow."""
    runner = GuardRunner()
    runner.changed_files = ["backend/data/reference/jwst_transmission_targets.csv"]
    runner.guard_allow = []  # No allow rule

    runner.check_protected_paths()
    assert len(runner.failures) > 0
    assert any("PROTECTED FILE MODIFIED" in f for f in runner.failures)


def test_guard_allow_permits_protected_path(monkeypatch, repo_root):
    """Protected file modifications pass when explicitly listed in .guard-allow."""
    runner = GuardRunner()
    runner.changed_files = ["backend/data/reference/jwst_transmission_targets.csv"]
    runner.guard_allow = ["backend/data/reference/jwst_transmission_targets.csv"]

    runner.check_protected_paths()
    assert len(runner.failures) == 0
    assert len(runner.allow_used) == 1


def test_guard_cannot_allow_itself(monkeypatch, repo_root):
    """.guard-allow can NEVER bypass the guard's own files."""
    for guard_file in [
        "scripts/guard_changes.py",
        ".guard.toml",
        ".guard-allow",
        ".github/workflows/guard.yml",
        ".pre-commit-config.yaml",
    ]:
        runner = GuardRunner()
        runner.changed_files = [guard_file]
        # Even if human tries to put guard file in .guard-allow:
        runner.guard_allow = [guard_file, "**"]

        runner.check_protected_paths()
        assert len(runner.failures) > 0, f"Guard failed to block self-modification of {guard_file}"
        assert any("PROTECTED GUARD INFRASTRUCTURE MODIFIED" in f for f in runner.failures)


def test_guard_data_integrity_unapproved_row(monkeypatch, tmp_path):
    """verified=True without matching APPROVED entry in LABEL_REVIEW.md fails."""
    runner = GuardRunner()
    runner.repo_root = tmp_path

    ref_dir = tmp_path / "backend" / "data" / "reference"
    ref_dir.mkdir(parents=True)
    ref_csv = ref_dir / "jwst_transmission_targets.csv"
    ref_csv.write_text(
        "planet_name,program_id,source_url,observation_type,verified\n"
        "Unapproved-1 b,1234,https://stsci.edu/1234,transmission,True\n"
    )

    review_dir = tmp_path / "reports"
    review_dir.mkdir(parents=True)
    review_md = review_dir / "LABEL_REVIEW.md"
    review_md.write_text("# Review Log\nNo approved rows here\n")

    runner.check_data_integrity()
    assert any("has no matching 'APPROVED' entry" in f for f in runner.failures)


def test_guard_data_integrity_non_transmission_mode(monkeypatch, tmp_path):
    """verified=True with observation_type != 'transmission' fails."""
    runner = GuardRunner()
    runner.repo_root = tmp_path

    ref_dir = tmp_path / "backend" / "data" / "reference"
    ref_dir.mkdir(parents=True)
    ref_csv = ref_dir / "jwst_transmission_targets.csv"
    ref_csv.write_text(
        "planet_name,program_id,source_url,observation_type,verified\n"
        "Phase-Curve b,1234,https://stsci.edu/1234,phase_curve,True\n"
    )

    runner.check_data_integrity()
    assert any("!= 'transmission'" in f for f in runner.failures)


def test_guard_data_integrity_cycle4_missing_source(monkeypatch, tmp_path):
    """Cycle 4 CSV with data rows fails if reports/CYCLE4_SOURCE.md is missing."""
    runner = GuardRunner()
    runner.repo_root = tmp_path

    ref_dir = tmp_path / "backend" / "data" / "reference"
    ref_dir.mkdir(parents=True)
    cycle4_csv = ref_dir / "jwst_cycle4_targets.csv"
    cycle4_csv.write_text("planet_name,program_id,source_url\nTarget-1,9999,https://stsci.edu/9999\n")

    runner.check_data_integrity()
    assert any("reports/CYCLE4_SOURCE.md is missing" in f for f in runner.failures)


def test_guard_blocks_staged_mast_cache():
    """Staging or committing files under reports/.mast_cache/ fails."""
    runner = GuardRunner()
    runner.staged_files = ["reports/.mast_cache/WASP-39.ecsv"]

    runner.check_data_integrity()
    assert any("under reports/.mast_cache/ cannot be committed or staged" in f for f in runner.failures)


def test_guard_test_integrity_deleted_test():
    """Deleting a test file under backend/tests fails."""
    runner = GuardRunner()
    runner.deleted_files = ["backend/tests/test_old.py"]

    runner.check_test_integrity()
    assert any("was deleted. Tests must never be deleted" in f for f in runner.failures)


def test_guard_test_integrity_added_skip():
    """Adding pytest.mark.skip or xfail in test diff fails."""
    runner = GuardRunner()
    runner.diff_text = """
diff --git a/backend/tests/test_example.py b/backend/tests/test_example.py
--- a/backend/tests/test_example.py
+++ b/backend/tests/test_example.py
@@ -10,3 +10,4 @@
+@pytest.mark.skip(reason="temp")
 def test_foo():
"""
    runner.check_test_integrity()
    assert any("Test skip marker added" in f for f in runner.failures)


def test_guard_test_integrity_weakened_assertions():
    """Removing more assert lines than adding in a test file fails."""
    runner = GuardRunner()
    runner.diff_text = """
diff --git a/backend/tests/test_example.py b/backend/tests/test_example.py
--- a/backend/tests/test_example.py
+++ b/backend/tests/test_example.py
@@ -10,5 +10,2 @@
-    assert x == 10
-    assert y == 20
-    assert z == 30
+    assert x == 10
"""
    runner.check_test_integrity()
    assert any("Net loss of assertions" in f for f in runner.failures)


def test_guard_test_integrity_fixture_watermark(tmp_path):
    """Adding a fixture without 'SYNTHETIC TEST DATA' watermark fails."""
    runner = GuardRunner()
    runner.repo_root = tmp_path

    fix_dir = tmp_path / "backend" / "tests" / "fixtures"
    fix_dir.mkdir(parents=True)
    fix_file = fix_dir / "bad_fixture.csv"
    fix_file.write_text("col1,col2\n1,2\n")

    runner.changed_files = ["backend/tests/fixtures/bad_fixture.csv"]
    runner.check_test_integrity()
    assert any("SYNTHETIC TEST DATA" in f for f in runner.failures)


def test_guard_secrets_detection():
    """Detects AWS keys, GitHub tokens, and private keys in diff."""
    runner = GuardRunner()
    runner.diff_text = """
+AKIAIOSFODNN7EXAMPLE
+ghp_123456789012345678901234567890123456
+-----BEGIN RSA PRIVATE KEY-----
"""
    runner.check_secrets()
    assert len(runner.failures) >= 3
