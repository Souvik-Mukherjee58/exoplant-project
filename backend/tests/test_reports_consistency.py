"""Tests asserting strict consistency across serialized reports, metrics JSON, and documentation."""

import json
import re
import subprocess
import sys
from pathlib import Path


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def test_readme_results_table_is_up_to_date():
    """Assert render_readme_results.py --check passes and README table matches evaluation.json."""
    repo_root = get_repo_root()
    script_path = repo_root / "scripts" / "render_readme_results.py"
    assert script_path.exists(), "render_readme_results.py must exist"

    cmd = [sys.executable, str(script_path), "--check"]
    proc = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)

    assert proc.returncode == 0, (
        f"README.md results table is stale according to render_readme_results.py --check:\n{proc.stdout}\n{proc.stderr}"
    )


def test_evaluation_json_matches_evaluation_md():
    """Assert key metrics in evaluation.json match numerical claims in EVALUATION.md."""
    repo_root = get_repo_root()
    active_ptr = repo_root / "backend" / "artifacts" / "active_version.txt"
    assert active_ptr.exists(), "active_version.txt must exist"
    version = active_ptr.read_text().strip()

    eval_json_path = repo_root / "backend" / "artifacts" / version / "evaluation.json"
    eval_md_path = repo_root / "backend" / "artifacts" / version / "EVALUATION.md"

    assert eval_json_path.exists(), f"evaluation.json not found at {eval_json_path}"
    assert eval_md_path.exists(), f"EVALUATION.md not found at {eval_md_path}"

    with open(eval_json_path, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    eval_md_content = eval_md_path.read_text(encoding="utf-8")

    # Find production variant A in leaderboard
    leaderboard = eval_data.get("leaderboard", [])
    prod_model = next((m for m in leaderboard if "Logistic Regression (Variant A" in m.get("model_name", "")), None)
    assert prod_model is not None, "Variant A must exist in evaluation.json leaderboard"

    ap_val = prod_model["ap"]
    ap_str = f"{ap_val:.4f}"

    # Verify that the AP score appears in EVALUATION.md
    assert ap_str in eval_md_content, (
        f"Production AP {ap_str} from evaluation.json must appear in EVALUATION.md"
    )

    # Verify candidate pool size consistency
    n_eligible = eval_data.get("n_eligible", 4643)
    assert str(n_eligible) in eval_md_content, (
        f"Eligible count {n_eligible} must appear in EVALUATION.md"
    )


def test_manifest_population_matches_parquet():
    """Assert manifest.json total_planets and eligible_planets match active Parquet file."""
    repo_root = get_repo_root()
    active_ptr = repo_root / "backend" / "artifacts" / "active_version.txt"
    version = active_ptr.read_text().strip()

    manifest_path = repo_root / "backend" / "artifacts" / version / "manifest.json"
    parquet_path = repo_root / "backend" / "artifacts" / version / "planets.parquet"

    assert manifest_path.exists(), "manifest.json must exist"
    assert parquet_path.exists(), "planets.parquet must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    import pandas as pd
    df = pd.read_parquet(parquet_path)

    total_manifest = manifest.get("total_planets", manifest.get("n_planets"))
    eligible_manifest = manifest.get("eligible_planets", manifest.get("n_eligible"))

    if total_manifest is not None:
        assert len(df) == total_manifest, (
            f"Parquet row count ({len(df)}) does not match manifest total_planets ({total_manifest})"
        )

    if eligible_manifest is not None and "eligible_for_transmission" in df.columns:
        actual_eligible = int((df["eligible_for_transmission"] == True).sum())
        assert actual_eligible == eligible_manifest, (
            f"Parquet eligible count ({actual_eligible}) does not match manifest ({eligible_manifest})"
        )


def test_readme_contains_no_unrendered_template_tokens():
    """Assert README.md does not contain broken placeholders or unrendered template tokens."""
    repo_root = get_repo_root()
    readme_path = repo_root / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")

    # Assert no unrendered bracketed template placeholders like {{RESULT}} or [TODO]
    unrendered_patterns = [
        r"\{\{[A-Z_]+\}\}",
        r"<!-- TODO",
    ]
    for pattern in unrendered_patterns:
        match = re.search(pattern, readme_text)
        assert not match, f"Found unrendered token in README.md matching {pattern}: {match.group(0) if match else ''}"


def test_model_selection_md_matches_evaluation_json():
    """Assert all quantitative metrics in MODEL_SELECTION.md match evaluation.json."""
    repo_root = get_repo_root()
    active_ptr = repo_root / "backend" / "artifacts" / "active_version.txt"
    assert active_ptr.exists(), "active_version.txt must exist"
    version = active_ptr.read_text().strip()

    eval_json_path = repo_root / "backend" / "artifacts" / version / "evaluation.json"
    model_sel_path = repo_root / "backend" / "artifacts" / version / "MODEL_SELECTION.md"

    assert eval_json_path.exists(), f"evaluation.json not found at {eval_json_path}"
    assert model_sel_path.exists(), f"MODEL_SELECTION.md not found at {model_sel_path}"

    with open(eval_json_path, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    model_sel_content = model_sel_path.read_text(encoding="utf-8")

    # Assert all leaderboard models' AP, AP std, CI, recall@50, and ndcg@25 appear in MODEL_SELECTION.md
    for m in eval_data.get("leaderboard", []):
        ap_str = f"{m['ap']:.4f}"
        std_str = f"{m['ap_std']:.4f}"
        rec_str = f"{m['recall@50']:.4f}"
        ndcg_str = f"{m['ndcg@25']:.4f}"

        assert ap_str in model_sel_content, f"Model {m['model_name']} AP {ap_str} missing from MODEL_SELECTION.md"
        assert std_str in model_sel_content, f"Model {m['model_name']} std {std_str} missing from MODEL_SELECTION.md"
        assert rec_str in model_sel_content, f"Model {m['model_name']} Recall@50 {rec_str} missing from MODEL_SELECTION.md"
        assert ndcg_str in model_sel_content, f"Model {m['model_name']} NDCG@25 {ndcg_str} missing from MODEL_SELECTION.md"

    # Assert distinct score count matches
    score_div = eval_data.get("score_diversity", {})
    distinct_scores = score_div.get("distinct_scores_total")
    if distinct_scores is not None:
        assert str(distinct_scores) in model_sel_content, (
            f"distinct_scores_total {distinct_scores} missing from MODEL_SELECTION.md"
        )


def test_distinct_score_count_in_report_equals_parquet():
    """Assert distinct-score count in evaluation.json equals unique priority_score count in served Parquet."""
    repo_root = get_repo_root()
    active_ptr = repo_root / "backend" / "artifacts" / "active_version.txt"
    assert active_ptr.exists(), "active_version.txt must exist"
    version = active_ptr.read_text().strip()

    eval_json_path = repo_root / "backend" / "artifacts" / version / "evaluation.json"
    parquet_path = repo_root / "backend" / "artifacts" / version / "planets.parquet"

    with open(eval_json_path, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    import pandas as pd
    df = pd.read_parquet(parquet_path)
    eligible = df[df["eligible_for_transmission"] == True]

    parquet_distinct_scores = int(eligible["priority_score"].nunique())
    report_distinct_scores = int(eval_data["score_diversity"]["distinct_scores_total"])

    assert parquet_distinct_scores == report_distinct_scores, (
        f"Distinct score count mismatch: Parquet has {parquet_distinct_scores} unique scores, "
        f"while evaluation report states {report_distinct_scores}"
    )


def test_nested_cv_report_matches_evaluation_json():
    """Assert nested cross-validation report matches evaluation.json nested_cv field."""
    repo_root = get_repo_root()
    active_ptr = repo_root / "backend" / "artifacts" / "active_version.txt"
    assert active_ptr.exists(), "active_version.txt must exist"
    version = active_ptr.read_text().strip()

    eval_json_path = repo_root / "backend" / "artifacts" / version / "evaluation.json"
    nested_cv_md_path = repo_root / "reports" / "NESTED_CV.md"

    assert eval_json_path.exists(), f"evaluation.json not found at {eval_json_path}"
    assert nested_cv_md_path.exists(), f"NESTED_CV.md not found at {nested_cv_md_path}"

    with open(eval_json_path, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    nested_data = eval_data.get("nested_cv")
    assert nested_data is not None, "evaluation.json must contain 'nested_cv' field"

    nested_md = nested_cv_md_path.read_text(encoding="utf-8")

    mean_nested_ap_str = f"{nested_data['mean_nested_ap']:.4f}"
    mean_nested_rec50_str = f"{nested_data['mean_nested_recall50']:.4f}"

    assert mean_nested_ap_str in nested_md, (
        f"Mean nested AP {mean_nested_ap_str} missing from NESTED_CV.md"
    )
    assert mean_nested_rec50_str in nested_md, (
        f"Mean nested Recall@50 {mean_nested_rec50_str} missing from NESTED_CV.md"
    )

    for r in nested_data.get("outer_results", []):
        ap_str = f"{r['ap']:.4f}"
        rec_str = f"{r['recall@50']:.4f}"
        assert ap_str in nested_md, f"Fold {r['fold']} AP {ap_str} missing from NESTED_CV.md"
        assert rec_str in nested_md, f"Fold {r['fold']} Recall@50 {rec_str} missing from NESTED_CV.md"
