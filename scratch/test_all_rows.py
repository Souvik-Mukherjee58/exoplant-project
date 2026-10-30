import requests, time, re, csv
from pathlib import Path

csv_path = Path("backend/data/reference/jwst_transmission_targets.csv")
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

cache = {}

for r in rows:
    pname = r["planet_name"].strip()
    pid = r["program_id"].strip()
    url = r["source_url"].strip()
    
    # Extract host star name from planet name
    # e.g. "TRAPPIST-1 b" -> "TRAPPIST-1", "L 98-59 b" -> "L 98-59", "55 Cnc e" -> "55 Cnc"
    host_star = re.sub(r"\s+[a-z]$", "", pname, flags=re.I).strip()
    
    if not pid or not url.startswith("http"):
        print(f"Row {pname}: No valid URL/PID -> needs review")
        continue
        
    if pid not in cache:
        time.sleep(1.0)
        # Fetch STScI program info
        # Check outer page
        try:
            resp_outer = s.get(url, timeout=15)
            http_ok = (resp_outer.status_code == 200)
        except Exception as e:
            http_ok = False
            resp_outer = None
            
        # Also fetch inner program info page which has Title and metadata
        inner_url = f"https://www.stsci.edu/jwst-program-info/program?program={pid}&pi=1"
        try:
            time.sleep(1.0)
            resp_inner = s.get(inner_url, timeout=15)
            inner_text = resp_inner.text if resp_inner.status_code == 200 else ""
        except Exception:
            inner_text = ""
            
        # Also fetch visits page for target listing
        visits_url = f"https://www.stsci.edu/jwst-program-info/visits/?program={pid}"
        try:
            time.sleep(1.0)
            resp_vis = s.get(visits_url, timeout=15)
            visits_text = resp_vis.text if resp_vis.status_code == 200 else ""
        except Exception:
            visits_text = ""
            
        # Parse title
        m = re.search(r'<b>Title:</b>\s*(.*?)(?:<br|</b>|</p)', inner_text, re.DOTALL | re.IGNORECASE)
        title = m.group(1).strip() if m else ""
        title = re.sub(r'<[^>]+>', '', title).strip()
        
        combined_text = (resp_outer.text if resp_outer else "") + " " + inner_text + " " + visits_text
        cache[pid] = {
            "http_ok": http_ok,
            "title": title,
            "combined_text": combined_text
        }
    
    cached = cache[pid]
    # Check if host star is found
    # Normalize host star for matching (e.g. check "TRAPPIST-1", "L 98-59", "L98-59", "55 Cnc")
    host_clean = host_star.lower()
    host_no_space = host_clean.replace(" ", "").replace("-", "")
    text_clean = cached["combined_text"].lower()
    text_no_space = text_clean.replace(" ", "").replace("-", "")
    
    host_found = (host_clean in text_clean) or (host_no_space in text_no_space)
    
    print(f"{pname} (PID {pid}): http_ok={cached['http_ok']}, host_found={host_found}, Title='{cached['title']}'")
