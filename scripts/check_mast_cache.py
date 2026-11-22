#!/usr/bin/env python3
"""Re-verify the local MAST cache against the LIVE MAST archive.

Picks N random proposal_ids from reports/.mast_cache/jwst_timeseries.ecsv, re-queries MAST for each
and compares row by row (keyed by obs_id):

FAIL  if the cache SHA-256 does not match its .meta.json
FAIL  if every MJD in the cache is a whole number (signature of hand-made data)
FAIL  if a cached obs_id does not exist live for that proposal
FAIL  if obs_title, t_min or t_max of a cached row differ from the live value
WARN  if MAST now has MORE rows for a proposal than the cache (a program that took new data
      since the fetch is not evidence of fabrication; re-run the builder with --force-refresh)

This exists because an AI tool once committed a fabricated "MAST cache". Run it after every fetch.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_jwst_labels_from_mast as builder  # noqa: E402

QueryFn = Callable[[str], pd.DataFrame]
T_TOL_DAYS = 1e-7  # ~9 ms; values are copied verbatim, so any real difference is far larger


def live_query(proposal_id: str) -> pd.DataFrame:
    from astroquery.mast import Observations

    table = Observations.query_criteria(proposal_id=proposal_id, **builder.MAST_QUERY)
    return builder.mast_table_to_frame(table)


def all_whole_number_mjd(frame: pd.DataFrame) -> bool:
    values = pd.to_numeric(pd.concat([frame["t_min"], frame["t_max"]]), errors="coerce").dropna()
    values = values[(values > 40_000) & (values < 100_000)]
    return len(values) > 0 and bool((values == values.round()).all())


def compare_proposal(pid: str, cached: pd.DataFrame, live: pd.DataFrame) -> Tuple[List[str], List[str]]:
    failures: List[str] = []
    warnings: List[str] = []
    live_by_id: Dict[str, Dict[str, Any]] = {str(r["obs_id"]): r for r in live.to_dict("records")}
    for rec in cached.to_dict("records"):
        oid = str(rec["obs_id"])
        lv = live_by_id.get(oid)
        if lv is None:
            failures.append(f"proposal {pid}: cached obs_id {oid} does not exist in live MAST")
            continue
        if (rec.get("obs_title") or "") != (lv.get("obs_title") or ""):
            failures.append(
                f"proposal {pid} obs {oid}: obs_title differs (cache {rec.get('obs_title')!r} vs live {lv.get('obs_title')!r})"
            )
        for col in ("t_min", "t_max"):
            a, b = rec.get(col), lv.get(col)
            try:
                fa, fb = float(a), float(b)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                if a != b:
                    failures.append(f"proposal {pid} obs {oid}: {col} differs ({a!r} vs {b!r})")
                continue
            if math.isnan(fa) and math.isnan(fb):
                continue
            if not abs(fa - fb) <= T_TOL_DAYS:
                failures.append(f"proposal {pid} obs {oid}: {col} differs (cache {fa!r} vs live {fb!r})")
    if len(live) > len(cached):
        warnings.append(
            f"proposal {pid}: live MAST has {len(live)} rows, cache has {len(cached)} (new data since fetch?)"
        )
    elif len(live) < len(cached):
        failures.append(f"proposal {pid}: cache has {len(cached)} rows but live MAST has only {len(live)}")
    return failures, warnings


def run_check(
    cache_dir: Path, n: int, seed: Optional[int], query: QueryFn, proposals: Optional[Sequence[str]] = None
) -> int:
    print("=" * 78)
    print(" MAST cache live re-verification")
    print("=" * 78)
    try:
        frame, meta = builder.fetch_jwst_timeseries(cache_dir, force_refresh=False, offline=True)
    except builder.CacheIntegrityError as err:
        print(f"[FAIL] {err}")
        print("MAST CACHE CHECK: FAIL")
        return 1
    except FileNotFoundError as err:
        print(f"[FAIL] {err}. Run scripts/build_jwst_labels_from_mast.py first.")
        print("MAST CACHE CHECK: FAIL")
        return 1
    print(f"[PASS] SHA-256 matches .meta.json ({meta.get('sha256')})")

    failures: List[str] = []
    warnings: List[str] = []
    if all_whole_number_mjd(frame):
        failures.append("every MJD in the cache is a whole number (fabricated-data signature)")
    else:
        print("[PASS] MJD values are fractional")

    pids = sorted({str(p) for p in frame["proposal_id"].dropna() if str(p).strip()})
    if proposals:
        chosen = [str(p) for p in proposals]
    else:
        if not pids:
            failures.append("cache contains no proposal_ids")
            chosen = []
        else:
            chosen = random.Random(seed).sample(pids, k=min(n, len(pids)))
    print(f"Re-querying live MAST for proposals: {', '.join(chosen)}")
    for pid in chosen:
        cached = frame[frame["proposal_id"].astype(str) == pid]
        try:
            live = query(pid)
        except Exception as err:
            failures.append(f"proposal {pid}: live query failed ({err}); cannot verify")
            continue
        pid_failures, pid_warnings = compare_proposal(pid, cached, live)
        status = "FAIL" if pid_failures else "PASS"
        print(f"[{status}] proposal {pid}: {len(cached)} cached rows, {len(live)} live rows")
        failures += pid_failures
        warnings += pid_warnings

    for msg in warnings:
        print(f"[WARN] {msg}")
    for msg in failures:
        print(f"[FAIL] {msg}")
    print("MAST CACHE CHECK: " + ("FAIL" if failures else "PASS"))
    return 1 if failures else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Re-verify the MAST cache against live MAST")
    p.add_argument("--cache-dir", default="reports/.mast_cache")
    p.add_argument("-n", type=int, default=3, help="number of random proposals to re-query")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--proposals", default=None, help="comma-separated proposal ids instead of random ones")
    args = p.parse_args(argv)
    proposals = [x.strip() for x in args.proposals.split(",")] if args.proposals else None
    return run_check(builder.REPO_ROOT / args.cache_dir, args.n, args.seed, live_query, proposals)


if __name__ == "__main__":
    sys.exit(main())
