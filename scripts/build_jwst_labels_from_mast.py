#!/usr/bin/env python3
"""Build JWST candidate labels from STScI / MAST public program archives.

Systematically queries the Mikulski Archive for Space Telescopes (MAST) via
astroquery.mast for all transmission-eligible transiting exoplanet hosts, filters
time-series spectroscopy observations, and writes reports/jwst_mast_candidates.csv
for human domain review.

Key Requirements:
1. Query astroquery.mast Observations: obs_collection="JWST", dataproduct_type in
   ("timeseries", "spectrum"), querying by host star name with batching, polite rate
   limiting, retries, and disk caching in reports/.mast_cache/.
2. Filter time-series spectroscopy modes: NIRISS SOSS, NIRSpec BOTS/PRISM/G395H,
   NIRCam grism time series, and MIRI LRS slitless.
3. Write reports/jwst_mast_candidates.csv:
   hostname, candidate_planets, proposal_id, instrument, filters, obs_date,
   proposal_title, proposal_url, likely_type.
4. Do NOT write to jwst_transmission_targets.csv. Print a summary: hosts found,
   proposals found, and hosts in our reference CSV with no MAST match.
"""

import argparse
import csv
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from astropy.time import Time
from astroquery.mast import Observations


def sanitize_filename(name: str) -> str:
    """Sanitize a hostname string for safe disk filename usage."""
    return re.sub(r"[^A-Za-z0-9_\-\.]", "_", name.strip())


def is_time_series_spectroscopy(instrument: str, filters: str) -> bool:
    """Check if the observation is in an approved JWST time-series spectroscopy mode.

    Modes checked:
    - NIRISS SOSS (Single Object Slitless Spectroscopy: GR700XD / SUBSTRIP)
    - NIRSpec BOTS/PRISM/G395H (Bright Object Time Series / transiting gratings)
    - NIRCam grism time series (F322W2, F444W with GRISMR/GRISMC)
    - MIRI LRS slitless (P750L / SLITLESS)
    """
    inst = str(instrument).upper().strip()
    flt = str(filters).upper().strip()

    # Reject non-spectroscopic or non-time-series configurations
    if any(k in inst for k in ["IMAGE", "TARGACQ", "CORON", "WFS", "IFU", "MOS"]):
        return False

    # 1. NIRISS SOSS
    if "NIRISS" in inst:
        if "SOSS" in inst or "SOSS" in flt or "GR700XD" in flt or "SUBSTRIP" in flt:
            return True

    # 2. NIRSpec BOTS / PRISM / G395H / G140H / G235H
    if "NIRSPEC" in inst:
        if "BOTS" in inst or "SLIT" in inst or "PRISM" in flt:
            ts_features = [
                "PRISM",
                "G395H",
                "G140H",
                "G235H",
                "G395M",
                "G140M",
                "G235M",
                "BOTS",
            ]
            if any(feat in flt or feat in inst for feat in ts_features):
                return True

    # 3. NIRCam grism time series
    if "NIRCAM" in inst:
        if "GRISM" in inst or "GRISM" in flt:
            return True

    # 4. MIRI LRS slitless
    if "MIRI" in inst:
        if any(feat in inst or feat in flt for feat in ["SLITLESS", "LRS", "P750L"]):
            return True

    return False


def classify_likely_type_from_title(title: str) -> str:
    """Classify astrophysical observation regime strictly from proposal title keywords.

    Categories:
    - phase_curve: full-orbit thermal phase curve measurements
    - eclipse: secondary eclipse / dayside thermal emission measurements
    - transmission: primary transit transmission spectroscopy
    - unknown: generic or non-specific proposal title
    """
    if not title or not isinstance(title, str):
        return "unknown"

    t = title.lower()

    # 1. Phase curves take priority because titles often say "phase curve of transiting planet"
    if any(k in t for k in ["phase curve", "phase-curve", "full orbit", "full-orbit"]):
        return "phase_curve"

    # 2. Secondary eclipse / thermal emission
    if any(k in t for k in ["secondary eclipse", "emission", "occultation", "dayside"]):
        return "eclipse"

    # 3. Transmission spectroscopy
    if any(k in t for k in ["transmission", "transit", "terminator", "atmosphere", "atmospheric"]):
        return "transmission"

    return "unknown"


