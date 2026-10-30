#!/usr/bin/env python3
"""JWST Reference Catalog Verification & Audit Script.

Fetches STScI program-information pages for all entries in
backend/data/reference/jwst_transmission_targets.csv to audit:
(a) HTTP availability (page loads),
(b) Host star presence on program/visit pages,
(c) Exact published program title,
(d) Objective observation type classification:
    - transmission: title explicitly mentions 'transmission' or 'transit spectroscopy'
    - emission: title explicitly mentions 'emission' or 'eclipse'
    - phase_curve: title explicitly mentions 'phase curve'
    - unknown: anything else (no guessing)
(e) Manual review flags (needs_review = True for anything non-transmission or unconfirmed).

Outputs:
- reports/jwst_reference_verification.csv
- Updates backend/data/reference/jwst_transmission_targets.csv with observation_type and verified (default False).
- Prints a clean Markdown/terminal checklist of every row needing manual inspection with URLs.
"""

import csv
import re
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Canonical host star synonyms / aliases to ensure robust detection
HOST_ALIASES = {
    "55 Cnc": ["55 Cnc", "55 Cancri", "Cancri"],
    "L 98-59": ["L 98-59", "L98-59", "TOI-175", "TIC 307210830"],
    "GJ 1214": ["GJ 1214", "GJ1214", "Gliese 1214"],
    "GJ 436": ["GJ 436", "GJ436", "Gliese 436"],
    "GJ 3470": ["GJ 3470", "GJ3470", "Gliese 3470"],
    "GJ 1132": ["GJ 1132", "GJ1132", "Gliese 1132"],
    "GJ 367": ["GJ 367", "GJ367", "Gliese 367"],
    "HD 209458": ["HD 209458", "HD209458"],
    "HD 189733": ["HD 189733", "HD189733"],
    "LHS 1140": ["LHS 1140", "LHS1140"],
    "LP 791-18": ["LP 791-18", "LP791-18"],
}


def create_resilient_session() -> requests.Session:
    """Create a requests session with retries, backoff, and browser User-Agent."""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36 (ExoSignal Reference Verifier)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    })
    return session


def extract_host_name(planet_name: str) -> str:
    """Extract host star name from planet designation (e.g. 'TRAPPIST-1 e' -> 'TRAPPIST-1')."""
    return re.sub(r"\s+[a-z]$", "", planet_name.strip(), flags=re.IGNORECASE).strip()


def classify_observation_type(program_title: str) -> str:
    """
    Classify observation type strictly from the published STScI program title:
    - transmission: explicitly mentions 'transmission' or 'transit spectroscopy'
    - emission: explicitly mentions 'emission' or 'eclipse'
    - phase_curve: explicitly mentions 'phase curve' or 'phase-curve'
    - unknown: anything else. NO GUESSING.
    """
    if not program_title or not program_title.strip():
        return "unknown"

    title_lower = program_title.lower()

    # Explicit Phase Curve
    if "phase curve" in title_lower or "phase-curve" in title_lower or "phase curves" in title_lower:
        return "phase_curve"

    # Explicit Emission / Eclipse
    if "emission" in title_lower or "eclipse" in title_lower or "secondary eclipse" in title_lower:
        return "emission"

    # Explicit Transmission / Transit Spectroscopy
    if "transmission" in title_lower or "transit spectroscopy" in title_lower:
        return "transmission"

    # Strict: do not guess. If title only says 'transiting exoplanets' or 'atmosphere', return unknown
    return "unknown"


