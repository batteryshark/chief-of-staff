"""Read exactly one known Docket item through its existing supported client; no state/credential writes."""
import json
import os
import re
import sys

source, item = sys.argv[1:]
if not os.path.isabs(source) or not re.fullmatch(r"dkt_[A-Za-z0-9]+", item):
    raise SystemExit("Explicit Docket source and known item ID required")
sys.path.insert(0, source)
from docket.client import request
try:
    _, body = request("GET", "/api/v1/items/" + item, timeout=5)
    print(json.dumps(body["item"]))
except Exception:
    raise SystemExit("Known Docket item read unavailable")
