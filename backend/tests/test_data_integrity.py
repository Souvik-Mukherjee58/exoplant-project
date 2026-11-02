"""Unit tests for scripts/check_data_integrity.py.

SYNTHETIC TEST DATA.
Validates scientific data integrity checking logic using isolated temporary files.
"""

import hashlib
import json
from pathlib import Path

from scripts.check_data_integrity import (
    check_cycle4_targets,
    check_mast_cache_files,
    check_transmission_targets,
)


def test_transmission_targets_valid(tmp_path: Path):
    """Verified transmission target with matching APPROVED review entry passes."""
    ref_csv = tmp_path / "targets.csv"
    ref_csv.write_text(
        "planet_name,program_id,source_url,observation_type,verified\n"
        "SYNTHETIC-1 b,1234,https://stsci.edu/1234,transmission,True\n",
        encoding="utf-8",
    )
    review_md = tmp_path / "REVIEW.md"
    review_md.write_text(
        "# SYNTHETIC TEST DATA - Review\n"
        "| SYNTHETIC-1 b | 1234 | APPROVED: transmission | ReviewerA | 2026-11-01 |\n",
        encoding="utf-8",
    )

    fails, verified_cnt, total_cnt = check_transmission_targets(ref_csv, review_md)
    assert len(fails) == 0
    assert verified_cnt == 1
    assert total_cnt == 1


def test_transmission_targets_invalid_type_and_missing_review(tmp_path: Path):
    """Verified target with phase_curve mode or missing review entry fails."""
    ref_csv = tmp_path / "targets.csv"
    ref_csv.write_text(
        "planet_name,program_id,source_url,observation_type,verified\n"
        "SYNTHETIC-2 b,1234,https://stsci.edu/1234,phase_curve,True\n"
        "SYNTHETIC-3 b,5678,https://stsci.edu/5678,transmission,True\n",
        encoding="utf-8",
    )
    review_md = tmp_path / "REVIEW.md"
    review_md.write_text("# SYNTHETIC TEST DATA - Empty\n", encoding="utf-8")

    fails, verified_cnt, total_cnt = check_transmission_targets(ref_csv, review_md)
    assert len(fails) >= 2
    assert any("!= 'transmission'" in f for f in fails)
    assert any("no matching APPROVED review row" in f for f in fails)


def test_mast_cache_sha256_validation(tmp_path: Path):
    """MAST cache files with matching SHA-256 pass, mismatched fail."""
    cache_dir = tmp_path / ".mast_cache"
    cache_dir.mkdir()

    ecsv_file = cache_dir / "SYNTHETIC_TARGET.ecsv"
    ecsv_content = "# SYNTHETIC TEST DATA\nt_min,t_max\n59964.81234,59965.12345\n"
    ecsv_file.write_text(ecsv_content, encoding="utf-8")
    actual_sha = hashlib.sha256(ecsv_file.read_bytes()).hexdigest()

    meta_file = cache_dir / "SYNTHETIC_TARGET.meta.json"
    meta_file.write_text(json.dumps({"sha256": actual_sha}), encoding="utf-8")

    # Valid check
    fails = check_mast_cache_files(cache_dir)
    assert len(fails) == 0

    # Tampered file check
    meta_file.write_text(json.dumps({"sha256": "0000000000000000000000000000000000000000000000000000000000000000"}), encoding="utf-8")
    fails_bad = check_mast_cache_files(cache_dir)
    assert len(fails_bad) == 1
    assert "SHA-256 mismatch" in fails_bad[0]


def test_mast_cache_fabricated_whole_number_dates(tmp_path: Path):
    """MAST cache containing all whole integer MJD dates is flagged as fabricated."""
    cache_dir = tmp_path / ".mast_cache"
    cache_dir.mkdir()

    ecsv_file = cache_dir / "FAKE_TARGET.ecsv"
    # All integer dates without fractional seconds
    lines = ["# SYNTHETIC TEST DATA", "t_min,t_max"]
    for i in range(10):
        lines.append(f"5900{i},5901{i}")
    ecsv_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sha = hashlib.sha256(ecsv_file.read_bytes()).hexdigest()

    meta_file = cache_dir / "FAKE_TARGET.meta.json"
    meta_file.write_text(json.dumps({"sha256": sha}), encoding="utf-8")

    fails = check_mast_cache_files(cache_dir)
    assert len(fails) == 1
    assert "Fabricated dates signature" in fails[0]


def test_cycle4_targets_validation(tmp_path: Path):
    """Header-only Cycle 4 passes without source; data rows require CYCLE4_SOURCE.md."""
    cycle4_csv = tmp_path / "cycle4.csv"
    cycle4_source = tmp_path / "CYCLE4_SOURCE.md"

    # 1. Header only -> passes even without source md
    cycle4_csv.write_text("planet_name,program_id,source_url\n", encoding="utf-8")
    assert len(check_cycle4_targets(cycle4_csv, cycle4_source)) == 0

    # 2. Data rows without source md -> fails
    cycle4_csv.write_text("planet_name,program_id,source_url\nSYNTHETIC-1 b,9999,https://stsci.edu/9999\n", encoding="utf-8")
    fails = check_cycle4_targets(cycle4_csv, cycle4_source)
    assert len(fails) == 1

    # 3. Data rows with source md -> passes
    cycle4_source.write_text("# SYNTHETIC TEST DATA - Source\nAccess date: 2026-11-01\n", encoding="utf-8")
    assert len(check_cycle4_targets(cycle4_csv, cycle4_source)) == 0

