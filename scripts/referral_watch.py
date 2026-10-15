#!/usr/bin/env python3
"""Referral-pool watch: verify B3NYLG is still listed in public invite-code pools.

Read-only, no logins, no LLM. Writes status/referral-watch.json.
Alerts (via GitHub issue) only after CONSECUTIVE_MISSES misses in a row,
to avoid flapping on one transient fetch failure.
"""
import http.client
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

CODE = "B3NYLG"
CONSECUTIVE_MISSES = 2
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) mission-keepalive/1.0"}

POOLS = {
    "usemuse.lol": "https://usemuse.lol/invite-code",
    "museai-code.com": "https://museai-code.com",
    "landing-page": "https://midnightmichigan.github.io/muse-invite-code/",
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS_PATH = os.path.join(ROOT, "status", "referral-watch.json")


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except http.client.IncompleteRead as e:
        # Some pools (e.g. museai-code.com) advertise a Content-Length the
        # connection never fully delivers. The partial bytes are usable.
        partial = getattr(e, "partial", b"")
        if partial:
            return 200, partial.decode("utf-8", errors="replace")
        return None, f"FETCH_ERROR: IncompleteRead: {e}"
    except Exception:
        pass  # fall through to curl fallback
    # curl fallback: tolerates servers urllib chokes on
    try:
        out = subprocess.run(
            ["curl", "-sL", "--max-time", "25", "-A",
             "Mozilla/5.0 (X11; Linux x86_64) mission-keepalive/1.0",
             "-o", "-", "-w", "\n%{http_code}", url],
            capture_output=True, text=True, timeout=40)
        body, _, code = out.stdout.rpartition("\n")
        status = int(code.strip()) if code.strip().isdigit() else None
        return status, body
    except Exception as e:  # network/DNS/TLS failures
        return None, f"FETCH_ERROR: {type(e).__name__}: {e}"


def load_prev():
    try:
        with open(STATUS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def gh_issue(title, body):
    """Create an issue if no open issue with the same title exists."""
    try:
        out = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--search",
             f'in:title "{title}"', "--json", "number"],
            capture_output=True, text=True, timeout=60)
        if out.returncode == 0 and json.loads(out.stdout or "[]"):
            return "already-open"
        r = subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", body],
            capture_output=True, text=True, timeout=60)
        return "created" if r.returncode == 0 else f"failed: {r.stderr[:200]}"
    except Exception as e:
        return f"error: {e}"


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
            title = f"ALERT: code missing from {name}"
            body_txt = (
                f"B3NYLG was not found at {url} on {CONSECUTIVE_MISSES} "
                f"consecutive checks (last check {now}). "
                "A human or a token-funded agent should verify the pool "
                "page manually and re-submit the code if needed. "
                "Join link: https://muse.ai/join"
            )
            results[name]["alert"] = gh_issue(title, body_txt)

    out = {"checked_at_utc": now, "code": CODE, "pools": results}
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.exit(main())
