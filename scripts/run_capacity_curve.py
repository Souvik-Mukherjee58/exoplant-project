#!/usr/bin/env python3
"""Measure a latency-vs-load curve with k6 (open model) and write reports/k6_capacity.json.

    python scripts/run_capacity_curve.py --base-url http://localhost:8000 \
        --rates 25,50,100,200,400 --duration 60s \
        --hardware "e.g. laptop, Ryzen 7 5800H 8C/16T, 16 GB, Windows 11, 2 uvicorn workers" \
        --client-location "same machine as the server"

Runs loadtest/capacity.js once per rate (native k6, or the grafana/k6 Docker image), then merges the
k6 summaries with the run metadata. It refuses to run if the target's rate limit would throttle the test
(start the target with RATE_LIMIT_PER_MINUTE=0 for a capacity run). Numbers are never edited by hand:
render them with scripts/render_loadtest_report.py.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse, urlunparse

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "loadtest" / "capacity.js"


def preflight(base_url: str, max_rate: int) -> Optional[str]:
    """Return an error message if the target would distort the test, else None."""
    try:
        with urllib.request.urlopen(f"{base_url}/api/v1/top-targets?limit=1", timeout=30) as resp:
            limit = resp.headers.get("X-RateLimit-Limit")
    except Exception as err:  # noqa: BLE001 - any failure means we cannot run
        return f"target not reachable: {err}"
    if limit is not None and int(limit) > 0 and int(limit) < max_rate * 60:
        return (
            f"target rate limit is {limit} requests/minute per client, below the planned {max_rate * 60}/minute: "
            "the run would measure the rate limiter. Start the target with RATE_LIMIT_PER_MINUTE=0 "
            "(Fly: `fly secrets set RATE_LIMIT_PER_MINUTE=0`, then restore it after the test)."
        )
    return None


def docker_url(base_url: str) -> str:
    """On Docker Desktop, 'localhost' inside the container is the container: use host.docker.internal."""
    u = urlparse(base_url)
    if u.hostname in ("localhost", "127.0.0.1"):
        netloc = "host.docker.internal" + (f":{u.port}" if u.port else "")
        return urlunparse(u._replace(netloc=netloc))
    return base_url


def k6_command(base_url: str, rate: int, duration: str, summary: Path) -> List[str]:
    env = ["-e", f"RATE={rate}", "-e", f"DURATION={duration}"]
    if shutil.which("k6"):
        return [
            "k6",
            "run",
            "--quiet",
            "-e",
            f"BASE_URL={base_url}",
            *env,
            "--summary-export",
            str(summary),
            str(SCRIPT),
        ]
    if shutil.which("docker"):
        return [
            "docker", "run", "--rm",
            "-v", f"{SCRIPT.parent}:/loadtest",
            "-v", f"{summary.parent}:/out",
            "grafana/k6", "run", "--quiet",
            "-e", f"BASE_URL={docker_url(base_url)}", *env,
            "--summary-export", f"/out/{summary.name}", "/loadtest/capacity.js",
        ]  # fmt: skip
    raise RuntimeError("Neither k6 nor docker is available. Install k6: https://grafana.com/docs/k6/latest/set-up/")


def stage_from_summary(rate: int, data: Dict[str, Any]) -> Dict[str, Any]:
    m = data.get("metrics", {})
    dur = m.get("http_req_duration", {})
    reqs = m.get("http_reqs", {})
    failed = m.get("http_req_failed", {})
    dropped = m.get("dropped_iterations", {})
    return {
        "target_rate_rps": rate,
        "achieved_rps": reqs.get("rate"),
        "requests": reqs.get("count"),
        "error_rate": failed.get("value", failed.get("rate")),
        "dropped_iterations": dropped.get("count", 0),
        "p50_ms": dur.get("med"),
        "p95_ms": dur.get("p(95)"),
        "p99_ms": dur.get("p(99)"),
        "max_ms": dur.get("max"),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--base-url", required=True)
    p.add_argument("--rates", default="25,50,100,200,400")
    p.add_argument("--duration", default="60s")
    p.add_argument("--hardware", required=True, help="server hardware and process config, written into the report")
    p.add_argument(
        "--client-location", required=True, help="where k6 ran, e.g. 'same machine' or 'laptop in Bhubaneswar'"
    )
    p.add_argument("--output", default="reports/k6_capacity.json")
    args = p.parse_args(argv)

    base_url = args.base_url.rstrip("/")
    rates = [int(r) for r in args.rates.split(",") if r.strip()]
    problem = preflight(base_url, max(rates))
    if problem:
        print(f"ABORT: {problem}")
        return 2

    stages: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        for rate in rates:
            summary = Path(tmp) / f"rate_{rate}.json"
            print(f"[k6] {rate} req/s for {args.duration} ...", flush=True)
            subprocess.run(k6_command(base_url, rate, args.duration, summary), check=False)
            if not summary.exists():
                print(f"[k6] no summary for rate {rate}; stopping")
                break
            stage = stage_from_summary(rate, json.loads(summary.read_text(encoding="utf-8")))
            stages.append(stage)
            print(f"      achieved {stage['achieved_rps']} rps, p95 {stage['p95_ms']} ms, errors {stage['error_rate']}")

    out = REPO_ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "kind": "capacity_curve",
                "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "base_url": base_url,
                "duration_per_rate": args.duration,
                "hardware": args.hardware,
                "client_location": args.client_location,
                "script": "loadtest/capacity.js",
                "stages": stages,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {out}. Render with: python scripts/render_loadtest_report.py --capacity {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
