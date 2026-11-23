#!/usr/bin/env python3
"""CI ML benchmark regression gate (run from the backend/ directory).

The benchmark trains rankers on JWST transmission labels. Labels count only when a human verified them
(verified=True, observation_type=transmission; see reports/LABEL_REVIEW.md), and the pipeline refuses to
train on fewer than 15. Retraining with fewer verified labels is impossible (one class) or meaningless,
so in that case this gate:
  - validates the structure of the committed evaluation report of the active artifact, and
  - emits a visible GitHub Actions warning that the benchmark was skipped and why.
It never reports a silent pass and never counts unverified labels.

With >= 15 verified labels it runs the benchmark and enforces the regression gates.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

MIN_VERIFIED_PLANETS = 15
MIN_LEADERBOARD_MODELS = 7
DEFAULT_METRICS = ("ap", "ndcg@25")
BACKEND = Path(__file__).resolve().parent.parent / "backend"
LABELS_CSV = BACKEND / "data" / "reference" / "jwst_transmission_targets.csv"


def annotate(level: str, message: str) -> None:
    """GitHub Actions workflow command (shown as an annotation on the run)."""
    print(f"::{level}::{message}")


def count_verified_planets(path: Path = LABELS_CSV) -> int:
    if not path.exists():
        return 0
    with open(path, newline="", encoding="utf-8") as f:
        return len(
            {
                row.get("planet_name", "").strip()
                for row in csv.DictReader(f)
                if str(row.get("verified", "")).strip().lower() in ("true", "1", "yes")
                and str(row.get("observation_type", "")).strip().lower() == "transmission"
            }
        )


def validate_committed_report(backend: Path = BACKEND, metrics: Sequence[str] = DEFAULT_METRICS) -> List[str]:
    """Structural checks on the committed evaluation report of the active artifact."""
    errors: List[str] = []
    pointer = backend / "artifacts" / "active_version.txt"
    if not pointer.exists():
        return ["artifacts/active_version.txt missing"]
    version = pointer.read_text(encoding="utf-8").strip()
    path = backend / "artifacts" / version / "evaluation.json"
    if not path.exists():
        return [f"artifacts/{version}/evaluation.json missing"]
    report: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    board = report.get("leaderboard") or []
    names = [m.get("model_name", "") for m in board]
    if len(board) < MIN_LEADERBOARD_MODELS:
        errors.append(f"leaderboard has {len(board)} models, expected >= {MIN_LEADERBOARD_MODELS}")
    if not any("TSM" in n for n in names):
        errors.append("no TSM baseline in the leaderboard")
    selected = (report.get("selected_production_model") or {}).get("model_name")
    if not selected:
        errors.append("selected_production_model.model_name missing")
    elif selected not in names:
        errors.append(f"selected production model {selected!r} is not in the leaderboard")
    for m in board:
        for metric in metrics:
            if not isinstance(m.get(metric), (int, float)):
                errors.append(f"model {m.get('model_name')!r} has no numeric {metric!r}")
    if not isinstance(report.get("n_positives"), int) or report["n_positives"] <= 0:
        errors.append("n_positives missing or not a positive integer")
    return errors


def run_benchmark(metrics: Sequence[str] = DEFAULT_METRICS) -> int:
    sys.path.insert(0, str(BACKEND))
    from app.ml.evaluation import RankingBenchmarkSuite
    from app.services.data_processor import get_data_processor

    df = get_data_processor().get_processed_data()
    report = RankingBenchmarkSuite().run_benchmark(df, eval_split="test")
    board = report.get("leaderboard") or []
    errors = []
    if len(board) < MIN_LEADERBOARD_MODELS:
        errors.append(f"expected >= {MIN_LEADERBOARD_MODELS} benchmark models, got {len(board)}")
    if not report.get("test_set_size"):
        errors.append("test split is empty")
    for metric in ("map", *metrics):
        if any(not isinstance(m.get(metric), (int, float)) for m in board):
            errors.append(f"a leaderboard entry has no numeric {metric!r}")
    for e in errors:
        annotate("error", f"benchmark gate: {e}")
    (BACKEND / "benchmark-ci-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not errors:
        print("All ML benchmark regression gates passed")
    return 1 if errors else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CI ML benchmark regression gate")
    parser.add_argument("--require-metrics", default=",".join(DEFAULT_METRICS), help="comma-separated, e.g. ap,ndcg@25")
    args = parser.parse_args(argv)
    metrics = [m.strip() for m in args.require_metrics.split(",") if m.strip()]

    n = count_verified_planets()
    if n >= MIN_VERIFIED_PLANETS:
        print(f"{n} verified transmission planets: running the benchmark")
        return run_benchmark(metrics)

    errors = validate_committed_report(metrics=metrics)
    for e in errors:
        annotate("error", f"committed evaluation report: {e}")
    if errors:
        return 1
    annotate(
        "warning",
        f"ML benchmark SKIPPED: {n} human-verified transmission labels (< {MIN_VERIFIED_PLANETS} required). "
        "Retraining needs verified labels (scripts/review_labels.py). The committed evaluation report passed "
        "structural checks; its metrics are provisional.",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
