#!/usr/bin/env python3
"""Build JWST label *candidates* from the real MAST archive, with ephemeris-based planet assignment.

What this script does
---------------------
1. Fetches every JWST time-series observation from MAST in ONE bulk query
   (``Observations.query_criteria(obs_collection="JWST", dataproduct_type="timeseries")``).
   All JWST transit/eclipse data products are filed as ``timeseries``; the whole table is a few
   thousand rows, so a bulk query is cheaper and more complete than thousands of per-host queries.
2. Fetches transit ephemerides (pl_tranmid, pl_orbper and their uncertainties) for every
   transiting planet from the NASA Exoplanet Archive TAP service (pscomppars, tran_flag = 1).
3. Caches both RAW responses unmodified under ``reports/.mast_cache/`` with a ``.meta.json``
   companion (fetched_at UTC, query, tool versions, row count, SHA-256). The SHA-256 is verified
   on every read; a mismatch aborts the run.
4. Keeps time-series *spectroscopy* modes only (NIRISS/SOSS, NIRSpec BOTS gratings/PRISM,
   NIRCam grism time series, MIRI LRS slitless P750L) and drops short target-acquisition segments.
5. Matches each MAST ``target_name`` to a host star (normalised name, then a coordinate fallback),
   and for every planet of that host predicts whether a transit or a secondary eclipse falls inside
   the observation window ``[t_min, t_max]`` using a linear ephemeris with propagated uncertainty.
6. Writes ``reports/jwst_mast_candidates.csv`` and ``reports/jwst_mast_summary.md`` for HUMAN
   review (``scripts/review_labels.py``). It never writes to ``backend/data/reference/``.

Time systems
------------
MAST ``t_min``/``t_max`` are MJD. ``pl_tranmid`` is BJD_TDB expressed as a Julian Date. Converting
with MJD = JD - 2400000.5 leaves a systematic offset of at most ~10 minutes (barycentric light-travel
time <= ~8.3 min plus TDB-UTC ~69 s). ``--margin-hours`` (default 0.25 h) absorbs that offset and
small unmodelled transit-timing variations. Linear ephemerides do not model TTVs; systems with large
TTVs can still be mis-assigned, which is why every candidate goes to a human reviewer.

Nothing here decides a label. ``match_status`` and ``likely_type`` are triage hints only.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

STSCI_PROGRAM_URL = "https://www.stsci.edu/jwst/science-execution/program-information?id={pid}"
NASA_TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
EPHEMERIS_ADQL = (
    "select pl_name,hostname,ra,dec,pl_orbper,pl_orbpererr1,pl_orbpererr2,"
    "pl_tranmid,pl_tranmiderr1,pl_tranmiderr2,pl_orbeccen,tran_flag "
    "from pscomppars where tran_flag=1"
)
MAST_QUERY = {"obs_collection": "JWST", "dataproduct_type": "timeseries"}

JD_MINUS_MJD = 2400000.5
DEFAULT_MARGIN_HOURS = 0.25
DEFAULT_MIN_WINDOW_HOURS = 0.5
DEFAULT_COORD_RADIUS_ARCSEC = 30.0
ECCENTRIC_LIMIT = 0.1
SIGMA_K = 3.0

MAST_CACHE_STEM = "jwst_timeseries"
EPHEM_CACHE_STEM = "nasa_ephemerides"

MATCH_STATUSES = ("transit_in_window", "eclipse_in_window", "ambiguous", "no_event_in_window")

CANDIDATE_FIELDS = [
    "hostname",
    "target_name",
    "host_match_method",
    "host_match_sep_arcsec",
    "assigned_planet",
    "in_eligible_catalog",
    "proposal_id",
    "obs_id",
    "instrument_name",
    "filters",
    "t_min",
    "t_max",
    "window_hours",
    "transit_epoch",
    "predicted_mid_transit",
    "timing_uncertainty_hours",
    "match_status",
    "match_note",
    "obs_title",
    "title_type",
    "likely_type",
    "stsci_url",
]


class CacheIntegrityError(RuntimeError):
    """Raised when a cached raw response does not match its recorded SHA-256."""


# --------------------------------------------------------------------------------------------
# Raw cache (unmodified bytes + metadata)
# --------------------------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cache_paths(cache_dir: Path, stem: str, ext: str) -> Tuple[Path, Path]:
    return cache_dir / f"{stem}{ext}", cache_dir / f"{stem}.meta.json"


def write_raw_cache(cache_dir: Path, stem: str, ext: str, raw: bytes, meta: Dict[str, Any]) -> Path:
    """Write raw response bytes unmodified plus a metadata file with their SHA-256."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    data_path, meta_path = cache_paths(cache_dir, stem, ext)
    data_path.write_bytes(raw)
    full_meta = dict(meta)
    full_meta["sha256"] = sha256_bytes(raw)
    full_meta["file"] = data_path.name
    meta_path.write_text(json.dumps(full_meta, indent=2, sort_keys=True), encoding="utf-8")
    return data_path


