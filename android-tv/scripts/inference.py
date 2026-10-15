#!/usr/bin/env python3
"""inference.py — $0 text inference MESH for the Android TV box. Stdlib only.

Four providers, all $0 with NO credit card (verified Oct 2026):

  1. pollinations  — keyless lane (https://text.pollinations.ai/openai).
                     No signup, no key. ~1 req/15s anonymous. PRIMARY.
  2. groq          — free tier, free key at console.groq.com/keys, no card.
                     OpenAI-compatible https://api.groq.com/openai/v1.
                     ~30 RPM / ~14,400 RPD on free tier. Very fast (LPU).
  3. openrouter    — :free models, free key, no card, 50 req/day on free tier.
                     https://openrouter.ai/api/v1. Model "openrouter/free".
  4. gemini        — Google AI Studio free tier, free key (aistudio.google.com),
                     no card. Gemini 2.5 Flash ~15 RPM free. OpenAI-compatible
                     endpoint https://generativelanguage.googleapis.com/v1beta/openai/

Role chaining (see worker.py role_chain): each role (drafter / critic /
finalizer) runs on a DIFFERENT provider+model, so the chain is genuinely
multiple agents checking each other, not one model talking to itself.

Privacy: free lanes send prompts to third parties. NEVER put Dakota's PII,
credentials, or secrets in a prompt — drafts use [PLACEHOLDER] tokens that
the VM fills in at send time.

Stub mode: KA_STUB_INFERENCE=1 returns canned text with no network. In stub
mode, complete_with() tags output with the provider name so tests can prove
the chain used distinct providers.

Daily cap: default 40 inference calls/day total across ALL providers
(config.local.json: daily_inference_cap). Realistic free-tier headroom is
~40-60/day; we stay conservative. Keyless lane spacing: 16s minimum.
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
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/openai/"
              "chat/completions")

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
    return u, u.get(today, {}), today


def _bump_usage(provider):
    os.makedirs(STATE_DIR, exist_ok=True)
    u, today_map, today = _usage()
    today_map[provider] = today_map.get(provider, 0) + 1
    u[today] = today_map
    for k in list(u):
        if k < today and len(u) > 14:
            u.pop(k, None)
    with open(USAGE_PATH, "w") as f:
        json.dump(u, f)


def _total_today():
    _, today_map, _ = _usage()
    return sum(today_map.values())


def _cap_reached():
    cfg = _config()
    cap = int(cfg.get("daily_inference_cap", DEFAULT_DAILY_CAP))
    return _total_today() >= cap


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


def _messages(prompt, system):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return msgs


# ------------------------------------------------------------- providers
def _pollinations(prompt, system, max_tokens, timeout):
    headers = dict(UA)
    headers["Content-Type"] = "application/json"
    status, body = _post_json(
        POLLINATIONS_URL,
        {"model": "openai", "messages": _messages(prompt, system),
         "max_tokens": max_tokens},
        headers, timeout)
    text = _extract_openai_text(body) if status == 200 else None
    if text:
        return text
    # legacy keyless GET fallback
    q = urllib.parse.quote((system + "\n\n" if system else "") + prompt)
    url = "https://text.pollinations.ai/%s?model=openai" % q
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            t = resp.read().decode("utf-8", errors="replace").strip()
            return t[: max_tokens * 6] if t else None
    except Exception:
        return None


def _openai_chat(url, key, model, prompt, system, max_tokens, timeout,
                 extra_headers=None):
    headers = dict(UA)
    headers["Content-Type"] = "application/json"
    headers["Authorization"] = "Bearer " + key
    if extra_headers:
        headers.update(extra_headers)
    status, body = _post_json(
        url,
        {"model": model, "messages": _messages(prompt, system),
         "max_tokens": max_tokens},
        headers, timeout)
    return _extract_openai_text(body) if status == 200 else None


def _groq(prompt, system, max_tokens, timeout):
    key = _config().get("groq_key")
    if not key:
        return None
    model = _config().get("groq_model", "llama-3.3-70b-versatile")
    return _openai_chat(GROQ_URL, key, model, prompt, system, max_tokens,
                        timeout)


def _openrouter(prompt, system, max_tokens, timeout):
    key = _config().get("openrouter_key")
    if not key:
        return None
    model = _config().get("openrouter_model", "openrouter/free")
    return _openai_chat(
        OPENROUTER_URL, key, model, prompt, system, max_tokens, timeout,
        {"HTTP-Referer": "https://midnightmichigan.github.io/muse-invite-code/",
         "X-Title": "mission-keepalive-androidtv"})


def _gemini(prompt, system, max_tokens, timeout):
    key = _config().get("gemini_key")
    if not key:
        return None
    model = _config().get("gemini_model", "gemini-2.5-flash")
    return _openai_chat(GEMINI_URL, key, model, prompt, system, max_tokens,
                        timeout)


PROVIDERS = {
    "pollinations": {
        "fn": _pollinations, "keyless": True, "key_field": None,
        "model": "openai (pollinations lane)",
        "note": "keyless; ~1 req/15s anonymous",
    },
    "groq": {
        "fn": _groq, "keyless": False, "key_field": "groq_key",
        "model": "llama-3.3-70b-versatile (config: groq_model)",
        "note": "free key, no card; ~30 RPM / ~14,400 RPD",
    },
    "openrouter": {
        "fn": _openrouter, "keyless": False, "key_field": "openrouter_key",
        "model": "openrouter/free (config: openrouter_model)",
        "note": "free key, no card; 50 req/day free tier",
    },
    "gemini": {
        "fn": _gemini, "keyless": False, "key_field": "gemini_key",
        "model": "gemini-2.5-flash (config: gemini_model)",
        "note": "AI Studio free key, no card; ~15 RPM",
    },
}

# Mesh failover order: keyless first, then keyed providers.
MESH_ORDER = ["pollinations", "groq", "openrouter", "gemini"]

# Default role->provider mapping for role chaining. Each role runs on a
# DIFFERENT provider so the chain is multi-agent, not self-review.
ROLE_PROVIDERS = {
    "drafter": "pollinations",
    "critic": "groq",
    "finalizer": "gemini",
}


def available_providers():
    """Providers usable right now (keyless always; keyed only if key set)."""
    cfg = _config()
    out = []
    for name, meta in PROVIDERS.items():
        if meta["keyless"] or cfg.get(meta["key_field"]):
            out.append(name)
    return out


def complete_with(provider, prompt, system=None, max_tokens=500, timeout=75):
    """Run one completion on a SPECIFIC provider. Returns text or None.
    Never raises on provider failure."""
    if os.environ.get("KA_STUB_INFERENCE") == "1":
        return "%s\n[provider: %s]" % (_STUB_TEXT, provider)
    if _cap_reached():
        return None
    meta = PROVIDERS.get(provider)
    if not meta:
        return None
    if not meta["keyless"] and not _config().get(meta["key_field"]):
        return None
    _space_calls()
    try:
        text = meta["fn"](prompt, system, max_tokens, timeout)
    except Exception:
        text = None
    if text:
        _bump_usage(provider)
    return text


def complete(prompt, system=None, max_tokens=500, timeout=75):
    """Mesh failover: try providers in MESH_ORDER, return first success.
    Returns None if all unavailable or daily cap reached."""
    if os.environ.get("KA_STUB_INFERENCE") == "1":
        return _STUB_TEXT
    if _cap_reached():
        return None
    for provider in MESH_ORDER:
        text = complete_with(provider, prompt, system, max_tokens, timeout)
        if text:
            return text
    return None


def provider_status():
    """Human-readable status line for logs/diagnostics. No secrets."""
    cfg = _config()
    _, today_map, today = _usage()
    cap = int(cfg.get("daily_inference_cap", DEFAULT_DAILY_CAP))
    total = sum(today_map.values())
    parts = ["%s=%d" % (p, today_map.get(p, 0)) for p in MESH_ORDER]
    keys = []
    for name, meta in PROVIDERS.items():
        if meta["keyless"]:
            keys.append("%s=keyless" % name)
        else:
            keys.append("%s=%s" % (
                name, "key" if cfg.get(meta["key_field"]) else "no-key"))
    return ("inference %d/%d today (%s) [%s]; %s" % (
        total, cap, today, ", ".join(parts), "; ".join(keys)))
