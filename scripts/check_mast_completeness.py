#!/usr/bin/env python3
"""Owner-run check: does the bulk time-series query miss anything PLAN.md's per-host query would find?

For each host it runs PLAN.md's query (JWST, target-name variants, dataproduct_type timeseries AND spectrum), keeps
the time-series spectroscopy modes, and FAILs if any obs_id is not in the cached bulk table. It proves
completeness only for the hosts it was given, so --all-hosts is needed for the full statement. Needs live MAST.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_jwst_labels_from_mast as builder  # noqa: E402

QueryFn = Callable[[List[str]], pd.DataFrame]


def name_variants(host: str) -> List[str]:
    """PLAN.md: host plus variants like 'WASP-39', 'WASP39', 'WASP 39'."""
    return sorted({host, host.replace("-", ""), host.replace("-", " "), host.replace(" ", ""), host.replace(" ", "-")})


def live_query(names: List[str]) -> pd.DataFrame:
    from astroquery.mast import Observations

    table = Observations.query_criteria(
        obs_collection="JWST", target_name=names, dataproduct_type=["timeseries", "spectrum"]
    )
    return builder.mast_table_to_frame(table)


def missing_from_bulk(bulk: pd.DataFrame, per_host: pd.DataFrame) -> List[str]:
    """obs_ids of time-series spectroscopy rows that the per-host query has and the bulk table lacks."""
    have = {str(v).strip() for v in bulk["obs_id"] if not pd.isna(v)}
    missing: List[str] = []
    for rec in per_host.to_dict("records"):
        oid = "" if pd.isna(rec.get("obs_id")) else str(rec["obs_id"]).strip()
        if builder.is_time_series_spectroscopy(rec.get("instrument_name"), rec.get("filters")) and oid not in have:
            missing.append(oid or "<no obs_id>")
    return sorted(missing)


def run(bulk: pd.DataFrame, hosts: Sequence[str], query: QueryFn, pause_s: float = 0.0) -> int:
    if not hosts:
        print("[FAIL] no hosts given; nothing was checked")
        return 1
    failures = 0
    for host in hosts:
        try:
            missing = missing_from_bulk(bulk, query(name_variants(host)))
        except Exception as err:  # network errors vary; an unchecked host is a failure
            print(f"[FAIL] {host}: query failed ({err}); cannot verify")
            failures += 1
            continue
        if missing:
            failures += 1
            print(
                f"[FAIL] {host}: {len(missing)} observation(s) missing from the bulk query: {', '.join(missing[:10])}"
            )
        else:
            print(f"[PASS] {host}")
        time.sleep(pause_s)
    print(f"COMPLETENESS CHECK: {'FAIL' if failures else 'PASS'} ({len(hosts)} host(s) checked)")
    return 1 if failures else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Check that the bulk MAST query is complete (live, owner-run)")
    p.add_argument("--cache-dir", default="reports/.mast_cache")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--hosts", help="comma-separated host names")
    group.add_argument("--all-hosts", action="store_true", help="every transiting host in the ephemeris cache")
    p.add_argument("--pause", type=float, default=0.5, help="seconds between queries")
    args = p.parse_args(argv)
    cache: Any = builder.REPO_ROOT / args.cache_dir
    bulk, _ = builder.fetch_jwst_timeseries(cache, force_refresh=False, offline=True)
    if args.all_hosts:
        ephem, _ = builder.fetch_ephemerides(cache, force_refresh=False, offline=True)
        hosts = sorted(ephem["hostname"].astype(str).unique())
    else:
        hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
    return run(bulk, hosts, live_query, args.pause)


if __name__ == "__main__":
    sys.exit(main())
