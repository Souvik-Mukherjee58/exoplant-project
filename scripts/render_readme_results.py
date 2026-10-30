#!/usr/bin/env python3
"""
render_readme_results.py

Regenerates the benchmark evaluation results table in README.md from evaluation.json
between <!-- RESULTS:START --> and <!-- RESULTS:END --> markers.

Usage:
    python scripts/render_readme_results.py          # Update README.md in-place
    python scripts/render_readme_results.py --check  # Validate freshness in CI (exit 1 if stale)
"""

import argparse
import json
import sys
from pathlib import Path


def find_evaluation_json(workspace_root: Path, json_arg: str = None) -> Path:
    if json_arg:
        path = Path(json_arg)
        if path.exists():
            return path
        raise FileNotFoundError(f"Specified evaluation file not found: {json_arg}")

    artifacts_dir = workspace_root / "backend" / "artifacts"
    active_ptr = artifacts_dir / "active_version.txt"
    if active_ptr.exists():
        version = active_ptr.read_text().strip()
        candidate = artifacts_dir / version / "evaluation.json"
        if candidate.exists():
            return candidate

    fallback = artifacts_dir / "evaluation.json"
    if fallback.exists():
        return fallback

    # Check any subfolder for evaluation.json
    for sub in artifacts_dir.glob("v*/evaluation.json"):
        return sub

    raise FileNotFoundError("Could not locate evaluation.json in backend/artifacts/")


def generate_results_table(eval_data: dict) -> str:
    leaderboard = eval_data.get("leaderboard", [])
    if not leaderboard:
        return "No evaluation benchmark results found in evaluation.json."

    lines = [
        "| Ranker / Model | AP (PR-AUC) [95% CI] | NDCG@25 | Precision@10 | Recall@50 | vs. TSM Baseline |",
        "| :--- | :---: | :---: | :---: | :---: | :--- |",
    ]

    for row in leaderboard:
        name = row.get("model_name", "Unknown")
        is_selected = "Logistic Regression (Variant A" in name
        bold = "**" if is_selected else ""

        ap = row.get("ap", 0.0)
        ap_ci = row.get("ap_ci95", [ap, ap])
        ap_str = f"{bold}{ap:.4f}{bold} [{ap_ci[0]:.4f}, {ap_ci[1]:.4f}]"

        ndcg25 = row.get("ndcg@25", 0.0)
        ndcg_str = f"{bold}{ndcg25:.4f}{bold}"

        p10 = row.get("precision@10", 0.0)
        p10_str = f"{bold}{p10:.4f}{bold}"

        r50 = row.get("recall@50", 0.0)
        r50_str = f"{bold}{r50:.4f}{bold}"

        paired = row.get("paired_vs_tsm_ap", {})
        diff_mean = paired.get("diff_mean", 0.0)
        sign = "+" if diff_mean > 0 else ""

        if "TSM-Only" in name:
            vs_tsm = "baseline (ref)"
        elif paired.get("is_significant", False):
            if diff_mean > 0:
                vs_tsm = f"{bold}{sign}{diff_mean:.4f} (significant){bold}"
            else:
                vs_tsm = f"{sign}{diff_mean:.4f} (underperformed)"
        else:
            vs_tsm = f"{sign}{diff_mean:.4f} (no diff)"

        lines.append(f"| {bold}{name}{bold} | {ap_str} | {ndcg_str} | {p10_str} | {r50_str} | {vs_tsm} |")

    return "\n".join(lines)


def update_readme(readme_path: Path, new_table: str, check_only: bool = False) -> bool:
    if not readme_path.exists():
        raise FileNotFoundError(f"README file not found at {readme_path}")

    content = readme_path.read_text(encoding="utf-8")
    start_tag = "<!-- RESULTS:START -->"
    end_tag = "<!-- RESULTS:END -->"

    if start_tag not in content or end_tag not in content:
        raise ValueError(f"Missing required markers '{start_tag}' and '{end_tag}' in {readme_path}")

    pre, rest = content.split(start_tag, 1)
    current_table, post = rest.split(end_tag, 1)

    expected_block = f"\n{new_table.strip()}\n"
    if current_table == expected_block:
        return True  # Table is already up to date

    if check_only:
        return False  # Stale

    updated_content = f"{pre}{start_tag}{expected_block}{end_tag}{post}"
    readme_path.write_text(updated_content, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(description="Render benchmark evaluation results into README.md")
    parser.add_argument("--check", action="store_true", help="Check if README results are up-to-date without modifying")
    parser.add_argument("--json", type=str, default=None, help="Path to evaluation.json")
    parser.add_argument("--readme", type=str, default=None, help="Path to README.md")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    readme_path = Path(args.readme) if args.readme else workspace_root / "README.md"

    try:
        json_path = find_evaluation_json(workspace_root, args.json)
        with open(json_path, "r", encoding="utf-8") as f:
            eval_data = json.load(f)

        table_md = generate_results_table(eval_data)
        is_fresh = update_readme(readme_path, table_md, check_only=args.check)

        if args.check:
            if is_fresh:
                print(f"[OK] README.md results table is up-to-date with {json_path.name}")
                sys.exit(0)
            else:
                print(
                    f"[FAIL] README.md results table is STALE compared to {json_path.name}!\n"
                    "Run 'python scripts/render_readme_results.py' to synchronize.",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            print(f"[SUCCESS] Updated README.md results table from {json_path}")
            sys.exit(0)

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
