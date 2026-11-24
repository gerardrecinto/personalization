"""Ship the service's JSON logs to a real Splunk over HEC, then find them with a search.

Usage: python scripts/splunk_check.py   (reads logs from `docker compose logs`, needs Splunk on :8088 and :8089)
"""
import json
import subprocess
import sys
import time

import httpx

HEC = "https://localhost:8088/services/collector/event"
MGMT = "https://localhost:8089"
TOKEN = "lab-hec-token"
AUTH = ("admin", "Chang3d!Pass")

raw = subprocess.run(["docker", "compose", "logs", "--no-log-prefix", "api", "worker"], capture_output=True, text=True).stdout
events = []
for line in raw.splitlines():
    try:
        events.append(json.loads(line))
    except ValueError:
        continue
events = [e for e in events if "msg" in e]
if not events:
    sys.exit("no JSON log lines found")

body = "".join(json.dumps({"event": e, "time": e["ts"], "index": "main", "sourcetype": "_json"}) for e in events)
r = httpx.post(HEC, content=body, headers={"Authorization": f"Splunk {TOKEN}"}, verify=False, timeout=30)
r.raise_for_status()
print(f"sent {len(events)} events to Splunk")

query = 'search index=main msg="recommendations served" | stats count, perc95(ms) AS p95_ms'
for _ in range(30):
    job = httpx.post(f"{MGMT}/services/search/jobs", data={"search": query, "exec_mode": "oneshot", "output_mode": "json"},
                     auth=AUTH, verify=False, timeout=60)
    rows = job.json().get("results", [])
    if rows and int(rows[0]["count"]) > 0:
        print("Splunk found recommendation logs:", rows[0])
        sys.exit(0)
    time.sleep(3)
sys.exit("Splunk did not return the indexed events")
