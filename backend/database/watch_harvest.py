import requests, time

for _ in range(120):
    r = requests.get("http://localhost:8000/api/admin/harvester/status").json()
    running = r.get("is_running", False)
    added = r.get("nodes_added", 0)
    updated = r.get("nodes_updated", 0)
    source = r.get("current_source", "-")
    print(f"running={running}  added={added}  updated={updated}  source={source}")
    if not running:
        break
    time.sleep(15)
print("Done.")
