"""End-to-end test of the build pipeline and evaluation report schema on a small fixture."""

import json
from pathlib import Path

import pytest

from app.pipeline import build_artifacts


@pytest.fixture
def fixture_raw_csv_path() -> Path:
    csv_path = Path(__file__).parent / "fixtures" / "fixture_raw_archive.csv"
    assert csv_path.exists(), f"Fixture CSV missing at {csv_path}"
    return csv_path


def test_pipeline_fixture_and_evaluation_schema(tmp_path: Path, fixture_raw_csv_path: Path):
    """Run build_artifacts on the curated raw fixture and validate the evaluation report schema."""
    version_tag = "v1_ci_fixture"
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # 1. Execute pipeline
    v_dir = build_artifacts(
        version=version_tag,
        raw_path=str(fixture_raw_csv_path),
        artifacts_dir=artifacts_dir,
    )

    # 2. Assert core output artifacts exist
    assert v_dir.exists(), f"Artifact version directory {v_dir} was not created"
    parquet_path = v_dir / "planets.parquet"
    model_path = v_dir / "ltr_model.joblib"
    manifest_path = v_dir / "manifest.json"
    eval_json_path = v_dir / "evaluation.json"
    pca_path = v_dir / "precomputed_pca.json"
    stats_path = v_dir / "precomputed_stats.json"

    assert parquet_path.exists(), "planets.parquet missing"
    assert model_path.exists(), "ltr_model.joblib missing"
    assert manifest_path.exists(), "manifest.json missing"
    assert eval_json_path.exists(), "evaluation.json missing"
    assert pca_path.exists(), "precomputed_pca.json missing"
    assert stats_path.exists(), "precomputed_stats.json missing"

    # 3. Validate Evaluation Report Schema
    with open(eval_json_path, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    # Required top-level keys in evaluation schema
    required_keys = [
        "evaluation_split",
        "n_positives",
        "n_eligible",
        "leaderboard",
        "primary_protocol",
        "temporal_sanity_check",
    ]
    for key in required_keys:
        assert key in eval_data, f"Required key '{key}' missing from evaluation.json"

    assert isinstance(eval_data["leaderboard"], list), "leaderboard must be a list"
    assert len(eval_data["leaderboard"]) >= 5, (
        f"Expected >= 5 models in leaderboard, got {len(eval_data['leaderboard'])}"
    )

    # Validate schema for every model in the leaderboard
    model_required_fields = ["model_name", "map", "pr_auc"]
    for model_entry in eval_data["leaderboard"]:
        for field in model_required_fields:
            assert field in model_entry, f"Model entry missing field '{field}': {model_entry}"
        assert isinstance(model_entry["map"], (int, float)), f"map must be float: {model_entry['map']}"
        assert isinstance(model_entry["pr_auc"], (int, float)), f"pr_auc must be float: {model_entry['pr_auc']}"

    # 4. Validate Manifest Schema
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    assert manifest_data.get("artifact_version") == version_tag
    assert "catalog" in manifest_data
    assert "models" in manifest_data
    assert "benchmark" in manifest_data
