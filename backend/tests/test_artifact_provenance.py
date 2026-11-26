"""The served artifact agrees with its own records and follows from its sources."""

import importlib.util
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from app.ml.model_registry import ModelRegistry

ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = ROOT / "backend" / "artifacts"
VERSION = (ARTIFACTS / "active_version.txt").read_text(encoding="utf-8").strip()


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("reproduce_artifact", ROOT / "scripts" / "reproduce_artifact.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def copy(tmp_path):
    target = tmp_path / VERSION
    shutil.copytree(ARTIFACTS / VERSION, target)
    return target


def test_recorded_checksums_match_the_files(script):
    assert script.check_files(ARTIFACTS / VERSION) == []
    assert ModelRegistry(artifacts_dir=str(ARTIFACTS)).validate_integrity(VERSION)["valid"] is True


def test_the_catalog_follows_from_the_raw_snapshot_the_model_and_the_code(script):
    assert script.check_content(ARTIFACTS / VERSION) == []


@pytest.mark.parametrize("name", ["planets.parquet", "ltr_model.joblib"])
def test_a_changed_file_is_found(script, copy, name):
    (copy / name).write_bytes((copy / name).read_bytes() + b"x")
    assert any(name in p for p in script.check_files(copy))


@pytest.mark.parametrize(
    "column", ["earth_similarity", "oof_priority_score", "priority_rank", "percentile_rank_string", "tsm"]
)
def test_one_changed_value_is_found(script, copy, column):
    df = pd.read_parquet(copy / "planets.parquet")
    row = df.index[df[column].notna()][0]
    df.loc[row, column] = "x" if df[column].dtype == object else df.loc[row, column] + 0.02
    df.to_parquet(copy / "planets.parquet", index=False)
    assert [p for p in script.check_content(copy) if p.startswith(f"{column}:")] == [f"{column}: 1 rows differ"]


def test_a_missing_value_replaced_by_zero_is_found(script, copy):
    df = pd.read_parquet(copy / "planets.parquet")
    df["earth_similarity"] = df["earth_similarity"].fillna(0.0)
    df.to_parquet(copy / "planets.parquet", index=False)
    assert "earth_similarity: 11 rows differ" in script.check_content(copy)


def test_the_record_explains_its_revision_and_names_no_machine():
    entry = json.loads((ARTIFACTS / VERSION / "registry_entry.json").read_text(encoding="utf-8"))
    (revision,) = entry["revisions"]
    assert revision["previous_parquet_sha256"].startswith("054e0aa50451")
    assert "hostname" not in entry["environment"]


def test_an_older_local_index_does_not_override_the_committed_record(copy):
    entry = json.loads((copy / "registry_entry.json").read_text(encoding="utf-8"))
    entry["artifacts"]["parquet"]["sha256"] = entry["revisions"][0]["previous_parquet_sha256"]
    entry["status"] = "production"
    (copy.parent / "registry.json").write_text(
        json.dumps({"versions": {VERSION: entry}, "promotion_history": []}), encoding="utf-8"
    )
    registry = ModelRegistry(artifacts_dir=str(copy.parent))
    assert registry.validate_integrity(VERSION)["valid"] is True
    assert registry.get_version(VERSION)["status"] == "production"  # the status is local
    assert [v["version"] for v in registry.list_versions()] == [VERSION]


def test_a_version_that_only_the_local_index_knows_is_still_found(tmp_path):
    (tmp_path / "registry.json").write_text(
        json.dumps({"versions": {"v0": {"status": "archived"}}, "promotion_history": []}), encoding="utf-8"
    )
    assert ModelRegistry(artifacts_dir=str(tmp_path)).get_version("v0") == {"status": "archived"}


def test_a_changed_byte_with_the_same_size_is_found(script, copy):
    data = bytearray((copy / "planets.parquet").read_bytes())
    data[1000] ^= 1
    (copy / "planets.parquet").write_bytes(bytes(data))
    assert script.check_files(copy) == ["planets.parquet differs from registry_entry.json"]


@pytest.mark.parametrize(
    "keys,problem",
    [
        (("catalog", "parquet_size_bytes"), "planets.parquet differs from manifest.json"),
        (("raw_data", "sha256"), "raw snapshot differs from manifest.json"),
    ],
)
def test_a_wrong_record_in_the_manifest_is_found(script, copy, keys, problem):
    path = copy / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest[keys[0]][keys[1]] = 1 if keys[1] == "parquet_size_bytes" else "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert script.check_files(copy) == [problem]


@pytest.mark.parametrize("field,value", [("sha256", "0" * 64), ("size_bytes", 1)])
def test_a_wrong_record_in_the_registry_entry_is_found(script, copy, field, value):
    path = copy / "registry_entry.json"
    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["artifacts"]["model"][field] = value
    path.write_text(json.dumps(entry), encoding="utf-8")
    assert script.check_files(copy) == ["ltr_model.joblib differs from registry_entry.json"]