def fetch_stsci_program_info(
    session: requests.Session,
    program_id: str,
    source_url: str,
    delay: float = 1.0,
    timeout: float = 15.0
) -> Dict[str, Any]:
    """
    Fetch STScI program information page, inner program info page, and visit status page.
    Enforces rate limiting delay and returns status, title, and combined page content.
    """
    result = {
        "http_ok": False,
        "program_title": "",
        "combined_text": "",
        "error": None
    }

    if not source_url or not source_url.startswith("http"):
        result["error"] = "No valid HTTP source_url provided"
        return result

    try:
        # 1. Fetch outer program information page
        time.sleep(delay)
        resp_outer = session.get(source_url, timeout=timeout)
        result["http_ok"] = (resp_outer.status_code == 200)

        outer_text = resp_outer.text if resp_outer.status_code == 200 else ""
        inner_text = ""
        visits_text = ""

        # 2. If program_id is numeric, fetch inner program metadata and visit pages
        clean_pid = str(program_id).strip()
        if clean_pid and clean_pid.isdigit():
            # STScI inner program metadata page
            inner_url = f"https://www.stsci.edu/jwst-program-info/program?program={clean_pid}&pi=1"
            time.sleep(delay)
            try:
                resp_inner = session.get(inner_url, timeout=timeout)
                if resp_inner.status_code == 200:
                    inner_text = resp_inner.text
            except Exception as e_inner:
                result["error"] = f"Inner page fetch error: {e_inner}"

            # STScI visit status page (contains specific target / host star names)
            visits_url = f"https://www.stsci.edu/jwst-program-info/visits/?program={clean_pid}"
            time.sleep(delay)
            try:
                resp_visits = session.get(visits_url, timeout=timeout)
                if resp_visits.status_code == 200:
                    visits_text = resp_visits.text
            except Exception as e_visits:
                pass

        # Parse program title
        # Primary location: <b>Title:</b> in inner program metadata
        title_m = re.search(r"<b>Title:</b>\s*(.*?)(?:<br|</b>|</p)", inner_text, re.DOTALL | re.IGNORECASE)
        if title_m:
            raw_title = title_m.group(1).strip()
            # Clean HTML tags and excessive whitespace
            clean_title = re.sub(r"<[^>]+>", "", raw_title).strip()
            clean_title = re.sub(r"\s+", " ", clean_title)
            result["program_title"] = clean_title
        else:
            # Fallback: check if inner page specifically reports not available
            if "isn't available via this interface" in inner_text:
                result["program_title"] = "Program details not available on STScI web interface"
            else:
                # Check title tag of outer page
                outer_title_m = re.search(r"<title>(.*?)</title>", outer_text, re.IGNORECASE)
                if outer_title_m and "Program Information" not in outer_title_m.group(1):
                    result["program_title"] = outer_title_m.group(1).strip()

        result["combined_text"] = f"{outer_text} {inner_text} {visits_text}"

    except requests.RequestException as e:
        result["http_ok"] = False
        result["error"] = str(e)

    return result


def check_host_in_text(host_name: str, text: str) -> bool:
    """Check case-insensitively whether host star name or known aliases appear in text."""
    if not text:
        return False

    text_lower = text.lower()
    text_compact = re.sub(r"[\s\-_]+", "", text_lower)

    # Check primary name
    h_lower = host_name.lower()
    h_compact = re.sub(r"[\s\-_]+", "", h_lower)
    if h_lower in text_lower or h_compact in text_compact:
        return True

    # Check aliases
    for alias_key, aliases in HOST_ALIASES.items():
        if alias_key.lower() in h_lower or h_lower in alias_key.lower():
            for a in aliases:
                a_lower = a.lower()
                a_compact = re.sub(r"[\s\-_]+", "", a_lower)
                if a_lower in text_lower or a_compact in text_compact:
                    return True

    return False


