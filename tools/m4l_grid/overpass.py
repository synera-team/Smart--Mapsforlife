"""Tiny Overpass client with on-disk cache and polite retries (used only by the offline grid builder)."""
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
USER_AGENT = "Xanh24-M4L-grid-builder/1.0 (Xanh24 Maps for Life; offline data build)"
CACHE_DIR = os.environ.get("M4L_OSM_CACHE", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache"))


def query(ql, tries=6, label="", cache_only=False):
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = hashlib.sha256(ql.encode()).hexdigest()[:24]
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    if cache_only:
        raise LookupError(label)
    body = urllib.parse.urlencode({"data": ql}).encode()
    for attempt in range(tries):
        req = urllib.request.Request(ENDPOINT, data=body, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                raw = r.read()
            data = json.loads(raw)
            if data.get("remark", "").startswith(("runtime error", "Query timed out")):
                raise RuntimeError(data["remark"])
            with open(path, "wb") as f:
                f.write(raw)
            return data
        except (urllib.error.URLError, RuntimeError, ValueError, TimeoutError) as exc:
            wait = 15 * (attempt + 1)
            print(f"    ! overpass {label} lần {attempt + 1}: {exc} — chờ {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Overpass thất bại: {label}")
