#!/usr/bin/env python3
"""
Empirical Latency and Throughput Benchmark for ExoSignal DuckDB Query Engine.

Executes representative analytical queries over the local Parquet-backed catalog,
measuring exact execution timings, percentiles (P50, P90, P95, P99), and throughput (QPS).

Usage:
    python scripts/bench_query.py [--iterations 200] [--warmup 20] [--json]
"""

import sys
import os
import time
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any
import numpy as np

# Ensure backend directory is in python search path
repo_root = Path(__file__).resolve().parent.parent
backend_dir = repo_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

os.chdir(backend_dir)

# Set UTF-8 encoding for stdout on Windows if needed
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app.services.query_engine import CatalogQueryEngine


BENCHMARK_QUERIES = [
    {
        "name": "Top Priority Targets (Rank Sorted)",
        "sql": "SELECT * FROM planets WHERE priority_rank IS NOT NULL ORDER BY priority_rank ASC LIMIT 20",
        "params": []
    },
    {
        "name": "Substring Search (Name Filter)",
        "sql": "SELECT * FROM planets WHERE lower(planet_name) LIKE '%toi%' LIMIT 20",
        "params": []
    },
    {
        "name": "Habitable Zone Multi-Condition",
        "sql": "SELECT * FROM planets WHERE hz_status = 'Inside HZ' AND eligible_for_transmission = true LIMIT 20",
        "params": []
    },
    {
        "name": "Planetary Radius Slice (0.8 - 1.8 R_Earth)",
        "sql": "SELECT * FROM planets WHERE planet_radius BETWEEN 0.8 AND 1.8 LIMIT 50",
        "params": []
    },
    {
        "name": "Population Group Aggregations",
        "sql": "SELECT hz_status, count(*), avg(target_priority_score), stddev(target_priority_score) FROM planets GROUP BY hz_status",
        "params": []
    }
]


def run_benchmark(iterations: int = 200, warmup: int = 20) -> Dict[str, Any]:
    """Execute empirical latency benchmark over DuckDB query engine."""
    engine = CatalogQueryEngine.get_instance()
    cursor = engine.get_cursor()
    total_records = cursor.execute("SELECT count(*) FROM planets").fetchone()[0]

    # Warmup phase
    for i in range(warmup):
        q = BENCHMARK_QUERIES[i % len(BENCHMARK_QUERIES)]
        cursor.execute(q["sql"], q["params"]).fetchall()

    per_query_results = []
    all_latencies_ms = []

    for q in BENCHMARK_QUERIES:
        q_latencies = []
        for _ in range(iterations):
            start = time.perf_counter()
            cursor.execute(q["sql"], q["params"]).fetchall()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            q_latencies.append(elapsed_ms)
            all_latencies_ms.append(elapsed_ms)

        q_latencies.sort()
        n = len(q_latencies)
        per_query_results.append({
            "name": q["name"],
            "iterations": iterations,
            "min_ms": round(float(q_latencies[0]), 3),
            "max_ms": round(float(q_latencies[-1]), 3),
            "mean_ms": round(float(np.mean(q_latencies)), 3),
            "p50_ms": round(float(np.percentile(q_latencies, 50)), 3),
            "p90_ms": round(float(np.percentile(q_latencies, 90)), 3),
            "p95_ms": round(float(np.percentile(q_latencies, 95)), 3),
            "p99_ms": round(float(np.percentile(q_latencies, 99)), 3)
        })

    all_latencies_ms.sort()
    n_all = len(all_latencies_ms)
    total_elapsed_sec = sum(all_latencies_ms) / 1000.0
    throughput_qps = round(n_all / total_elapsed_sec, 1) if total_elapsed_sec > 0 else 0.0

    return {
        "catalog_version": engine.active_version,
        "catalog_records": total_records,
        "total_queries_executed": n_all,
        "throughput_qps": throughput_qps,
        "overall": {
            "min_ms": round(float(all_latencies_ms[0]), 3),
            "max_ms": round(float(all_latencies_ms[-1]), 3),
            "mean_ms": round(float(np.mean(all_latencies_ms)), 3),
            "p50_ms": round(float(np.percentile(all_latencies_ms, 50)), 3),
            "p90_ms": round(float(np.percentile(all_latencies_ms, 90)), 3),
            "p95_ms": round(float(np.percentile(all_latencies_ms, 95)), 3),
            "p99_ms": round(float(np.percentile(all_latencies_ms, 99)), 3)
        },
        "queries": per_query_results
    }


def main():
    parser = argparse.ArgumentParser(description="Empirical DuckDB Query Latency Benchmark")
    parser.add_argument("--iterations", type=int, default=200, help="Number of iterations per query (default: 200)")
    parser.add_argument("--warmup", type=int, default=20, help="Number of warmup executions (default: 20)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    results = run_benchmark(iterations=args.iterations, warmup=args.warmup)

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print("\n" + "=" * 80)
    print("  ExoSignal DuckDB Empirical Query Engine Benchmark")
    print("=" * 80)
    print(f"Catalog Version : {results['catalog_version']}")
    print(f"Catalog Records : {results['catalog_records']:,} planets")
    print(f"Total Iterations: {results['total_queries_executed']} queries ({args.iterations} per pattern)")
    print(f"Throughput      : {results['throughput_qps']:,.1f} queries/sec")
    print("-" * 80)
    print(f"{'Query Pattern':<38} {'P50 (ms)':>10} {'P95 (ms)':>10} {'P99 (ms)':>10} {'Mean (ms)':>10}")
    print("-" * 80)
    for q in results["queries"]:
        print(f"{q['name']:<38} {q['p50_ms']:>10.3f} {q['p95_ms']:>10.3f} {q['p99_ms']:>10.3f} {q['mean_ms']:>10.3f}")
    print("-" * 80)
    ov = results["overall"]
    print(f"{'OVERALL COMBINED':<38} {ov['p50_ms']:>10.3f} {ov['p95_ms']:>10.3f} {ov['p99_ms']:>10.3f} {ov['mean_ms']:>10.3f}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