def verify_jwst_reference(
    reference_csv: Optional[str] = None,
    output_report_csv: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Path, Path]:
    """Execute complete audit over reference catalog rows."""
    base_dir = Path(__file__).resolve().parent.parent

    # Locate input reference CSV
    if reference_csv:
        ref_path = Path(reference_csv)
    else:
        candidates = [
            base_dir / "backend" / "data" / "reference" / "jwst_transmission_targets.csv",
            base_dir / "data" / "reference" / "jwst_transmission_targets.csv",
            Path("backend/data/reference/jwst_transmission_targets.csv")
        ]
        ref_path = next((p for p in candidates if p.exists()), candidates[0])

    if not ref_path.exists():
        raise FileNotFoundError(f"JWST reference CSV not found at {ref_path}")

    # Output report path
    if output_report_csv:
        report_path = Path(output_report_csv)
    else:
        report_path = base_dir / "reports" / "jwst_reference_verification.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing rows
    with open(ref_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    print("=" * 80)
    print("JWST Transmission Reference Verification & Audit Harness")
    print(f"Source CSV : {ref_path}")
    print(f"Total Rows : {len(rows)}")
    print("Rate Limit : 1.0s delay per request (with timeout & 3 retries)")
    print("=" * 80)

    session = create_resilient_session()
    program_cache: Dict[str, Dict[str, Any]] = {}
    verified_rows: List[Dict[str, Any]] = []

    for i, row in enumerate(rows, start=1):
        planet_name = row.get("planet_name", "").strip()
        program_id = row.get("program_id", "").strip()
        source_url = row.get("source_url", "").strip()
        cycle = row.get("cycle", "").strip()
        mode = row.get("mode", "").strip()

        host_name = extract_host_name(planet_name)
        print(f"[{i:02d}/{len(rows):02d}] Checking {planet_name:<16} (PID: {program_id or 'None'})... ", end="", flush=True)

        if not program_id or not source_url.startswith("http"):
            http_ok = False
            host_found = False
            program_title = row.get("source_url", "TODO: Missing URL/Program ID")
            obs_type = "unknown"
            needs_review = True
            print("SKIPPED (Missing PID or URL)")
        else:
            cache_key = f"{program_id}:{source_url}"
            if cache_key not in program_cache:
                program_cache[cache_key] = fetch_stsci_program_info(
                    session=session,
                    program_id=program_id,
                    source_url=source_url,
                    delay=1.0,
                    timeout=15.0
                )

            info = program_cache[cache_key]
            http_ok = info["http_ok"]
            program_title = info["program_title"]
            host_found = check_host_in_text(host_name, info["combined_text"])
            obs_type = classify_observation_type(program_title)

            # Strict needs_review condition:
            # Everything needs review unless HTTP loaded, host star confirmed, and title explicitly confirms transmission
            needs_review = (
                (not http_ok) or
                (not host_found) or
                (obs_type != "transmission") or
                ("not available" in program_title.lower())
            )

            status_str = f"HTTP={'OK' if http_ok else 'FAIL'}, Host={'YES' if host_found else 'NO'}, Type={obs_type}"
            if needs_review:
                status_str += " [NEEDS REVIEW]"
            print(status_str)

        verified_rows.append({
            "planet_name": planet_name,
            "program_id": program_id,
            "cycle": cycle,
            "mode": mode,
            "source_url": source_url,
            "http_ok": http_ok,
            "host_found": host_found,
            "program_title": program_title,
            "observation_type": obs_type,
            "verified": False,  # Default False per user instruction (set manually by user only)
            "needs_review": needs_review
        })

    # 1. Output reports/jwst_reference_verification.csv
    report_cols = [
        "planet_name",
        "program_id",
        "http_ok",
        "host_found",
        "program_title",
        "observation_type",
        "needs_review"
    ]
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=report_cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(verified_rows)

    print(f"\n[+] Saved verification report: {report_path}")

    # 2. Update backend/data/reference/jwst_transmission_targets.csv
    # Add observation_type and verified columns. Do NOT change any program_id.
    updated_fields = ["planet_name", "program_id", "cycle", "mode", "source_url", "observation_type", "verified"]
    with open(ref_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=updated_fields, extrasaction="ignore")
        writer.writeheader()
        for r in verified_rows:
            writer.writerow({
                "planet_name": r["planet_name"],
                "program_id": r["program_id"],
                "cycle": r["cycle"],
                "mode": r["mode"],
                "source_url": r["source_url"],
                "observation_type": r["observation_type"],
                "verified": False  # Must remain False until manually reviewed
            })

    print(f"[+] Updated reference catalog: {ref_path} (added observation_type and verified=False)")

    # 3. Print checklist of every row to check by hand
    print_manual_checklist(verified_rows)

    return verified_rows, report_path, ref_path


def print_manual_checklist(rows: List[Dict[str, Any]]) -> None:
    """Print clean, actionable checklist for user manual review with URLs."""
    print("\n" + "=" * 80)
    print("MANUAL REVIEW CHECKLIST (Rows to Check by Hand)")
    print("=" * 80)
    print("Instructions:")
    print("1. Review each program using the STScI URL.")
    print("2. For confirmed transmission spectroscopy programs, edit:")
    print("   backend/data/reference/jwst_transmission_targets.csv")
    print("   and set: observation_type=transmission, verified=True")
    print("3. Rows marked emission or phase_curve should have verified=False.")
    print("-" * 80)

    for i, r in enumerate(rows, start=1):
        pname = r["planet_name"]
        pid = r["program_id"] or "MISSING"
        url = r["source_url"] or "No URL"
        title = r["program_title"] or "No title retrieved"
        obs = r["observation_type"]
        review = "YES" if r["needs_review"] else "NO"
        host = "Found" if r["host_found"] else "NOT FOUND"

        flag_icon = "[!]" if r["needs_review"] else "[OK]"
        print(f"\n{flag_icon} #{i:02d}. {pname} (Program ID: {pid})")
        print(f"      Title            : {title}")
        print(f"      Host Match       : {host}")
        print(f"      Observation Type : {obs}")
        print(f"      Needs Review     : {review}")
        print(f"      STScI URL        : {url}")

    print("\n" + "=" * 80)
    print("Summary:")
    total = len(rows)
    needs_rev_count = sum(1 for r in rows if r["needs_review"])
    print(f"Total entries      : {total}")
    print(f"Needs manual review: {needs_rev_count} / {total}")
    print(f"Report saved to    : reports/jwst_reference_verification.csv")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    verify_jwst_reference()
