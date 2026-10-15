#!/usr/bin/env python3
"""Placement-health digest: HTTP-status-check every public URL mentioned in
the in-repo referral-placements snapshot. Records 200 = still live.

Read-only HEAD/GET requests, 1s politeness delay, capped URL count.
No logins, no LLM. Writes status/placement-health.json.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "referral-placements-snapshot.md")
STATUS_PATH = os.path.join(ROOT, "status", "placement-health.json")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) mission-keepalive/1.0"}
MAX_URLS = 150
DELAY = 1.0

URL_RE = re.compile(r"https?://[^\s\)\]\"'<>]+")


def check(url):
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, headers=UA, method=method)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            continue
    return None


def main():
    with open(SRC, encoding="utf-8", errors="replace") as f:
        text = f.read()
    urls = []
    for u in URL_RE.findall(text):
        u = u.rstrip(".,;")
        if u not in urls:
            urls.append(u)
    urls = urls[:MAX_URLS]
    results = []
    for u in urls:
        code = check(u)
        results.append({"url": u, "http_status": code,
                        "live": code == 200})
        time.sleep(DELAY)
    out = {"checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "urls_checked": len(results),
           "live_count": sum(1 for r in results if r["live"]),
           "placements": results}
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"checked {len(results)}, live {out['live_count']}")


if __name__ == "__main__":
    sys.exit(main())
