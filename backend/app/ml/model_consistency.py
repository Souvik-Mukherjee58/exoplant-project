"""The explanation model must be the model that scored the served catalog.

The query engine (catalog) and the SHAP explainer (model) load their artifacts separately, so a deployment can
pair a catalog with a different model: for example ARTIFACT_VERSION naming a version without its own model file,
or files copied by hand. The explanations would then describe scores the API does not serve. This check runs once,
when the explainer is created at startup, and compares the actual model with the served artifact:

1. Identity: the SHA-256 of the loaded model file equals the checksum recorded for the served version
   (registry_entry.json), and the model comes from that version's directory.
2. Behaviour: the model reproduces the catalog's in-sample scores (the final model's scores of every planet).

It fails closed: if the served version records no checksum, or the catalog has no score to compare with, the
model cannot be verified and the check fails.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple

import numpy as np
import pandas as pd

SCORE_TOLERANCE = 0.01  # score points (0 to 100), the tolerance of the served-score flag in explanations


class _ScoringModel(Protocol):
    def predict_priority_scores(self, df: pd.DataFrame) -> np.ndarray: ...


@dataclass(frozen=True)
class ModelConsistencyReport:
    """What was compared, and every difference found (none means the model is the served one)."""

    served_version: Optional[str]
    model_path: str
    model_version: str
    model_sha256: str
    recorded_sha256: Optional[str]
    planets_compared: int
    max_score_difference: Optional[float]
    problems: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.problems

    def as_dict(self) -> Dict[str, Any]:
        return {
            "verified": self.ok,
            "served_version": self.served_version,
            "model_version": self.model_version,
            "model_sha256": self.model_sha256,
            "recorded_sha256": self.recorded_sha256,
            "planets_compared": self.planets_compared,
            "max_score_difference": self.max_score_difference,
            "problems": list(self.problems),
        }


class ExplanationsUnavailable(RuntimeError):
    """The explanation model does not match, or cannot be verified against, the served catalog."""

    def __init__(self, report: ModelConsistencyReport) -> None:
        self.report = report
        super().__init__("Explanation model does not match the served catalog: " + "; ".join(report.problems))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recorded_model_sha256(version_dir: Path) -> Optional[str]:
    """The model checksum recorded with an artifact version, or None if the version records none."""
    entry = version_dir / "registry_entry.json"
    try:
        data = json.loads(entry.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    sha = data.get("artifacts", {}).get("model", {}).get("sha256") if isinstance(data, dict) else None
    return sha if isinstance(sha, str) and len(sha) == 64 else None


def _reference_scores(catalog: pd.DataFrame) -> Tuple[Optional[pd.DataFrame], Optional[pd.Series]]:
    """Planets and the served-model scores to compare with: in-sample scores, else the unlabelled planets' scores."""
    rows = catalog
    if "eligible_for_transmission" in rows.columns:
        rows = rows[rows["eligible_for_transmission"] == True]  # noqa: E712 - pandas element-wise comparison
    if "in_sample_priority_score" in rows.columns:
        ref = pd.to_numeric(rows["in_sample_priority_score"], errors="coerce")
    elif "priority_score" in rows.columns:
        # Labelled planets are served an out-of-fold score; every other planet is served the final model's score.
        if "already_observed_jwst" in rows.columns:
            rows = rows[rows["already_observed_jwst"] != True]  # noqa: E712
        ref = pd.to_numeric(rows["priority_score"], errors="coerce")
    else:
        return None, None
    keep = ref.notna()
    return rows[keep], ref[keep]


def check_model_matches_catalog(
    model: _ScoringModel,
    model_path: Path,
    served_version: Optional[str],
    artifacts_dir: Path,
    catalog: pd.DataFrame,
) -> ModelConsistencyReport:
    """Compare the loaded model with the served artifact; see the module docstring."""
    problems: List[str] = []
    model_path = Path(model_path)
    model_version = model_path.parent.name
    model_sha = _sha256(model_path)

    recorded: Optional[str] = None
    if not served_version:
        problems.append("the query engine reports no served artifact version")
    else:
        if model_version != served_version:
            problems.append(f"the model comes from artifact '{model_version}', the catalog from '{served_version}'")
        recorded = recorded_model_sha256(Path(artifacts_dir) / served_version)
        if recorded is None:
            problems.append(f"artifact '{served_version}' records no model checksum (registry_entry.json)")
        elif recorded != model_sha:
            problems.append(f"the model file's SHA-256 {model_sha[:12]}… differs from the recorded {recorded[:12]}…")

    rows, ref = _reference_scores(catalog)
    compared, max_diff = 0, None
    if rows is None or ref is None or rows.empty:
        problems.append("the catalog has no model scores to compare the explanation model with")
    else:
        diff = np.abs(model.predict_priority_scores(rows) - ref.to_numpy(dtype=float))
        compared, max_diff = int(len(diff)), float(np.max(diff))
        n_bad = int((diff >= SCORE_TOLERANCE).sum())
        if n_bad:
            problems.append(
                f"{n_bad} of {compared} planets score differently with the explanation model "
                f"(up to {max_diff:.3g} points)"
            )

    return ModelConsistencyReport(
        served_version=served_version,
        model_path=str(model_path),
        model_version=model_version,
        model_sha256=model_sha,
        recorded_sha256=recorded,
        planets_compared=compared,
        max_score_difference=max_diff,
        problems=tuple(problems),
    )
