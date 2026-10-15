#!/usr/bin/env python3
"""Referral-pool watch: verify B3NYLG is still listed in public invite-code pools.

Android TV / Termux build. Differences from the systemd version:
- No `gh` CLI on Android: alerts are written as local files under alerts/
  (one ALERT-*.md per pool, plus an appended alerts/alerts.log) instead of
  GitHub issues.
- Otherwise identical logic: read-only, no logins, no LLM.
  Writes status/referral-watch.json.
Alerts fire only after CONSECUTIVE_MISSES misses in a row, to avoid
flapping on one transient fetch failure.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

CODE = "B3NYLG"
CONSECUTIVE_MISSES = 2
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android) mission-keepalive-androidtv/1.0"}

POOLS = {
    "usemuse.lol": "https://usemuse.lol/invite-code",
    "museai-code.com": "https://museai-code.com",
    "landing-page": "https://midnightmichigan.github.io/muse-invite-code/",
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS_PATH = os.path.join(ROOT, "status", "referral-watch.json")
ALERTS_DIR = os.path.join(ROOT, "alerts")
ALERTS_LOG = os.path.join(ALERTS_DIR, "alerts.log")


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except Exception as e:  # network/DNS/TLS failures
        return None, "FETCH_ERROR: %s: %s" % (type(e).__name__, e)


def load_prev():
    try:
        with open(STATUS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def local_alert(title, body):
    """Write a local alert file (no GitHub on this box). Returns the path."""
    try:
        os.makedirs(ALERTS_DIR, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
        path = os.path.join(ALERTS_DIR, "ALERT-%s-%s.md" % (slug, stamp))
        with open(path, "w") as f:
            f.write("# %s\n\n%s\n\nRaised: %s UTC\n" % (
                title, body, datetime.now(timezone.utc).isoformat()))
        with open(ALERTS_LOG, "a") as f:
            f.write("%s UTC | %s | %s\n" % (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                title, path))
        return path
    except Exception as e:
        return "alert-write-failed: %s" % e


def main():
    prev = load_prev()
    prev_pools = prev.get("pools", {})
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = {}
    for name, url in POOLS.items():
        status, body = fetch(url)
        found = bool(status) and CODE in body
        prev_misses = prev_pools.get(name, {}).get("consecutive_misses", 0)
        misses = 0 if found else prev_misses + 1
        results[name] = {
            "url": url,
            "http_status": status,
            "code_found": found,
            "consecutive_misses": misses,
            "note": ("ok" if found
                     else ("fetch_failed" if status is None
                           else "code_not_in_page")),
        }
        if misses == CONSECUTIVE_MISSES:
            title = "code missing from %s" % name
            body_txt = (
                "B3NYLG was not found at %s on %d "
                "consecutive checks (last check %s). "
                "Verify the pool page manually and re-submit the code if "
                "needed. Join link: https://muse.ai/join" % (
                    url, CONSECUTIVE_MISSES, now))
            results[name]["alert"] = local_alert(title, body_txt)

    out = {"checked_at_utc": now, "code": CODE, "pools": results}
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.exit(main())
