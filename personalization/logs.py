"""One JSON object per line on stdout. Splunk (or any log shipper) can index the fields as they are."""
import json
import sys
import time


def log(level: str, msg: str, **fields) -> None:
    sys.stdout.write(json.dumps({"ts": round(time.time(), 3), "level": level, "msg": msg, **fields}) + "\n")
    sys.stdout.flush()