def read_raw_cache(cache_dir: Path, stem: str, ext: str) -> Tuple[bytes, Dict[str, Any]]:
    """Read cached raw bytes and verify them against the SHA-256 in the metadata file."""
    data_path, meta_path = cache_paths(cache_dir, stem, ext)
    if not data_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f"Cache missing: {data_path.name} / {meta_path.name}")
    raw = data_path.read_bytes()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    expected = str(meta.get("sha256", "")).lower()
    actual = sha256_bytes(raw)
    if not expected or expected != actual:
        raise CacheIntegrityError(
            f"SHA-256 mismatch for {data_path.name}: recorded {expected or '<none>'}, actual {actual}. "
            "The cache was modified after it was fetched; delete it and re-run with --force-refresh."
        )
    return raw, meta


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def with_retries(fn: Callable[[], Any], retries: int, backoff_s: float, label: str) -> Any:
    last_err: Optional[BaseException] = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as err:  # network errors from astroquery/requests vary by version
            last_err = err
            if attempt == retries:
                break
            wait = backoff_s * (2 ** (attempt - 1))
            print(f"      [WARN] {label} attempt {attempt}/{retries} failed: {err}. Retrying in {wait:.1f}s")
            time.sleep(wait)
    raise RuntimeError(f"{label} failed after {retries} attempts: {last_err}")


# --------------------------------------------------------------------------------------------
# Fetching (live) with caching
# --------------------------------------------------------------------------------------------


def mast_table_to_frame(table: Any) -> pd.DataFrame:
    """Convert the columns we use to a DataFrame without altering any string value."""
    cols = [
        "proposal_id",
        "obs_id",
        "target_name",
        "instrument_name",
        "filters",
        "t_min",
        "t_max",
        "obs_title",
        "s_ra",
        "s_dec",
    ]
    out: Dict[str, List[Any]] = {}
    n = len(table)
    for c in cols:
        if c not in table.colnames:
            out[c] = [None] * n
            continue
        col = table[c]
        masked = np.ma.getmaskarray(col)
        values: List[Any] = []
        for i in range(n):
            if masked[i]:
                values.append(None)
            else:
                v = col[i]
                values.append(v.item() if hasattr(v, "item") else v)
        out[c] = values
    return pd.DataFrame(out)


