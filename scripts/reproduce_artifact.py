#!/usr/bin/env python3
"""Check that the served catalog follows from its sources. Offline; writes nothing.

    cd backend && python ../scripts/reproduce_artifact.py

1. Files: the raw snapshot, the model and the catalog have the recorded SHA-256.
2. Features: the raw snapshot and the current code give the feature columns of the catalog.
3. Scores: the committed model gives the final-model scores; host-grouped cross-validation gives the out-of-fold scores.
4. Ranks: the scores give the ranks and percentiles.

The labels are those stored in the catalog. They are NOT human-verified; they are used here only to repeat what was done.
Exit code 0 if everything agrees, 1 otherwise.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

TOLERANCE = 1e-9  # relative and absolute; columns of the same formula differ by a few 1e-16 between library versions
# Cross-validated scores come from an iterative solver: last-bit differences of the inputs and other CPU instructions move
# them by up to 1.5e-4 points (of 100; Windows and Linux, six OpenBLAS kernels). Ranks were equal everywhere and must be.
SOLVER_COLUMNS = {"oof_raw_score": 1e-4, "oof_priority_score": 1e-2, "priority_score": 1e-2, "ml_priority_score": 1e-2}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def differing_rows(new: pd.Series, served: pd.Series, absolute: float = TOLERANCE) -> int:
    if pd.api.types.is_bool_dtype(new) or pd.api.types.is_bool_dtype(served) or served.dtype == object:
        equal = new.astype(str) == served.astype(str)
    else:
        equal = pd.Series(np.isclose(new.astype(float), served.astype(float), rtol=TOLERANCE, atol=absolute), new.index)
    return int((~(equal | (new.isna() & served.isna()))).sum())


def check_files(version_dir: Path) -> List[str]:
    """Recorded against actual checksums and sizes."""
    problems: List[str] = []
    manifest = json.loads((version_dir / "manifest.json").read_text(encoding="utf-8"))
    entry = json.loads((version_dir / "registry_entry.json").read_text(encoding="utf-8"))
    raw = BACKEND / "data" / "raw" / manifest["raw_data"]["file"]
    if sha256(raw) != manifest["raw_data"]["sha256"]:
        problems.append("raw snapshot differs from manifest.json")
    for key, name in (("model", "ltr_model.joblib"), ("parquet", "planets.parquet")):
        path, record = version_dir / name, entry["artifacts"][key]
        if sha256(path) != record["sha256"] or path.stat().st_size != record["size_bytes"]:
            problems.append(f"{name} differs from registry_entry.json")
    if (version_dir / "planets.parquet").stat().st_size != manifest["catalog"]["parquet_size_bytes"]:
        problems.append("planets.parquet differs from manifest.json")
    return problems


def check_content(version_dir: Path) -> List[str]:
    """Features, scores and ranks computed again and compared column by column."""
    from app.config import settings
    from app.ml import ground_truth, ltr_model
    from app.ml.anomaly_detection import AnomalyDetector
    from app.scoring.priority_scorer import TargetPriorityScorer
    from app.services.data_cleaning import DataCleaning
    from app.services.feature_engineering import FeatureEngineering

    served = pd.read_parquet(version_dir / "planets.parquet").set_index("planet_name")
    manifest = json.loads((version_dir / "manifest.json").read_text(encoding="utf-8"))
    raw = pd.read_csv(BACKEND / "data" / "raw" / manifest["raw_data"]["file"])
    features = FeatureEngineering().transform(DataCleaning().clean(raw))
    detector = AnomalyDetector(contamination=settings.ANOMALY_CONTAMINATION, random_state=settings.RANDOM_STATE)
    detector.fit(features)
    scored = TargetPriorityScorer().score(detector.predict_anomaly_scores(features))
    if set(scored["planet_name"]) != set(served.index):
        return ["the raw snapshot does not give the planets of the catalog"]

    labels = set(served.index[served["is_jwst_target"].astype(bool)])
    original = ground_truth.get_verified_jwst_targets
    ground_truth.get_verified_jwst_targets = lambda *_args, **_kwargs: labels  # for this comparison only
    try:
        eligible = scored[scored["eligible_for_transmission"]].copy()
        out_of_fold = ltr_model.compute_out_of_fold_predictions(
            eligible, feature_variant="A", random_state=settings.RANDOM_STATE
        )
        model = ltr_model.ExoSignalLTRModel.load(str(version_dir / "ltr_model.joblib"))
        result = model.score_catalog(scored, oof_predictions=out_of_fold)
        labelled = ground_truth.generate_ground_truth_labels(scored)
    finally:
        ground_truth.get_verified_jwst_targets = original
    result = result.set_index("planet_name").reindex(served.index)
    labelled = labelled.set_index("planet_name").reindex(served.index)

    problems: List[str] = []
    for column in served.columns:
        source = result if column in result else labelled if column in labelled else None
        if source is None:
            problems.append(f"{column}: not produced by the current code")
        elif n := differing_rows(source[column], served[column], SOLVER_COLUMNS.get(column, TOLERANCE)):
            problems.append(f"{column}: {n} rows differ")
    print(f"{len(served)} planets, {len(served.columns)} columns, {len(labels)} labels (not human-verified)")
    return problems


def main() -> int:
    artifacts = BACKEND / "artifacts"
    version_dir = artifacts / (artifacts / "active_version.txt").read_text(encoding="utf-8").strip()
    problems = check_files(version_dir) + check_content(version_dir)
    for p in problems:
        print(f"[DIFFERENT] {p}")
    print("Reproduced" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
