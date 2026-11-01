#!/usr/bin/env python3
"""
render_readme_results.py

Regenerates benchmark tables in README.md from:
1. evaluation.json (between <!-- RESULTS:START --> and <!-- RESULTS:END -->)
2. reports/k6_summary.json (between <!-- LOADTEST:START --> and <!-- LOADTEST:END -->)

Usage:
    python scripts/render_readme_results.py          # Update README.md in-place
    python scripts/render_readme_results.py --check  # Validate freshness in CI (exit 1 if stale)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def find_evaluation_json(workspace_root: Path, json_arg: Optional[str] = None) -> Path:
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


def generate_loadtest_table(workspace_root: Path, summary_arg: Optional[str] = None) -> str:
    summary_path = Path(summary_arg) if summary_arg else workspace_root / "reports" / "k6_summary.json"
    k6_data: Optional[Dict[str, Any]] = None

    if summary_path.exists():
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if "metrics" in loaded:
                    k6_data = loaded
        except Exception:
            pass

    if not k6_data:
        return (
            "| Target Concurrency | Throughput (RPS) | Median Latency ($p_{50}$) | 95th Percentile ($p_{95}$) | 99th Percentile ($p_{99}$) | Error Rate |\n"
            "|:---:|:---:|:---:|:---:|:---:|:---:|\n"
            "| 200 VUs | *[Not yet measured]* | *[Not yet measured]* | *[Not yet measured]* | *[Not yet measured]* | *[Not yet measured]* |"
        )

    metrics = k6_data.get("metrics", {})
    http_reqs = metrics.get("http_reqs", {}).get("values", {})
    duration = metrics.get("http_req_duration", {}).get("values", {})
    failed = metrics.get("http_req_failed", {}).get("values", {})
    vus_max = metrics.get("vus_max", {}).get("values", {}).get("max") or metrics.get("vus", {}).get("values", {}).get("max", 200)

    rps = float(http_reqs.get("rate", 0.0))
    p50 = float(duration.get("med", duration.get("p(50)", 0.0)))
    p95 = float(duration.get("p(95)", 0.0))
    p99 = float(duration.get("p(99)", 0.0))
    error_rate = float(failed.get("rate", 0.0)) * 100.0

    return (
        "| Target Concurrency | Throughput (RPS) | Median Latency ($p_{50}$) | 95th Percentile ($p_{95}$) | 99th Percentile ($p_{99}$) | Error Rate |\n"
        "|:---:|:---:|:---:|:---:|:---:|:---:|\n"
        f"| {vus_max} VUs | {rps:.1f} req/s | {p50:.2f} ms | {p95:.2f} ms | {p99:.2f} ms | {error_rate:.2f}% |"
    )


def update_section(content: str, start_tag: str, end_tag: str, new_block: str) -> str:
    if start_tag not in content or end_tag not in content:
        return content

    pre, rest = content.split(start_tag, 1)
    _, post = rest.split(end_tag, 1)
    return f"{pre}{start_tag}\n{new_block.strip()}\n{end_tag}{post}"


def update_readme(readme_path: Path, results_table: str, loadtest_table: str, check_only: bool = False) -> bool:
    if not readme_path.exists():
        raise FileNotFoundError(f"README file not found at {readme_path}")

    content = readme_path.read_text(encoding="utf-8")

    # Verify presence of markers
    if "<!-- RESULTS:START -->" not in content or "<!-- RESULTS:END -->" not in content:
        raise ValueError(f"Missing required RESULTS markers in {readme_path}")

    new_content = update_section(content, "<!-- RESULTS:START -->", "<!-- RESULTS:END -->", results_table)
    if "<!-- LOADTEST:START -->" in new_content and "<!-- LOADTEST:END -->" in new_content:
        new_content = update_section(new_content, "<!-- LOADTEST:START -->", "<!-- LOADTEST:END -->", loadtest_table)

    is_fresh = (content.strip() == new_content.strip())

    if check_only:
        return is_fresh

    if not is_fresh:
        readme_path.write_text(new_content, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(description="Render benchmark evaluation results into README.md")
    parser.add_argument("--check", action="store_true", help="Check if README results are up-to-date without modifying")
    parser.add_argument("--json", type=str, default=None, help="Path to evaluation.json")
    parser.add_argument("--summary", type=str, default=None, help="Path to k6_summary.json")
    parser.add_argument("--readme", type=str, default=None, help="Path to README.md")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    readme_path = Path(args.readme) if args.readme else workspace_root / "README.md"

    try:
        json_path = find_evaluation_json(workspace_root, args.json)
        with open(json_path, "r", encoding="utf-8") as f:
            eval_data = json.load(f)

        results_table = generate_results_table(eval_data)
        loadtest_table = generate_loadtest_table(workspace_root, args.summary)

        is_fresh = update_readme(readme_path, results_table, loadtest_table, check_only=args.check)

        if args.check:
            if is_fresh:
                print(f"[OK] README.md tables are up-to-date with {json_path.name}")
                sys.exit(0)
            else:
                print(
                    "[FAIL] README.md benchmark or loadtest table is STALE!\n"
                    "Run 'python scripts/render_readme_results.py' to synchronize.",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            print(f"[SUCCESS] Updated README.md tables from {json_path} and load test summary.")
            sys.exit(0)

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
