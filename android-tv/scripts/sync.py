#!/usr/bin/env python3
"""sync.py — push the box's output files to the GitHub repo so the VM can
pick them up. Stdlib only. COMPLETELY OPTIONAL: runs only if config.local.json
contains a github_token. The token never leaves the box except in the
Authorization header to api.github.com.

Pushes new/changed files from drafts/, pending-approval/, digests/, alerts/
into android-tv-inbox/ on the repo's main branch. Tracks pushed SHAs in
state/pushed.json so it never re-pushes unchanged files.
"""
import base64
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.local.json")
PUSHED_PATH = os.path.join(ROOT, "state", "pushed.json")
SYNC_DIRS = ("drafts", "pending-approval", "digests", "alerts")
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


if __name__ == "__main__":
    print(push_new_files())
