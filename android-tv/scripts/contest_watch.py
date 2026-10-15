#!/usr/bin/env python3
"""Contest-deadline watch: scan the in-repo queue snapshot for contests
ending within 72 hours and keep ONE persistent local alert file up to date.

Android TV / Termux build. Differences from the systemd version:
- No `gh` CLI on Android: the persistent "issue" is the local file
  alerts/contest-deadlines.md, rewritten each run (same one-place-to-look
  behavior as the GitHub issue).
- Otherwise identical: read-only parse of data/contests-queue-snapshot.md,
  no logins, no LLM. Writes status/contest-deadlines.json.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "data", "contests-queue-snapshot.md")
STATUS_PATH = os.path.join(ROOT, "status", "contest-deadlines.json")
ALERTS_DIR = os.path.join(ROOT, "alerts")
DEADLINES_FILE = os.path.join(ALERTS_DIR, "contest-deadlines.md")
WINDOW = timedelta(hours=72)

DATE_RE = re.compile(r"ends\s+(\d{1,2})/(\d{1,2})/(\d{2,4})")


def parse_date(m, d, y):
    y = int(y)
    if y < 100:
        y += 2000
    return datetime(int(y), int(m), int(d), tzinfo=timezone.utc)


def parse_line(line):
    m = DATE_RE.search(line)
    if not m:
        return None
    fields = [f.strip() for f in line.split("|")]
    name = fields[2] if len(fields) > 2 else line[:80]
    url = next((f for f in fields if f.startswith("http")), "")
    return {"name": name, "url": url,
            "end": parse_date(*m.groups())}


def write_deadlines_file(body):
    """One persistent local file, rewritten each run (replaces the GH issue)."""
    try:
        os.makedirs(ALERTS_DIR, exist_ok=True)
        with open(DEADLINES_FILE, "w") as f:
            f.write(body)
        return DEADLINES_FILE
    except Exception as e:
        return "write-failed: %s" % e


def main():
    now = datetime.now(timezone.utc)
    cutoff = now + WINDOW
    urgent = []
    try:
        with open(QUEUE, encoding="utf-8", errors="replace") as f:
            for line in f:
                p = parse_line(line)
                if p and now <= p["end"] <= cutoff:
                    urgent.append(p)
    except FileNotFoundError:
        pass
    urgent.sort(key=lambda x: x["end"])
    lines = ["- **%s** — ends %s — %s" % (u["name"], u["end"].date(), u["url"])
             for u in urgent]
    body = ("# Contest deadlines (next 72h)\n\n"
            "Auto-generated %s UTC from the queue snapshot. "
            "%d contest(s) end within 72 hours:\n\n" % (
                now.isoformat(timespec="seconds"), len(urgent))
            + ("\n".join(lines) if lines else "_None._")
            + "\n\nEntries must be made by a token-funded agent or a human; "
              "this watcher only reports deadlines.\n")
    file_state = write_deadlines_file(body) if urgent else "none-urgent"
    out = {"checked_at_utc": now.isoformat(timespec="seconds"),
           "window_hours": 72,
           "urgent_count": len(urgent),
           "deadlines_file": file_state,
           "contests": [{"name": u["name"], "url": u["url"],
                         "ends": u["end"].date().isoformat()}
                        for u in urgent]}
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.exit(main())
