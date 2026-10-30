import requests, time, re, csv
from pathlib import Path

csv_path = Path("backend/data/reference/jwst_transmission_targets.csv")
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (ExoSignal JWST Reference Verifier)'
})

print(f"Total rows in csv: {len(rows)}")
unique_pids = set()
for r in rows:
    pid = r.get("program_id", "").strip()
    if pid:
        unique_pids.add(pid)

print(f"Unique program IDs: {len(unique_pids)}: {sorted(list(unique_pids), key=lambda x: int(x) if x.isdigit() else 99999)}")
