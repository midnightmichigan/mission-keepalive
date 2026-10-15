#!/usr/bin/env python3
"""sync.py — two-way sync between the box and the GitHub repo. Stdlib only.

COMPLETELY OPTIONAL: runs only if config.local.json contains a
github_token. The token never leaves the box except in the Authorization
header to api.github.com.

PUSH (box -> repo, android-tv-inbox/): new/changed files from drafts/,
pending-approval/, digests/, alerts/, and tasks-out/ (task-request JSONs
for the VM's agents — see VM-WATCHER-SPEC.md). Tracks pushed SHAs in
state/pushed.json so it never re-pushes unchanged files.

PULL (repo -> box, tasks-in/): result JSONs the VM watcher wrote to
android-tv-outbox/ are downloaded into tasks-in/ so the box can see what
its delegated tasks produced. Tracks pulled files in state/pulled.json.
"""
import base64
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.local.json")
PUSHED_PATH = os.path.join(ROOT, "state", "pushed.json")
PULLED_PATH = os.path.join(ROOT, "state", "pulled.json")
SYNC_DIRS = ("drafts", "pending-approval", "digests", "alerts", "tasks-out")
OUTBOX_DIR = os.path.join(ROOT, "tasks-in")
API = "https://api.github.com"


def _config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _api(method, path, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json",
                 "User-Agent": "mission-keepalive-androidtv/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(
                resp.read().decode("utf-8", errors="replace") or "{}")
    except Exception as e:
        # urllib raises HTTPError (with .code) on 4xx/5xx
        code = getattr(e, "code", None)
        return code, {"error": "%s: %s" % (type(e).__name__, e)}


def push_new_files():
    cfg = _config()
    token = cfg.get("github_token")
    repo = cfg.get("github_repo", "midnightmichigan/mission-keepalive")
    if not token:
        return "no github_token configured — staying local"
    try:
        with open(PUSHED_PATH) as f:
            pushed = json.load(f)
    except Exception:
        pushed = {}
    pushed_count, skipped = 0, 0
    for d in SYNC_DIRS:
        srcdir = os.path.join(ROOT, d)
        if not os.path.isdir(srcdir):
            continue
        for fn in sorted(os.listdir(srcdir)):
            if fn.startswith("."):
                continue
            src = os.path.join(srcdir, fn)
            if not os.path.isfile(src):
                continue
            with open(src, "rb") as f:
                content = f.read()
            # skip unchanged
            key = "%s/%s" % (d, fn)
            digest = "%d:%s" % (len(content),
                                __import__("hashlib").sha1(content).hexdigest())
            if pushed.get(key) == digest:
                skipped += 1
                continue
            b64 = base64.b64encode(content).decode()
            dest = "android-tv-inbox/%s/%s" % (d, fn)
            # get current sha if the file exists (update vs create)
            status, existing = _api(
                "GET", "/repos/%s/contents/%s" % (repo, dest), token)
            payload = {"message": "android-tv box: %s" % key,
                       "content": b64, "branch": "main"}
            if status == 200 and existing.get("sha"):
                payload["sha"] = existing["sha"]
            status, _ = _api(
                "PUT", "/repos/%s/contents/%s" % (repo, dest), token, payload)
            if status in (200, 201):
                pushed[key] = digest
                pushed_count += 1
            else:
                return "push failed at %s (stopping)" % key
    os.makedirs(os.path.dirname(PUSHED_PATH), exist_ok=True)
    with open(PUSHED_PATH, "w") as f:
        json.dump(pushed, f, indent=2)
    return "pushed %d, skipped %d unchanged" % (pushed_count, skipped)


def pull_outbox():
    """Download result JSONs from android-tv-outbox/ in the repo into
    local tasks-in/. Returns a status string. Read-only except local files."""
    cfg = _config()
    token = cfg.get("github_token")
    repo = cfg.get("github_repo", "midnightmichigan/mission-keepalive")
    if not token:
        return "no github_token configured — skipping pull"
    try:
        with open(PULLED_PATH) as f:
            pulled = json.load(f)
    except Exception:
        pulled = {}
    status, listing = _api(
        "GET", "/repos/%s/contents/android-tv-outbox" % repo, token)
    if status == 404:
        return "no outbox in repo yet"
    if status != 200 or not isinstance(listing, list):
        return "outbox listing failed (status %s)" % status
    os.makedirs(OUTBOX_DIR, exist_ok=True)
    got = 0
    for entry in listing:
        name = entry.get("name", "")
        sha = entry.get("sha", "")
        if not name.endswith(".json") or pulled.get(name) == sha:
            continue
        dl = entry.get("download_url")
        if not dl:
            continue
        req = urllib.request.Request(
            dl, headers={"User-Agent": "mission-keepalive-androidtv/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            json.loads(body)  # validate before writing
        except Exception:
            continue
        with open(os.path.join(OUTBOX_DIR, name), "w") as f:
            f.write(body)
        pulled[name] = sha
        got += 1
    os.makedirs(os.path.dirname(PULLED_PATH), exist_ok=True)
    with open(PULLED_PATH, "w") as f:
        json.dump(pulled, f, indent=2)
    return "pulled %d new result(s)" % got


if __name__ == "__main__":
    print(push_new_files())
    print(pull_outbox())
