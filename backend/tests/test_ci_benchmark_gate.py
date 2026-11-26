"""CI benchmark gate: never counts unverified labels, never passes silently.

SYNTHETIC TEST DATA: label CSVs and evaluation reports below are fictional (SYN-* planets).
"""

import importlib
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

gate = importlib.import_module("ci_benchmark_gate")

HEADER = "planet_name,program_id,cycle,mode,source_url,observation_type,verified,needs_review,notes\n"


def _labels(tmp_path, rows):
    p = tmp_path / "labels.csv"
    p.write_text(HEADER + "".join(rows), encoding="utf-8")
    return p


def _report(tmp_path, board_names, selected, n_pos=12):
    art = tmp_path / "artifacts"
    (art / "vSYN").mkdir(parents=True)
    (art / "active_version.txt").write_text("vSYN", encoding="utf-8")
    board = [{"model_name": n, "ap": 0.1, "ndcg@25": 0.2} for n in board_names]
    (art / "vSYN" / "evaluation.json").write_text(
        json.dumps({"leaderboard": board, "selected_production_model": {"model_name": selected}, "n_positives": n_pos}),
        encoding="utf-8",
    )
    return tmp_path


NAMES = ["LR A", "LR B", "GBM A", "Distance", "TSM-Only Baseline", "Heuristic", "Random"]


def test_unverified_and_non_transmission_rows_are_not_counted(tmp_path):
    p = _labels(
        tmp_path,
        [
            "SYN-1 b,1,1,x,u,transmission,True,False,\n",
            "SYN-1 b,2,1,x,u,transmission,True,False,\n",  # same planet twice counts once
            "SYN-2 b,3,1,x,u,transmission,False,True,\n",
            "SYN-3 b,4,1,x,u,emission,True,False,\n",
        ],
    )
    log = tmp_path / "REVIEW.md"
    assert gate.count_verified_planets(p, log) == 0  # no review log, no label
    log.write_text("# SYNTHETIC TEST DATA\n", encoding="utf-8")
    assert gate.count_verified_planets(p, log) == 0  # verified=True without its approval
    head = "| planet | program_id | source_url | checked_by | date | decision |\n|---|---|---|---|---|---|\n"
    row = "| SYN-1 b | 1 | u | SYNTHETIC REVIEWER | 2026-11-01 | %s: transmission |\n"
    log.write_text(head + row % "APPROVED", encoding="utf-8")
    assert gate.count_verified_planets(p, log) == 1
    log.write_text(head + row % "APPROVED" + row % "REJECTED", encoding="utf-8")
    assert gate.count_verified_planets(p, log) == 0


def test_valid_committed_report_has_no_errors(tmp_path):
    assert gate.validate_committed_report(_report(tmp_path, NAMES, "LR A")) == []


def test_report_errors_are_detected(tmp_path):
    errors = gate.validate_committed_report(_report(tmp_path, ["LR A", "Random"], "Unknown model", n_pos=0))
    joined = " ".join(errors)
    assert "expected >= 7" in joined
    assert "no TSM baseline" in joined
    assert "not in the leaderboard" in joined
    assert "n_positives" in joined


def test_skip_is_announced_as_a_warning_not_a_silent_pass(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate, "count_verified_planets", lambda: 0)
    monkeypatch.setattr(gate, "validate_committed_report", lambda **k: [])
    assert gate.main([]) == 0
    out = capsys.readouterr().out
    assert out.startswith("::warning::ML benchmark SKIPPED: 0 human-verified")


def test_broken_committed_report_fails_even_when_skipping(monkeypatch, capsys):
    monkeypatch.setattr(gate, "count_verified_planets", lambda: 3)
    monkeypatch.setattr(gate, "validate_committed_report", lambda **k: ["leaderboard has 2 models"])
    assert gate.main([]) == 1
    assert "::error::" in capsys.readouterr().out


def test_enough_verified_labels_runs_the_benchmark(monkeypatch):
    monkeypatch.setattr(gate, "count_verified_planets", lambda: 20)
    monkeypatch.setattr(gate, "run_benchmark", lambda metrics: 0)
    assert gate.main([]) == 0


def test_missing_ndcg_metric_is_an_error(tmp_path):
    root = _report(tmp_path, NAMES, "LR A")
    path = root / "artifacts" / "vSYN" / "evaluation.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["leaderboard"][0]["ndcg@25"]
    path.write_text(json.dumps(data), encoding="utf-8")
    errors = gate.validate_committed_report(root, metrics=["ap", "ndcg@25"])
    assert any("ndcg@25" in e for e in errors)
