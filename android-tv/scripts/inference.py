#!/usr/bin/env python3
"""inference.py — $0 text inference for the Android TV box. Stdlib only.

Primary:  Pollinations keyless lane (https://text.pollinations.ai/openai,
          OpenAI-compatible POST, no signup, no key). Verified working
          keyless as of Oct 2026. Anonymous lane is rate-limited (~1 req/15s
          per IP, unpublished daily cap) — this module spaces calls 16s apart
          and enforces a small daily cap.
Fallback: OpenRouter :free models (needs a free key in config.local.json;
          no credit card required; 20 RPM / 50 req/day on the free tier).
          Model IDs rotate — default is the "openrouter/free" auto-router.

Privacy: the keyless lane sends prompts to a third party. NEVER put Dakota's
PII, credentials, or secrets in a prompt — drafts use [PLACEHOLDER] tokens
that the VM fills in at send time.

Stub mode: set KA_STUB_INFERENCE=1 to return canned text with no network
(used for offline testing of worker.py).
"""
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.local.json")
STATE_DIR = os.path.join(ROOT, "state")
USAGE_PATH = os.path.join(STATE_DIR, "inference-usage.json")
LASTCALL_PATH = os.path.join(STATE_DIR, "inference-lastcall")

POLLINATIONS_URL = "https://text.pollinations.ai/openai"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MIN_SPACING_S = 16
DEFAULT_DAILY_CAP = 40
UA = {"User-Agent": "mission-keepalive-androidtv/1.0"}

_STUB_TEXT = ("[STUB INFERENCE — offline test mode]\nThis is placeholder text "
              "standing in for a real model response.")


def _config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _usage():
    try:
        with open(USAGE_PATH) as f:
            u = json.load(f)
    except Exception:
        u = {}
    today = date.today().isoformat()
    return u, u.get(today, 0), today


def _bump_usage():
    os.makedirs(STATE_DIR, exist_ok=True)
    u, count, today = _usage()
    u[today] = count + 1
    # keep file small: only last 14 days
    for k in list(u):
        if k < today and len(u) > 14:
            u.pop(k, None)
    with open(USAGE_PATH, "w") as f:
        json.dump(u, f)


def _cap_reached():
    cfg = _config()
    cap = int(cfg.get("daily_inference_cap", DEFAULT_DAILY_CAP))
    _, count, _ = _usage()
    return count >= cap


def _space_calls():
    """Enforce minimum spacing between keyless-lane calls."""
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        with open(LASTCALL_PATH) as f:
            last = float(f.read().strip() or 0)
    except Exception:
        last = 0
    wait = MIN_SPACING_S - (time.time() - last)
    if wait > 0:
        time.sleep(wait)
    with open(LASTCALL_PATH, "w") as f:
        f.write(str(time.time()))


def _post_json(url, payload, headers, timeout):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, "ERROR: %s: %s" % (type(e).__name__, e)


def _extract_openai_text(body):
    try:
        j = json.loads(body)
        return j["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _pollinations(prompt, system, max_tokens, timeout):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    headers = dict(UA)
    headers["Content-Type"] = "application/json"
    # Attempt 1: OpenAI-compatible POST on the keyless lane
    status, body = _post_json(
        POLLINATIONS_URL,
        {"model": "openai", "messages": messages, "max_tokens": max_tokens},
        headers, timeout)
    text = _extract_openai_text(body) if status == 200 else None
    if text:
        return text
    # Attempt 2: legacy keyless GET (plain text response)
    _space_calls()
    q = urllib.parse.quote((system + "\n\n" if system else "") + prompt)
    url = "https://text.pollinations.ai/%s?model=openai" % q
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            t = resp.read().decode("utf-8", errors="replace").strip()
            return t[: max_tokens * 6] if t else None
    except Exception:
        return None


def _openrouter(prompt, system, max_tokens, timeout):
    cfg = _config()
    key = cfg.get("openrouter_key")
    if not key:
        return None
    model = cfg.get("openrouter_model", "openrouter/free")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    headers = dict(UA)
    headers["Content-Type"] = "application/json"
    headers["Authorization"] = "Bearer " + key
    headers["HTTP-Referer"] = "https://midnightmichigan.github.io/muse-invite-code/"
    headers["X-Title"] = "mission-keepalive-androidtv"
    status, body = _post_json(
        OPENROUTER_URL,
        {"model": model, "messages": messages, "max_tokens": max_tokens},
        headers, timeout)
    return _extract_openai_text(body) if status == 200 else None


def complete(prompt, system=None, max_tokens=500, timeout=75):
    """Return model text, or None if inference is unavailable/capped.

    Tries Pollinations keyless first, then OpenRouter :free if a key is
    configured. Never raises on provider failure — returns None.
    """
    if os.environ.get("KA_STUB_INFERENCE") == "1":
        return _STUB_TEXT
    if _cap_reached():
        return None
    _space_calls()
    try:
        text = _pollinations(prompt, system, max_tokens, timeout)
        if text:
            _bump_usage()
            return text
    except Exception:
        pass
    try:
        text = _openrouter(prompt, system, max_tokens, timeout)
        if text:
            _bump_usage()
            return text
    except Exception:
        pass
    return None


def provider_status():
    """Human-readable status line for logs/diagnostics. No secrets."""
    cfg = _config()
    _, count, today = _usage()
    cap = int(cfg.get("daily_inference_cap", DEFAULT_DAILY_CAP))
    or_key = "configured" if cfg.get("openrouter_key") else "not configured"
    return ("inference usage %d/%d today (%s); pollinations=keyless; "
            "openrouter=%s" % (count, cap, today, or_key))