def format_mjd_date(t_min: Any) -> str:
    """Format MJD timestamp to ISO YYYY-MM-DD date string."""
    if t_min is None or pd.isna(t_min) or str(t_min).strip() in ("", "nan", "None"):
        return ""
    try:
        mjd_val = float(t_min)
        if mjd_val <= 0:
            return ""
        return str(Time(mjd_val, format="mjd").iso).split()[0]
    except Exception:
        return str(t_min).split()[0]


def query_mast_for_host(
    hostname: str,
    cache_dir: Path,
    retries: int = 3,
    delay: float = 0.5,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """Query MAST Observations for a host star with disk caching and retry logic."""
    cache_file = cache_dir / f"{sanitize_filename(hostname)}.json"

    if cache_file.exists() and not force_refresh:
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                if isinstance(cached_data, list):
                    return cached_data
        except Exception:
            pass  # Fallback to query on corrupted cache

    obs_list: List[Dict[str, Any]] = []

    for attempt in range(1, retries + 1):
        try:
            results = Observations.query_criteria(
                target_name=hostname,
                obs_collection="JWST",
                dataproduct_type=["timeseries", "spectrum"],
            )

            if results is not None and len(results) > 0:
                for row in results:
                    obs_dict = {
                        "proposal_id": str(row["proposal_id"]).strip() if "proposal_id" in row.colnames else "",
                        "instrument_name": str(row["instrument_name"]).strip()
                        if "instrument_name" in row.colnames
                        else "",
                        "filters": str(row["filters"]).strip() if "filters" in row.colnames else "",
                        "target_name": str(row["target_name"]).strip() if "target_name" in row.colnames else hostname,
                        "t_min": float(row["t_min"]) if "t_min" in row.colnames and pd.notna(row["t_min"]) else None,
                        "proposal_title": str(row["obs_title"]).strip()
                        if "obs_title" in row.colnames and pd.notna(row["obs_title"])
                        else "",
                    }
                    obs_list.append(obs_dict)
            break
        except Exception as err:
            if attempt == retries:
                # Log final failure
                print(f"      [WARN] MAST query failed for {hostname} after {retries} retries: {err}")
            time.sleep(delay * (2 ** (attempt - 1)))

    # Save to disk cache
    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(obs_list, f, indent=2)

    # Polite rate limit between live network queries
    time.sleep(delay)
    return obs_list


def resolve_catalog_path(candidate_path: Optional[str] = None) -> Path:
    """Locate the processed catalog containing transiting, transmission-eligible planets."""
    if candidate_path:
        p = Path(candidate_path)
        if p.exists():
            return p

    search_paths = [
        Path("backend/data/processed/processed_exoplanets.csv"),
        Path("data/processed/processed_exoplanets.csv"),
        Path("backend/artifacts/v1_2026-10-30/planets.parquet"),
        Path("artifacts/v1_2026-10-30/planets.parquet"),
    ]
    for sp in search_paths:
        if sp.exists():
            return sp

    raise FileNotFoundError("Could not locate processed exoplanet catalog file.")


def load_transmission_eligible_hosts(catalog_path: Path) -> Dict[str, List[str]]:
    """Load all transiting, transmission-eligible planets grouped by host star name."""
    if catalog_path.suffix == ".parquet":
        df = pd.read_parquet(catalog_path)
    else:
        df = pd.read_csv(catalog_path)

    # Filter for transiting and transmission-eligible planets
    is_eligible = df["eligible_for_transmission"] == True if "eligible_for_transmission" in df.columns else True

    disc_meth = (
        df["discovery_method"].astype(str).str.lower()
        if "discovery_method" in df.columns
        else pd.Series("", index=df.index)
    )
    has_transit = disc_meth.str.contains("transit")
    if "transit_depth" in df.columns:
        has_transit = has_transit | (pd.to_numeric(df["transit_depth"], errors="coerce") > 0)

    filtered_df = df[is_eligible & has_transit].copy()

    # Determine hostname
    if "hostname" not in filtered_df.columns:
        if "pl_hostname" in filtered_df.columns:
            filtered_df["hostname"] = filtered_df["pl_hostname"]
        elif "planet_name" in filtered_df.columns:
            filtered_df["hostname"] = filtered_df["planet_name"].astype(str).str.replace(r"\s+[a-z]$", "", regex=True)
        else:
            filtered_df["hostname"] = filtered_df["pl_name"].astype(str).str.replace(r"\s+[a-z]$", "", regex=True)

    name_col = "planet_name" if "planet_name" in filtered_df.columns else "pl_name"

    hosts_map: Dict[str, List[str]] = {}
    for _, row in filtered_df.iterrows():
        h = str(row["hostname"]).strip()
        p = str(row[name_col]).strip()
        if not h:
            continue
        if h not in hosts_map:
            hosts_map[h] = []
        if p not in hosts_map[h]:
            hosts_map[h].append(p)

    for h in hosts_map:
        hosts_map[h].sort()

    return hosts_map


def load_reference_hosts(reference_csv_path: Path) -> Set[str]:
    """Load unique host star names from reference catalog."""
    if not reference_csv_path.exists():
        return set()
    df = pd.read_csv(reference_csv_path)
    if "planet_name" not in df.columns:
        return set()

    hosts: Set[str] = set()
    for pname in df["planet_name"].dropna().astype(str):
        h = re.sub(r"\s+[a-z]$", "", pname.strip())
        if h:
            hosts.add(h)
    return hosts


def process_mast_observations(
    hosts_to_query: Dict[str, List[str]],
    cache_dir: Path,
    delay: float = 0.5,
    force_refresh: bool = False,
) -> Tuple[List[Dict[str, Any]], Set[str], Set[str]]:
    """Query MAST and filter time-series spectroscopy observations for all targets."""
    candidates: List[Dict[str, Any]] = []
    hosts_found: Set[str] = set()
    proposals_found: Set[str] = set()

    # Deduplication tracking per host: (hostname, proposal_id, instrument, filters)
    seen_obs: Set[Tuple[str, str, str, str]] = set()

    total_hosts = len(hosts_to_query)
    for idx, (hostname, planets) in enumerate(hosts_to_query.items(), start=1):
        if idx % 10 == 0 or idx == total_hosts:
            print(f"      Processing host {idx}/{total_hosts}: {hostname}...")

        raw_observations = query_mast_for_host(
            hostname=hostname,
            cache_dir=cache_dir,
            delay=delay,
            force_refresh=force_refresh,
        )

        for obs in raw_observations:
            inst = obs.get("instrument_name", "")
            flt = obs.get("filters", "")

            # Filter time-series spectroscopy modes only
            if not is_time_series_spectroscopy(inst, flt):
                continue

            pid = obs.get("proposal_id", "")
            if not pid or pid == "nan":
                continue

            dedup_key = (hostname, pid, inst, flt)
            if dedup_key in seen_obs:
                continue
            seen_obs.add(dedup_key)

            hosts_found.add(hostname)
            proposals_found.add(pid)

            title = obs.get("proposal_title", "")
            obs_date = format_mjd_date(obs.get("t_min"))
            likely_type = classify_likely_type_from_title(title)
            proposal_url = f"https://www.stsci.edu/jwst/science-execution/program-information?id={pid}"
            candidate_planets_str = "; ".join(planets)

            candidate_row = {
                "hostname": hostname,
                "candidate_planets": candidate_planets_str,
                "proposal_id": pid,
                "instrument": inst,
                "filters": flt,
                "obs_date": obs_date,
                "proposal_title": title,
                "proposal_url": proposal_url,
                "likely_type": likely_type,
            }
            candidates.append(candidate_row)

    return candidates, hosts_found, proposals_found


def main() -> None:
    parser = argparse.ArgumentParser(description="Build JWST candidate labels from MAST public archives")
    parser.add_argument(
        "--catalog",
        type=str,
        default=None,
        help="Path to processed exoplanet catalog",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default="reports/.mast_cache",
        help="Directory to cache MAST API JSON responses",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reports/jwst_mast_candidates.csv",
        help="Destination CSV path for candidate records",
    )
    parser.add_argument(
        "--reference-csv",
        type=str,
        default="backend/data/reference/jwst_transmission_targets.csv",
        help="Path to live reference transmission targets catalog",
    )
    parser.add_argument(
        "--reference-only",
        action="store_true",
        help="Query only host stars present in the reference CSV",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of hosts to query (useful for testing)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.25,
        help="Delay in seconds between live MAST network requests",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass disk cache and query MAST API directly",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    cache_dir = repo_root / args.cache_dir
    out_path = repo_root / args.output
    ref_csv_path = repo_root / args.reference_csv

    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("================================================================================")
    print("ExoSignal JWST MAST Observation Ingestion Harness")
    print(f"Cache Directory : {cache_dir}")
    print(f"Output File     : {out_path}")
    print(f"Reference File  : {ref_csv_path}")
    print("================================================================================")

    # 1. Load catalog & candidate hosts
    catalog_path = resolve_catalog_path(args.catalog)
    print(f"[1/4] Loading transmission-eligible catalog: {catalog_path.name}...")
    eligible_hosts = load_transmission_eligible_hosts(catalog_path)
    ref_hosts = load_reference_hosts(ref_csv_path)

    if args.reference_only:
        hosts_to_query = {h: eligible_hosts.get(h, [f"{h} b"]) for h in ref_hosts}
        print(f"      Filtering to {len(hosts_to_query)} reference catalog hosts.")
    else:
        hosts_to_query = eligible_hosts
        print(f"      Identified {len(hosts_to_query)} transmission-eligible host systems.")

    if args.limit:
        hosts_to_query = dict(list(hosts_to_query.items())[: args.limit])
        print(f"      Restricted to first {len(hosts_to_query)} hosts via --limit.")

    # 2. Query MAST and extract time-series spectroscopy observations
    print(f"[2/4] Querying MAST Observations for {len(hosts_to_query)} host stars...")
    candidates, hosts_found, proposals_found = process_mast_observations(
        hosts_to_query=hosts_to_query,
        cache_dir=cache_dir,
        delay=args.rate_limit,
        force_refresh=args.force_refresh,
    )

    # 3. Write reports/jwst_mast_candidates.csv
    print(f"[3/4] Writing {len(candidates)} candidates to {out_path}...")
    fieldnames = [
        "hostname",
        "candidate_planets",
        "proposal_id",
        "instrument",
        "filters",
        "obs_date",
        "proposal_title",
        "proposal_url",
        "likely_type",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in candidates:
            writer.writerow(row)

    # 4. Summary statistics & mismatch audit (Requirement 4)
    ref_hosts_with_no_match = sorted([h for h in ref_hosts if h not in hosts_found])

    print("\n" + "=" * 80)
    print(" JWST MAST INGESTION AUDIT SUMMARY ".center(80, "="))
    print("=" * 80)
    print(f" Hosts with time-series spectroscopy found: {len(hosts_found)}")
    print(f" Unique JWST proposals found               : {len(proposals_found)}")
    print(f" Total candidate observations compiled    : {len(candidates)}")
    print(f" Reference CSV hosts with no MAST match   : {len(ref_hosts_with_no_match)}")
    if ref_hosts_with_no_match:
        print("\n Reference hosts with no exact MAST target_name match:")
        for h in ref_hosts_with_no_match:
            print(f"   * {h}")
        print(" (Note: In MAST, some targets are indexed by planet name or coordinates)")
    print("=" * 80)
    print(" Invariant Check: jwst_transmission_targets.csv NOT modified (read-only).")
    print("================================================================================\n")


if __name__ == "__main__":
    main()
