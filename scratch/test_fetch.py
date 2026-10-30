import requests, time, re

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

for pid in [1201, 2589, 1366]:
    time.sleep(1.0)
    outer_url = f'https://www.stsci.edu/jwst/science-execution/program-information?id={pid}'
    r = s.get(outer_url, timeout=15)
    print(f"Program {pid}: outer HTTP status={r.status_code}")
    
    # Check if host name or title is in outer page
    # Look for iframe
    m = re.search(r'piframe\.src\s*=\s*["\']([^"\']+)["\']', r.text)
    inner_url = m.group(1) if m else f"https://www.stsci.edu/jwst-program-info/program?program={pid}&pi=1"
    
    time.sleep(1.0)
    r_inner = s.get(inner_url, timeout=15)
    print(f"Program {pid}: inner HTTP status={r_inner.status_code}")
    
    title_m = re.search(r'<b>Title:</b>\s*(.*?)(?:<br|</b>|</p)', r_inner.text, re.DOTALL | re.IGNORECASE)
    title = title_m.group(1).strip() if title_m else ""
    # Clean tags from title
    title = re.sub(r'<[^>]+>', '', title).strip()
    print(f"Program {pid}: Title = '{title}'")
    
    # Check if host appears in title, inner page, or visits page
    print(f"Host checks: TRAPPIST in inner={ 'TRAPPIST' in r_inner.text }, WASP in inner={ 'WASP' in r_inner.text }")
    
    # Check visits page
    visits_url = f"https://www.stsci.edu/jwst-program-info/visits/?program={pid}"
    time.sleep(1.0)
    r_vis = s.get(visits_url, timeout=15)
    print(f"Program {pid}: visits HTTP status={r_vis.status_code}, TRAPPIST in visits={'TRAPPIST' in r_vis.text}, WASP in visits={'WASP' in r_vis.text}")
    print("-" * 50)
