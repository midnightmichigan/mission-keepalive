#!/usr/bin/env python3
"""Contest-deadline watch: scan the in-repo queue snapshot for contests
ending within 72 hours and keep ONE persistent GitHub issue up to date.

Read-only parse of data/contests-queue-snapshot.md. No logins, no LLM.
Writes status/contest-deadlines.json.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "data", "contests-queue-snapshot.md")
STATUS_PATH = os.path.join(ROOT, "status", "contest-deadlines.json")
ISSUE_TITLE = "Contest deadlines (next 72h)"
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


def find_issue():
    try:
        out = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--search",
             f'in:title "{ISSUE_TITLE}"', "--json", "number"],
            capture_output=True, text=True, timeout=60)
        items = json.loads(out.stdout or "[]")
        return items[0]["number"] if items else None
    except Exception:
        return None


def upsert_issue(body):
    num = find_issue()
    try:
        if num:
            r = subprocess.run(
                ["gh", "issue", "edit", str(num), "--body", body],
                capture_output=True, text=True, timeout=60)
            return f"updated #{num}" if r.returncode == 0 else "update-failed"
        r = subprocess.run(
            ["gh", "issue", "create", "--title", ISSUE_TITLE, "--body", body],
            capture_output=True, text=True, timeout=60)
        return "created" if r.returncode == 0 else "create-failed"
    except Exception as e:
        return f"error: {e}"


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
    lines = [f"- **{u['name']}** — ends {u['end'].date()} — {u['url']}"
             for u in urgent]
    body = (f"Auto-generated {now.isoformat(timespec='seconds')} UTC from the "
            f"queue snapshot. {len(urgent)} contest(s) end within 72 hours:\n\n"
            + ("\n".join(lines) if lines else "_None._")
            + "\n\nEntries must be made by a token-funded agent or a human; "
              "this watcher only reports deadlines.")
    issue_state = upsert_issue(body) if urgent else "none-urgent"
    out = {"checked_at_utc": now.isoformat(timespec="seconds"),
           "window_hours": 72,
           "urgent_count": len(urgent),
           "issue": issue_state,
           "contests": [{"name": u["name"], "url": u["url"],
                         "ends": u["end"].date().isoformat()}
                        for u in urgent]}
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.exit(main())
