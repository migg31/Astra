import requests

catalog = requests.get("http://localhost:8000/api/admin/catalog").json()
for e in catalog:
    name = (e.get("name") or "").lower()
    short = (e.get("short") or "").lower()
    if any(k in name or k in short for k in ["cs-25", "cs25", "acns"]):
        print(f"  short={e['short']!r:10s} indexed={e['indexed']} source_root={e['source_root']!r} node_count={e['node_count']} harvest_key={e.get('harvest_key')!r}")