def fetch_jwst_timeseries(
    cache_dir: Path, force_refresh: bool, offline: bool, retries: int = 4, backoff_s: float = 2.0
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Return all JWST time-series observations (raw MAST table) as a DataFrame."""
    from astropy.table import Table

    data_path, _ = cache_paths(cache_dir, MAST_CACHE_STEM, ".ecsv")
    if data_path.exists() and not force_refresh:
        raw, meta = read_raw_cache(cache_dir, MAST_CACHE_STEM, ".ecsv")
        print(f"      Using cached MAST table ({meta.get('row_count')} rows, fetched {meta.get('fetched_at')})")
    else:
        if offline:
            raise FileNotFoundError(f"--offline given but {data_path} does not exist")
        import astroquery
        from astroquery.mast import Observations

        print(f"      Querying MAST live: {MAST_QUERY} ...")
        table = with_retries(lambda: Observations.query_criteria(**MAST_QUERY), retries, backoff_s, "MAST query")
        buf = io.StringIO()
        table.write(buf, format="ascii.ecsv")
        meta = {
            "source": "MAST Observations.query_criteria",
            "query": MAST_QUERY,
            "fetched_at": utc_now_iso(),
            "astroquery_version": astroquery.__version__,
            "row_count": len(table),
        }
        write_raw_cache(cache_dir, MAST_CACHE_STEM, ".ecsv", buf.getvalue().encode("utf-8"), meta)
        raw, meta = read_raw_cache(cache_dir, MAST_CACHE_STEM, ".ecsv")
    # astropy treats a multi-line str as table content (a file object is not accepted here)
    table = Table.read(raw.decode("utf-8"), format="ascii.ecsv")
    return mast_table_to_frame(table), meta


def fetch_ephemerides(
    cache_dir: Path,
    force_refresh: bool,
    offline: bool,
    timeout_s: int = 120,
    retries: int = 4,
    backoff_s: float = 2.0,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Return transit ephemerides of all transiting planets from NASA TAP (raw CSV cached)."""
    data_path, _ = cache_paths(cache_dir, EPHEM_CACHE_STEM, ".csv")
    if data_path.exists() and not force_refresh:
        raw, meta = read_raw_cache(cache_dir, EPHEM_CACHE_STEM, ".csv")
        print(f"      Using cached ephemerides ({meta.get('row_count')} rows, fetched {meta.get('fetched_at')})")
    else:
        if offline:
            raise FileNotFoundError(f"--offline given but {data_path} does not exist")
        import requests

        print("      Querying NASA Exoplanet Archive TAP for transit ephemerides ...")

        def _get() -> bytes:
            resp = requests.get(NASA_TAP_URL, params={"query": EPHEMERIS_ADQL, "format": "csv"}, timeout=timeout_s)
            resp.raise_for_status()
            return resp.content

        fetched: bytes = with_retries(_get, retries, backoff_s, "NASA TAP query")
        meta = {
            "source": "NASA Exoplanet Archive TAP (pscomppars)",
            "url": NASA_TAP_URL,
            "query": EPHEMERIS_ADQL,
            "fetched_at": utc_now_iso(),
            "row_count": len(pd.read_csv(io.BytesIO(fetched))),
        }
        write_raw_cache(cache_dir, EPHEM_CACHE_STEM, ".csv", fetched, meta)
        raw, meta = read_raw_cache(cache_dir, EPHEM_CACHE_STEM, ".csv")
    return pd.read_csv(io.BytesIO(raw)), meta


# --------------------------------------------------------------------------------------------
# Filtering and classification
# --------------------------------------------------------------------------------------------


def is_time_series_spectroscopy(instrument: str, filters: str) -> bool:
    """True for JWST time-series spectroscopy modes used for transit/eclipse work.

    - NIRISS SOSS (GR700XD)
    - NIRSpec BOTS (PRISM, G140H/M, G235H/M, G395H/M)
    - NIRCam grism time series (GRISMR/GRISMC)
    - MIRI LRS slitless (P750L). MIRI/SLITLESS rows with other filters are target-acquisition images.
    """
    inst = str(instrument or "").upper().strip()
    flt = str(filters or "").upper().strip()

    if any(k in inst for k in ["IMAGE", "TARGACQ", "CORON", "WFS", "IFU", "MOS"]):
        return False

    if "NIRISS" in inst:
        return "SOSS" in inst or "SOSS" in flt or "GR700XD" in flt or "SUBSTRIP" in flt

    if "NIRSPEC" in inst:
        if "BOTS" in inst or "SLIT" in inst or "PRISM" in flt:
            ts_features = ["PRISM", "G395H", "G140H", "G235H", "G395M", "G140M", "G235M", "BOTS"]
            return any(feat in flt or feat in inst for feat in ts_features)
        return False

    if "NIRCAM" in inst:
        return "GRISM" in inst or "GRISM" in flt

    if "MIRI" in inst:
        return "P750L" in flt

    return False


def classify_likely_type_from_title(title: str) -> str:
    """Keyword classification of a RAW proposal/observation title (a weak hint only).

    Returns phase_curve, eclipse, transmission or unknown.
    """
    if not title or not isinstance(title, str):
        return "unknown"
    t = title.lower()
    if any(k in t for k in ["phase curve", "phase-curve", "full orbit", "full-orbit"]):
        return "phase_curve"
    if any(k in t for k in ["secondary eclipse", "emission", "occultation", "dayside"]):
        return "eclipse"
    if any(k in t for k in ["transmission", "transit", "terminator", "atmosphere", "atmospheric"]):
        return "transmission"
    return "unknown"


def combine_likely_type(match_status: str, title_type: str) -> str:
    """Combine the timing evidence with the title hint. Disagreements are surfaced, never resolved."""
    if match_status == "transit_in_window":
        return "transmission" if title_type in ("transmission", "unknown") else "conflict"
    if match_status == "eclipse_in_window":
        if title_type == "phase_curve":
            return "phase_curve"
        return "eclipse" if title_type in ("eclipse", "unknown") else "conflict"
    if match_status == "ambiguous":
        return "needs_review"
    return "no_event"


# --------------------------------------------------------------------------------------------
# Host matching
# --------------------------------------------------------------------------------------------


def normalize_name(name: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(name or "").upper())


@dataclass
class HostIndex:
    by_norm: Dict[str, str]
    collisions: Dict[str, List[str]]
    names: List[str]
    ra: np.ndarray
    dec: np.ndarray


def build_host_index(ephem: pd.DataFrame) -> HostIndex:
    hosts = ephem.groupby("hostname", sort=True).agg(ra=("ra", "first"), dec=("dec", "first")).reset_index()
    by_norm: Dict[str, str] = {}
    collisions: Dict[str, List[str]] = {}
    for h in hosts["hostname"]:
        key = normalize_name(h)
        if key in by_norm and by_norm[key] != h:
            collisions.setdefault(key, [by_norm[key]]).append(h)
        else:
            by_norm[key] = h
    for key in collisions:
        by_norm.pop(key, None)
    return HostIndex(
        by_norm=by_norm,
        collisions=collisions,
        names=list(hosts["hostname"]),
        ra=hosts["ra"].to_numpy(dtype=float),
        dec=hosts["dec"].to_numpy(dtype=float),
    )


def angular_sep_arcsec(ra1: float, dec1: float, ra2: np.ndarray, dec2: np.ndarray) -> np.ndarray:
    r1, d1, r2, d2 = np.radians(ra1), np.radians(dec1), np.radians(ra2), np.radians(dec2)
    cos_sep = np.sin(d1) * np.sin(d2) + np.cos(d1) * np.cos(d2) * np.cos(r1 - r2)
    return np.degrees(np.arccos(np.clip(cos_sep, -1.0, 1.0))) * 3600.0


def match_host(
    target_name: Any, s_ra: Any, s_dec: Any, index: HostIndex, radius_arcsec: float
) -> Tuple[Optional[str], str, Optional[float]]:
    """Return (hostname, method, separation_arcsec).

    method is one of: name, name_planet_suffix, coordinates, coordinates_ambiguous, none.
    """
    key = normalize_name(target_name)
    if key and key in index.by_norm:
        return index.by_norm[key], "name", None
    if len(key) > 1 and key[-1] in "BCDEFGHIJK" and key[:-1] in index.by_norm:
        return index.by_norm[key[:-1]], "name_planet_suffix", None
    try:
        ra, dec = float(s_ra), float(s_dec)
    except (TypeError, ValueError):
        return None, "none", None
    if math.isnan(ra) or math.isnan(dec) or len(index.names) == 0:
        return None, "none", None
    seps = angular_sep_arcsec(ra, dec, index.ra, index.dec)
    within = np.where(seps <= radius_arcsec)[0]
    if len(within) == 1:
        i = int(within[0])
        return index.names[i], "coordinates", round(float(seps[i]), 2)
    if len(within) > 1:
        return None, "coordinates_ambiguous", None
    return None, "none", None


# --------------------------------------------------------------------------------------------
# Ephemeris prediction
# --------------------------------------------------------------------------------------------


def to_mjd(t: Any) -> float:
    """Convert a JD/BJD value (~2.4e6) to MJD. Values already in the MJD range are returned unchanged."""
    v = float(t)
    if math.isnan(v):
        return v
    if v > 2_000_000:
        return v - JD_MINUS_MJD
    if 40_000 < v < 100_000:
        return v
    raise ValueError(f"Unrecognised time value {t!r}: expected JD (~2.4e6) or MJD (~4e4-1e5)")


def symmetric_err(e1: Any, e2: Any) -> float:
    vals = [abs(float(x)) for x in (e1, e2) if x is not None and not pd.isna(x)]
    return max(vals) if vals else float("nan")


@dataclass
class EventCheck:
    status: str  # yes / maybe / no
    epoch: Optional[int]
    mid_mjd: Optional[float]
    sigma_days: float


_RANK = {"yes": 2, "maybe": 1, "no": 0}


def check_event(
    t_min: float,
    t_max: float,
    t0_mjd: float,
    period: float,
    sigma_t0: float,
    sigma_p: float,
    phase_offset: float,
    margin_days: float,
) -> EventCheck:
    """Strongest evidence of an event (transit: offset 0, eclipse: offset 0.5) inside [t_min, t_max].

    yes   : predicted time +/- (3 sigma + margin) lies entirely inside the window
    maybe : predicted time lies within the window widened by (3 sigma + margin)
    no    : otherwise
    Ties between epochs with the same status go to the epoch closest to the window centre.
    """
    n_lo = math.floor((t_min - t0_mjd) / period - phase_offset) - 1
    n_hi = math.ceil((t_max - t0_mjd) / period - phase_offset) + 1
    centre = 0.5 * (t_min + t_max)
    best = EventCheck("no", None, None, float("nan"))
    for n in range(n_lo, n_hi + 1):
        cycles = n + phase_offset
        tc = t0_mjd + cycles * period
        sigma = math.sqrt(sigma_t0**2 + (cycles * sigma_p) ** 2)
        tol = SIGMA_K * sigma + margin_days
        if t_min + tol <= tc <= t_max - tol:
            status = "yes"
        elif t_min - tol <= tc <= t_max + tol:
            status = "maybe"
        else:
            continue
        if (
            best.mid_mjd is None
            or _RANK[status] > _RANK[best.status]
            or (_RANK[status] == _RANK[best.status] and abs(tc - centre) < abs(best.mid_mjd - centre))
        ):
            best = EventCheck(status, n, tc, sigma)
    return best


def check_phase_range(
    t_min: float,
    t_max: float,
    t0_mjd: float,
    period: float,
    sigma_t0: float,
    sigma_p: float,
    phase_lo: float,
    phase_hi: float,
    margin_days: float,
) -> EventCheck:
    """'maybe' if any time with orbital phase in [phase_lo, phase_hi] overlaps the widened window.

    Used when the event time is not predictable (eccentric orbit with unknown argument of periastron).
    Never returns 'yes': the event's position inside the window is unknown.
    """
    n_lo = math.floor((t_min - t0_mjd) / period - phase_hi) - 1
    n_hi = math.ceil((t_max - t0_mjd) / period - phase_lo) + 1
    for n in range(n_lo, n_hi + 1):
        start = t0_mjd + (n + phase_lo) * period
        end = t0_mjd + (n + phase_hi) * period
        sigma = math.sqrt(sigma_t0**2 + ((n + 0.5 * (phase_lo + phase_hi)) * sigma_p) ** 2)
        tol = SIGMA_K * sigma + margin_days
        if start - tol <= t_max and end + tol >= t_min:
            return EventCheck("maybe", n, None, sigma)
    return EventCheck("no", None, None, float("nan"))


def orbital_phase(t_mjd: float, t0_mjd: float, period: float) -> float:
    """Orbital phase in [0, 1) with phase 0 at mid-transit."""
    return ((t_mjd - t0_mjd) / period) % 1.0


def circular_phase_stats(phases: Sequence[float]) -> Tuple[float, float]:
    """Circular mean and circular standard deviation of phases (both in phase units)."""
    angles = np.asarray(phases, dtype=float) * 2.0 * math.pi
    c, s = float(np.mean(np.cos(angles))), float(np.mean(np.sin(angles)))
    r = max(min(math.hypot(c, s), 1.0), 1e-12)
    mean = (math.atan2(s, c) / (2.0 * math.pi)) % 1.0
    std = math.sqrt(-2.0 * math.log(r)) / (2.0 * math.pi)
    return mean, std


def phase_distance(a: float, b: float) -> float:
    d = abs(a - b) % 1.0
    return min(d, 1.0 - d)


def assign_planet_event(
    t_min: float, t_max: float, planet: Dict[str, Any], margin_hours: float = DEFAULT_MARGIN_HOURS
) -> Dict[str, Any]:
    """Classify one planet's transit/eclipse visibility in one observation window."""
    result: Dict[str, Any] = {
        "transit_epoch": "",
        "predicted_mid_transit": "",
        "timing_uncertainty_hours": "",
        "match_status": "ambiguous",
        "match_note": "",
    }
    try:
        t0 = to_mjd(planet.get("pl_tranmid"))
        period = float(planet.get("pl_orbper"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        result["match_note"] = "no_ephemeris"
        return result
    if math.isnan(t0) or math.isnan(period) or period <= 0:
        result["match_note"] = "no_ephemeris"
        return result

    sigma_t0 = symmetric_err(planet.get("pl_tranmiderr1"), planet.get("pl_tranmiderr2"))
    sigma_p = symmetric_err(planet.get("pl_orbpererr1"), planet.get("pl_orbpererr2"))
    notes: List[str] = []
    uncertainty_known = not (math.isnan(sigma_t0) or math.isnan(sigma_p))
    if not uncertainty_known:
        notes.append("ephemeris_uncertainty_missing")
        sigma_t0 = 0.0 if math.isnan(sigma_t0) else sigma_t0
        sigma_p = 0.0 if math.isnan(sigma_p) else sigma_p

    margin_days = margin_hours / 24.0
    transit = check_event(t_min, t_max, t0, period, sigma_t0, sigma_p, 0.0, margin_days)

    ecc_raw = planet.get("pl_orbeccen")
    ecc = float(ecc_raw) if ecc_raw is not None and not pd.isna(ecc_raw) else float("nan")
    if not math.isnan(ecc) and ecc > ECCENTRIC_LIMIT:
        # Secondary eclipse phase is 0.5 + (2/pi) e cos(w) to first order (Winn 2010, eq. 33).
        # Without a reliable argument of periastron, search the whole physically possible range.
        half_width = min(0.45, (2.0 / math.pi) * ecc)
        eclipse = check_phase_range(
            t_min, t_max, t0, period, sigma_t0, sigma_p, 0.5 - half_width, 0.5 + half_width, margin_days
        )
        if eclipse.status != "no":
            notes.append("eccentric_orbit_eclipse_possible")
    else:
        eclipse = check_event(t_min, t_max, t0, period, sigma_t0, sigma_p, 0.5, margin_days)

    if transit.mid_mjd is not None:
        result["transit_epoch"] = transit.epoch
        result["predicted_mid_transit"] = round(transit.mid_mjd, 6)
        result["timing_uncertainty_hours"] = round(transit.sigma_days * 24.0, 4)
    elif eclipse.mid_mjd is not None:
        result["timing_uncertainty_hours"] = round(eclipse.sigma_days * 24.0, 4)

    relevant_sigma = transit.sigma_days if transit.mid_mjd is not None else eclipse.sigma_days
    stale = not math.isnan(relevant_sigma) and relevant_sigma > period / 4.0

    if stale:
        status = "ambiguous"
        notes.append("ephemeris_stale")
    elif transit.status == "yes" and eclipse.status == "no":
        status = "transit_in_window"
    elif eclipse.status == "yes" and transit.status == "no":
        status = "eclipse_in_window"
    elif transit.status == "no" and eclipse.status == "no":
        status = "no_event_in_window"
    else:
        status = "ambiguous"
        if transit.status == "yes" and eclipse.status == "yes":
            notes.append("window_covers_transit_and_eclipse")
        elif transit.status == "maybe" or (
            eclipse.status == "maybe" and "eccentric_orbit_eclipse_possible" not in notes
        ):
            notes.append("event_near_window_edge")

    if not uncertainty_known and status in ("transit_in_window", "eclipse_in_window"):
        status = "ambiguous"

    result["match_status"] = status
    result["match_note"] = ";".join(notes)
    return result


# --------------------------------------------------------------------------------------------
# Main build
# --------------------------------------------------------------------------------------------


def load_eligible_planets(catalog_path: Optional[Path]) -> Optional[set]:
    """Planet names that are transmission-eligible in our processed catalog (None if unavailable)."""
    candidates: List[Path] = [catalog_path] if catalog_path else []
    active = REPO_ROOT / "backend" / "artifacts" / "active_version.txt"
    if active.exists():
        version = active.read_text(encoding="utf-8").strip()
        candidates.append(REPO_ROOT / "backend" / "artifacts" / version / "planets.parquet")
    candidates.append(REPO_ROOT / "backend" / "data" / "processed" / "processed_exoplanets.csv")
    for p in candidates:
        if p.exists():
            try:
                df = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)
            except Exception as err:  # e.g. a Git LFS pointer instead of the real file
                print(f"      [WARN] Could not read catalog {p}: {err}")
                continue
            if "eligible_for_transmission" in df.columns and "planet_name" in df.columns:
                return set(df.loc[df["eligible_for_transmission"].astype(bool), "planet_name"].astype(str))
    return None


PHASE_CLUSTER_TOL = 0.015
PHASE_CLUSTER_MIN_OBS = 3
PHASE_CLUSTER_MIN_PROPOSALS = 2
CONFIDENT_STATUSES = ("transit_in_window", "eclipse_in_window")


def largest_phase_group(phases: Sequence[float], tol: float) -> List[int]:
    """Indices of the largest set of phases that all lie within +/- tol of their circular mean."""
    best: List[int] = []
    for anchor in phases:
        group = [j for j, p in enumerate(phases) if phase_distance(p, anchor) <= 2 * tol]
        if len(group) <= len(best):
            continue
        mean, _ = circular_phase_stats([phases[j] for j in group])
        group = [j for j in group if phase_distance(phases[j], mean) <= tol]
        if len(group) > len(best):
            best = group
    return best


def flag_phase_clusters(
    kept: List[Dict[str, Any]],
    events: Dict[Tuple[int, str], Dict[str, Any]],
    planets_by_host: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Re-label clustered 'no event' windows as ambiguous (possible ephemeris error). Mutates events."""
    explained = {i for (i, _), ev in events.items() if ev["match_status"] in CONFIDENT_STATUSES}
    by_host: Dict[str, List[int]] = {}
    for i, k in enumerate(kept):
        by_host.setdefault(k["base"]["hostname"], []).append(i)

    found: List[Dict[str, Any]] = []
    for host, idxs in by_host.items():
        clusters: Dict[str, Tuple[List[int], float, float, set]] = {}
        for planet in planets_by_host.get(host, []):
            name = planet["pl_name"]
            try:
                t0 = to_mjd(planet.get("pl_tranmid"))
                period = float(planet.get("pl_orbper"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            if math.isnan(t0) or math.isnan(period) or period <= 0:
                continue
            cand = [i for i in idxs if i not in explained and events[(i, name)]["match_status"] == "no_event_in_window"]
            if len(cand) < PHASE_CLUSTER_MIN_OBS:
                continue
            phases = [orbital_phase(0.5 * (kept[i]["t_min"] + kept[i]["t_max"]), t0, period) for i in cand]
            group = [cand[j] for j in largest_phase_group(phases, PHASE_CLUSTER_TOL)]
            proposals = {kept[i]["base"]["proposal_id"] for i in group}
            if len(group) < PHASE_CLUSTER_MIN_OBS or len(proposals) < PHASE_CLUSTER_MIN_PROPOSALS:
                continue
            mean, std = circular_phase_stats(
                [orbital_phase(0.5 * (kept[i]["t_min"] + kept[i]["t_max"]), t0, period) for i in group]
            )
            clusters[name] = (group, mean, std, proposals)

        # In resonant multi-planet systems, scheduling on one planet's events makes the other planets'
        # phases bunch as well, so a cluster is attributable only if no other planet clusters on the
        # same windows. Non-attributable windows are surfaced once each, at host level.
        periods = {p["pl_name"]: float(p["pl_orbper"]) for p in planets_by_host.get(host, [])}
        for name, (group, mean, std, proposals) in clusters.items():
            gset = set(group)
            shared = any(
                len(gset & set(other[0])) >= 0.5 * min(len(gset), len(other[0]))
                for other_name, other in clusters.items()
                if other_name != name
            )
            attributable = not shared
            if attributable:
                note = f"phase_cluster_{mean:.3f}_n{len(group)}_possible_ephemeris_error"
                for i in group:
                    events[(i, name)]["match_status"] = "ambiguous"
                    events[(i, name)]["match_note"] = note
            else:
                for i in group:
                    kept[i]["unexplained_cluster"] = True
            found.append(
                {
                    "planet": name,
                    "attributable": attributable,
                    "mean_phase": round(mean, 4),
                    "phase_std": round(std, 4),
                    "n_obs": len(group),
                    "proposals": sorted(proposals),
                    "offset_hours_from_transit": round((mean if mean <= 0.5 else mean - 1.0) * periods[name] * 24.0, 2),
                }
            )
    return found


def build_candidates(
    obs: pd.DataFrame,
    ephem: pd.DataFrame,
    hosts_filter: Optional[Sequence[str]] = None,
    eligible: Optional[set] = None,
    margin_hours: float = DEFAULT_MARGIN_HOURS,
    min_window_hours: float = DEFAULT_MIN_WINDOW_HOURS,
    coord_radius_arcsec: float = DEFAULT_COORD_RADIUS_ARCSEC,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Turn raw MAST rows + ephemerides into candidate rows and run statistics."""
    stats: Dict[str, Any] = {
        "mast_rows": len(obs),
        "dropped_not_tso_spectroscopy": 0,
        "dropped_short_window": 0,
        "dropped_duplicate_obs_id": 0,
        "dropped_missing_times": 0,
        "unmatched_targets": {},
        "host_match_methods": {},
    }
    index = build_host_index(ephem)
    stats["host_name_collisions"] = index.collisions
    planets_by_host: Dict[str, List[Dict[str, Any]]] = {
        str(h): g.sort_values("pl_name").to_dict("records") for h, g in ephem.groupby("hostname")
    }
    wanted = {normalize_name(h) for h in hosts_filter} if hosts_filter else None

    # Pass 1: filter observations and match them to hosts
    kept: List[Dict[str, Any]] = []
    seen_obs: set = set()
    for rec in obs.to_dict("records"):
        if not is_time_series_spectroscopy(rec.get("instrument_name"), rec.get("filters")):
            stats["dropped_not_tso_spectroscopy"] += 1
            continue
        obs_id = str(rec.get("obs_id") or "")
        if obs_id in seen_obs:
            stats["dropped_duplicate_obs_id"] += 1
            continue
        try:
            t_min, t_max = float(rec["t_min"]), float(rec["t_max"])
        except (TypeError, ValueError, KeyError):
            stats["dropped_missing_times"] += 1
            continue
        if math.isnan(t_min) or math.isnan(t_max):
            stats["dropped_missing_times"] += 1
            continue
        window_hours = (t_max - t_min) * 24.0
        if window_hours < min_window_hours:
            stats["dropped_short_window"] += 1
            continue
        seen_obs.add(obs_id)

        host, method, sep = match_host(
            rec.get("target_name"), rec.get("s_ra"), rec.get("s_dec"), index, coord_radius_arcsec
        )
        stats["host_match_methods"][method] = stats["host_match_methods"].get(method, 0) + 1
        if host is None:
            tname = str(rec.get("target_name"))
            stats["unmatched_targets"][tname] = stats["unmatched_targets"].get(tname, 0) + 1
            continue
        if wanted is not None and normalize_name(host) not in wanted:
            continue

        pid = str(rec.get("proposal_id") or "").strip()
        title = rec.get("obs_title") or ""
        kept.append(
            {
                "t_min": t_min,
                "t_max": t_max,
                "base": {
                    "hostname": host,
                    "target_name": rec.get("target_name"),
                    "host_match_method": method,
                    "host_match_sep_arcsec": "" if sep is None else sep,
                    "proposal_id": pid,
                    "obs_id": obs_id,
                    "instrument_name": rec.get("instrument_name"),
                    "filters": rec.get("filters"),
                    "t_min": repr(t_min),
                    "t_max": repr(t_max),
                    "window_hours": round(window_hours, 3),
                    "obs_title": title,
                    "title_type": classify_likely_type_from_title(title),
                    "stsci_url": STSCI_PROGRAM_URL.format(pid=pid) if pid else "",
                },
            }
        )

    # Pass 2: predict events for every (observation, planet of its host)
    events: Dict[Tuple[int, str], Dict[str, Any]] = {}
    for i, k in enumerate(kept):
        for planet in planets_by_host.get(k["base"]["hostname"], []):
            events[(i, planet["pl_name"])] = assign_planet_event(k["t_min"], k["t_max"], planet, margin_hours)

    # Pass 3: phase clusters. Independent programs schedule visits on a planet's events, so several
    # unexplained windows bunching at one orbital phase point to an ephemeris error for that planet.
    stats["phase_clusters"] = flag_phase_clusters(kept, events, planets_by_host)

    # Pass 4: emit rows
    rows: List[Dict[str, Any]] = []
    for i, k in enumerate(kept):
        base = k["base"]
        event_rows = []
        for planet in planets_by_host.get(base["hostname"], []):
            ev = events[(i, planet["pl_name"])]
            if ev["match_status"] == "no_event_in_window":
                continue
            row = dict(base)
            row.update(ev)
            row["assigned_planet"] = planet["pl_name"]
            row["in_eligible_catalog"] = "" if eligible is None else str(planet["pl_name"] in eligible)
            row["likely_type"] = combine_likely_type(ev["match_status"], base["title_type"])
            event_rows.append(row)
        if not event_rows:
            row = dict(base)
            row.update(
                {
                    "assigned_planet": "",
                    "in_eligible_catalog": "",
                    "transit_epoch": "",
                    "predicted_mid_transit": "",
                    "timing_uncertainty_hours": "",
                    "match_status": "no_event_in_window",
                    "match_note": "",
                    "likely_type": "no_event",
                }
            )
            if k.get("unexplained_cluster"):
                row["match_status"] = "ambiguous"
                row["match_note"] = "unexplained_window_phase_clusters_in_multi_planet_system"
                row["likely_type"] = "needs_review"
            event_rows.append(row)
        rows.extend(event_rows)

    rows.sort(
        key=lambda r: (
            MATCH_STATUSES.index(r["match_status"]),
            r["hostname"],
            r["assigned_planet"],
            r["proposal_id"],
            r["obs_id"],
        )
    )
    return rows, stats


def assert_safe_output(path: Path) -> None:
    ref_dir = (REPO_ROOT / "backend" / "data" / "reference").resolve()
    resolved = path.resolve()
    if ref_dir == resolved or ref_dir in resolved.parents:
        raise ValueError(f"Refusing to write into {ref_dir}: reference labels are only written by human review")


def write_candidates_csv(rows: List[Dict[str, Any]], out_path: Path) -> None:
    assert_safe_output(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CANDIDATE_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in CANDIDATE_FIELDS})


def render_summary(
    rows: List[Dict[str, Any]],
    stats: Dict[str, Any],
    mast_meta: Dict[str, Any],
    ephem_meta: Dict[str, Any],
    reference_csv: Optional[Path] = None,
) -> str:
    """Markdown summary. Every number is computed from this run."""
    status_counts = {s: sum(1 for r in rows if r["match_status"] == s) for s in MATCH_STATUSES}
    transit_rows = [r for r in rows if r["match_status"] == "transit_in_window"]
    lines = [
        "# JWST MAST candidate summary",
        "",
        "Generated by `scripts/build_jwst_labels_from_mast.py`. These are review candidates, not labels.",
        "",
        "## Sources",
        "",
        f"- MAST: query `{json.dumps(mast_meta.get('query'))}`, fetched {mast_meta.get('fetched_at')}, "
        f"{mast_meta.get('row_count')} rows, sha256 `{mast_meta.get('sha256')}`",
        f"- NASA Exoplanet Archive: fetched {ephem_meta.get('fetched_at')}, {ephem_meta.get('row_count')} rows, "
        f"sha256 `{ephem_meta.get('sha256')}`",
        "",
        "## Filtering",
        "",
        f"- Raw MAST rows: {stats['mast_rows']}",
        f"- Dropped (not a time-series spectroscopy mode): {stats['dropped_not_tso_spectroscopy']}",
        f"- Dropped (window shorter than minimum, e.g. target acquisition): {stats['dropped_short_window']}",
        f"- Dropped (duplicate obs_id): {stats['dropped_duplicate_obs_id']}",
        f"- Dropped (missing t_min/t_max): {stats['dropped_missing_times']}",
        f"- Host match methods: {json.dumps(stats['host_match_methods'], sort_keys=True)}",
        "",
        "## Candidate rows by match_status",
        "",
        "| match_status | rows |",
        "|:---|---:|",
    ]
    lines += [f"| {s} | {status_counts[s]} |" for s in MATCH_STATUSES]
    lines += [
        "",
        f"Distinct planets with a transit in window: {len({r['assigned_planet'] for r in transit_rows})}  ",
        f"Distinct proposals with a transit in window: {len({r['proposal_id'] for r in transit_rows})}",
        "",
    ]
    if reference_csv is not None and reference_csv.exists():
        ref = pd.read_csv(reference_csv)
        transit_planets = {r["assigned_planet"] for r in transit_rows}
        lines += [
            "## Planets in the existing reference CSV",
            "",
            "| planet | has transit_in_window row |",
            "|:---|:---:|",
        ]
        for p in sorted(ref["planet_name"].astype(str).unique()):
            lines.append(f"| {p} | {'yes' if p in transit_planets else 'no'} |")
        lines.append("")
    clusters = stats.get("phase_clusters") or []
    lines += ["## Phase clusters (possible ephemeris errors)", ""]
    if clusters:
        lines += [
            "Unexplained observations (no confident transit/eclipse of any planet) from several programs",
            "bunch at one orbital phase. Programs schedule visits on events, so for an *attributable* cluster",
            "the archive ephemeris of that planet may be offset. In multi-planet (often resonant) systems",
            "several planets can cluster on the same windows; those clusters are not attributable and the",
            "windows are listed once each at host level. All such rows are `ambiguous`: check the program page.",
            "",
            "| planet | attributable | mean phase | phase std | offset from predicted transit (h) | observations | proposals |",
            "|:---|:---:|---:|---:|---:|---:|:---|",
        ]
        lines += [
            f"| {c['planet']} | {'yes' if c['attributable'] else 'no'} | {c['mean_phase']} | {c['phase_std']} | "
            f"{c['offset_hours_from_transit']} | {c['n_obs']} | {', '.join(c['proposals'])} |"
            for c in clusters
        ]
    else:
        lines.append("None.")
    lines.append("")
    unmatched = sorted(stats["unmatched_targets"].items(), key=lambda kv: (-kv[1], kv[0]))
    lines += ["## MAST targets not matched to a transiting host", ""]
    if unmatched:
        lines += ["| target_name | observations |", "|:---|---:|"]
        lines += [f"| {t} | {c} |" for t, c in unmatched]
    else:
        lines.append("None.")
    if stats.get("host_name_collisions"):
        lines += ["", "## Host-name collisions (excluded from name matching)", ""]
        lines += [f"- `{k}`: {', '.join(v)}" for k, v in stats["host_name_collisions"].items()]
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Build JWST label candidates from MAST with ephemeris matching")
    p.add_argument("--cache-dir", default="reports/.mast_cache")
    p.add_argument("--output", default="reports/jwst_mast_candidates.csv")
    p.add_argument("--summary", default="reports/jwst_mast_summary.md")
    p.add_argument("--reference-csv", default="backend/data/reference/jwst_transmission_targets.csv")
    p.add_argument("--catalog", default=None, help="Processed catalog used only to flag in_eligible_catalog")
    p.add_argument("--hosts", default=None, help="Comma-separated host names to restrict output to")
    p.add_argument("--force-refresh", action="store_true", help="Re-query MAST and NASA TAP, replacing the cache")
    p.add_argument("--offline", action="store_true", help="Fail instead of querying when the cache is missing")
    p.add_argument("--dry-run", action="store_true", help="Compute and print the summary; write no output files")
    p.add_argument("--margin-hours", type=float, default=DEFAULT_MARGIN_HOURS)
    p.add_argument("--min-window-hours", type=float, default=DEFAULT_MIN_WINDOW_HOURS)
    p.add_argument("--coord-radius-arcsec", type=float, default=DEFAULT_COORD_RADIUS_ARCSEC)
    args = p.parse_args(argv)

    cache_dir = REPO_ROOT / args.cache_dir
    out_path = REPO_ROOT / args.output
    summary_path = REPO_ROOT / args.summary
    assert_safe_output(out_path)
    assert_safe_output(summary_path)

    print("[1/4] Loading JWST time-series observations from MAST")
    obs, mast_meta = fetch_jwst_timeseries(cache_dir, args.force_refresh, args.offline)
    print("[2/4] Loading transit ephemerides from NASA Exoplanet Archive")
    ephem, ephem_meta = fetch_ephemerides(cache_dir, args.force_refresh, args.offline)

    print("[3/4] Matching hosts and predicting transit/eclipse windows")
    hosts = [h.strip() for h in args.hosts.split(",")] if args.hosts else None
    eligible = load_eligible_planets(Path(args.catalog) if args.catalog else None)
    rows, stats = build_candidates(
        obs, ephem, hosts, eligible, args.margin_hours, args.min_window_hours, args.coord_radius_arcsec
    )
    summary = render_summary(rows, stats, mast_meta, ephem_meta, REPO_ROOT / args.reference_csv)

    if args.dry_run:
        print("[4/4] --dry-run: not writing files\n")
        print(summary)
        return 0
    print(f"[4/4] Writing {len(rows)} candidate rows to {out_path} and summary to {summary_path}")
    write_candidates_csv(rows, out_path)
    summary_path.write_text(summary, encoding="utf-8")
    print("\nDone. Next: python scripts/check_mast_cache.py, then human review with scripts/review_labels.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
