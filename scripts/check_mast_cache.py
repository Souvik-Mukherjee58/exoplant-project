#!/usr/bin/env python3
"""Re-verify the local MAST cache against the LIVE MAST archive.

Picks N random proposal_ids from reports/.mast_cache/jwst_timeseries.ecsv, re-queries MAST for each
and compares row by row (keyed by obs_id):

FAIL  if the cache SHA-256 does not match its .meta.json
FAIL  if every MJD in the cache is a whole number (signature of hand-made data)
FAIL  if the row count or the set of obs_ids differs in either direction (PLAN.md Phase 2). New data since the
      fetch is the innocent explanation for extra live rows; re-run the builder with --force-refresh
FAIL  if an obs_id is missing, or repeated on either side
FAIL  if obs_title, t_min or t_max of a cached row differ from the live value
FAIL  if reports/jwst_mast_candidates.csv exists and was built from a different cache or different rows

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


def obs_ids(frame: pd.DataFrame) -> List[str]:
    return ["" if pd.isna(v) else str(v).strip() for v in frame["obs_id"]]


def compare_proposal(pid: str, cached: pd.DataFrame, live: pd.DataFrame) -> Tuple[List[str], List[str]]:
    """Return (failures, warnings). Any difference in rows, ids or values is a failure."""
    failures: List[str] = []
    ids = {"cache": obs_ids(cached), "live MAST": obs_ids(live)}
    for side, values in ids.items():
        if "" in values:
            failures.append(f"proposal {pid}: {values.count('')} row(s) without obs_id in {side}")
        for oid in sorted({v for v in values if v and values.count(v) > 1}):
            failures.append(f"proposal {pid}: obs_id {oid} appears {values.count(oid)} times in {side}")
    if len(cached) != len(live):
        hint = " (new data since the fetch? re-run with --force-refresh)" if len(live) > len(cached) else ""
        failures.append(f"proposal {pid}: row count differs: cache {len(cached)}, live MAST {len(live)}{hint}")
    for oid in sorted(set(ids["cache"]) - set(ids["live MAST"]) - {""}):
        failures.append(f"proposal {pid}: cached obs_id {oid} does not exist in live MAST")
    for oid in sorted(set(ids["live MAST"]) - set(ids["cache"]) - {""}):
        failures.append(f"proposal {pid}: live obs_id {oid} is not in the cache")

    live_by_id: Dict[str, List[Dict[str, Any]]] = {}
    for rec in live.to_dict("records"):
        live_by_id.setdefault(str(rec["obs_id"]).strip(), []).append(rec)
    for rec in cached.to_dict("records"):
        oid = str(rec["obs_id"]).strip()
        for lv in live_by_id.get(oid, []):
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
    return failures, []


def check_candidates(candidates: Path, frame: pd.DataFrame, cache_sha: str) -> List[str]:
    """Every candidate row must come from this cache and from an unchanged row of it."""
    if not candidates.exists():
        return []
    rows = pd.read_csv(candidates, dtype=str, keep_default_na=False)
    if not {"obs_id", "mast_row_sha256", "mast_cache_sha256"} <= set(rows.columns):
        return [f"{candidates.name} has no provenance columns; rebuild it"]
    known = {str(r["obs_id"]).strip(): builder.row_sha256(r) for r in frame.to_dict("records") if r.get("obs_id")}
    failures: List[str] = []
    for rec in rows.to_dict("records"):
        if rec["mast_cache_sha256"] != cache_sha:
            failures.append(f"candidate {rec['obs_id']}: built from another cache")
        elif known.get(rec["obs_id"]) != rec["mast_row_sha256"]:
            failures.append(f"candidate {rec['obs_id']}: its MAST row is not in the cache or has changed")
    return failures


def run_check(
    cache_dir: Path,
    n: int,
    seed: Optional[int],
    query: QueryFn,
    proposals: Optional[Sequence[str]] = None,
    candidates: Optional[Path] = None,
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

    if "" in obs_ids(frame):
        failures.append("the cache contains rows without obs_id")
    if candidates is not None:
        failures += check_candidates(candidates, frame, str(meta.get("sha256", "")))

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
    p.add_argument("--candidates", default="reports/jwst_mast_candidates.csv")
    p.add_argument("--proposals", default=None, help="comma-separated proposal ids instead of random ones")
    args = p.parse_args(argv)
    proposals = [x.strip() for x in args.proposals.split(",")] if args.proposals else None
    return run_check(
        builder.REPO_ROOT / args.cache_dir,
        args.n,
        args.seed,
        live_query,
        proposals,
        builder.REPO_ROOT / args.candidates,
    )


if __name__ == "__main__":
    sys.exit(main())
