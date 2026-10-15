#!/usr/bin/env python3
"""worker.py — token-free AI worker for the Android TV box. Stdlib only.

Runs every WORKER_INT (default 2h) from run.sh. Does REAL mission work with
$0 inference (see inference.py) and deterministic tools:

  1. draft_outreach  — draft->critic->finalize ROLE CHAIN across three
                       different providers/models -> drafts/ (3 staged files
                       per email: -draft, -critique, -final)
  2. gen_prompts     — same role chain -> prompts/idea-bank.md
  3. digest          — deterministic daily summary -> digests/
  4. price_watch     — price-drop monitoring -> alerts/ on hits
  5. sweepstakes_prep— pre-filled entry packet -> pending-approval/
  6. deal_scan       — one aggregator page per run -> freebie candidates
  7. delegate        — writes task-request JSON -> tasks-out/ for the VM's
                       agents (see VM-WATCHER-SPEC.md)

The role chain is genuinely multi-agent: the drafter (Pollinations), the
critic (Groq, checks the draft against the personalization standard), and
the finalizer (Gemini) are different providers/models with distinct system
prompts. If a role's provider is down, the chain degrades gracefully to the
mesh failover instead of dying.

Hard rules:
- Nothing is ever SENT, ENTERED, CLAIMED, or BOUGHT from this box. Drafts,
  packets, and candidates go to drafts/ and pending-approval/ for the VM
  pipelines (with all their gates) or Dakota.
- No PII ever goes into an inference prompt. Drafts use [PLACEHOLDER] tokens;
  the VM fills real details at send time.
- Inference is capped (daily cap in config.local.json, default 40/day) and
  spaced (~16s) to respect the free tier. Per-run call budget: 18.
- Every job is wrapped: one job failing never stops the others.
"""
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inference

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "mission-keepalive-androidtv/1.0"}
MAX_CALLS_PER_RUN = 18

_CALL_BUDGET = {"used": 0}


def _infer(provider, prompt, system=None, max_tokens=500):
    """One budgeted inference call. provider=None -> mesh failover."""
    if _CALL_BUDGET["used"] >= MAX_CALLS_PER_RUN:
        return None
    _CALL_BUDGET["used"] += 1
    if provider:
        return inference.complete_with(provider, prompt, system, max_tokens)
    return inference.complete(prompt, system, max_tokens)


# ------------------------------------------------------- role chaining
# Three distinct agents, three different providers. The critic enforces the
# personalization standard; the finalizer reconciles draft + critique.
CRITIC_SYSTEM = (
    "You are a ruthless quality critic for outreach emails. Score the draft "
    "against these rules and list every violation with a fix: "
    "(1) Could this email go to ten unrelated companies with only names "
    "changed? If yes, FAIL. "
    "(2) Is there a verified, recipient-specific reason for contact? "
    "(3) Are all personal claims true and supported (no invented usage, no "
    "invented purchase history)? "
    "(4) Is the ask appropriate for this organization? "
    "(5) Any em dash (U+2014) anywhere? FAIL if present. "
    "(6) Any PR/influencer/collab/partnership/review-program framing? FAIL. "
    "(7) Any manufactured emotion, begging, or guilt-tripping? FAIL. "
    "(8) Any real personal details (name, city, email, phone, address)? "
    "Placeholders only — FAIL on real ones. "
    "Be specific: quote the offending line, name the rule, give the fix. "
    "End with one line: VERDICT: PASS or VERDICT: REWRITE."
)

FINALIZER_SYSTEM = (
    "You finalize outreach emails. You receive an original draft plus a "
    "critic's review. Rewrite the email fixing every violation the critic "
    "found, keeping what was good. Voice: warm, grateful dad, first person. "
    "No em dashes ever. No PR/influencer/collab framing. Never invent "
    "personal details — keep [YOUR NAME], [CITY], [EMAIL] placeholders. "
    "Under 180 words. Output ONLY the final email: 'Subject: ...' line, "
    "then the body, signed [YOUR NAME]."
)

PROMPT_CRITIC_SYSTEM = (
    "You are a ruthless quality critic for content prompts. Reject any "
    "prompt that is vague, generic, unusable, or duplicated from common "
    "advice. Each surviving prompt must be concrete and specific enough to "
    "execute immediately. Quote weak lines and say why they fail. End with "
    "VERDICT: PASS or VERDICT: REWRITE."
)

PROMPT_FINALIZER_SYSTEM = (
    "You finalize a pack of content prompts. You receive a draft pack plus "
    "a critic's review. Rewrite fixing every weakness, keeping strengths. "
    "Output ONLY the final numbered list, one prompt per line, each under "
    "25 words."
)


def role_chain(slug, kind, draft_prompt, draft_system,
               critic_system, finalizer_system, save_dir, max_tokens=450):
    """Run draft -> critic -> finalize on three DIFFERENT providers.

    Saves three staged files: <slug>-draft.md, <slug>-critique.md,
    <slug>-final.md in save_dir. Returns the final text, or the best
    available stage if the chain degrades. Returns None if nothing works.
    """
    roles = inference.ROLE_PROVIDERS
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    os.makedirs(save_dir, exist_ok=True)

    def _save(stage, text):
        p = os.path.join(save_dir, "%s-%s-%s.md" % (kind, slug, stage))
        with open(p, "w") as f:
            f.write("# %s (%s) — %s\n\n%s\n" % (kind, stage, slug, text))
        return p

    draft = _infer(roles.get("drafter"), draft_prompt, draft_system,
                   max_tokens)
    if not draft:
        log("role_chain %s: drafter failed" % slug)
        return None
    _save("draft", draft)

    critic_prompt = ("Critique this %s against your quality rules. Be "
                     "specific.\n\n%s" % (kind, draft))
    critique = _infer(roles.get("critic"), critic_prompt, critic_system,
                      max_tokens)
    if critique:
        _save("critique", critique)
    else:
        log("role_chain %s: critic failed, finalizing from draft" % slug)
        critique = "(critic unavailable — finalize from draft alone)"

    final_prompt = ("Original draft:\n%s\n\nCritic's review:\n%s\n\n"
                    "Now produce the final version." % (draft, critique))
    final = _infer(roles.get("finalizer"), final_prompt, finalizer_system,
                   max_tokens)
    if not final:
        log("role_chain %s: finalizer failed, using draft" % slug)
        final = draft
    _save("final", final)
    log("role_chain %s: draft->critic->finalize complete" % slug)
    return final

DRAFT_QUEUE = os.path.join(ROOT, "data", "outreach-draft-queue.md")
PRICE_LIST = os.path.join(ROOT, "data", "price-watchlist.md")
SWEEP_QUEUE = os.path.join(ROOT, "data", "sweepstakes-prep-queue.md")
DEAL_SOURCES = os.path.join(ROOT, "data", "deal-sources.md")


def log(msg):
    print("[worker %s] %s" % (
        datetime.now(timezone.utc).isoformat(timespec="seconds"), msg),
        flush=True)


def _ensure(*dirs):
    for d in dirs:
        os.makedirs(os.path.join(ROOT, d), exist_ok=True)


def _load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def _parse_rows(path):
    """Parse '- [ ] **Name** | field | field...' rows. Skips [EXAMPLE] rows
    and lines inside fenced code blocks (format documentation)."""
    rows = []
    in_fence = False
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("```"):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    continue
                line = stripped
                if not line.startswith("- [ ]"):
                    continue
                if "[EXAMPLE]" in line:
                    continue
                m = re.match(r"- \[ \] \*\*(.+?)\*\*\s*\|(.*)$", line)
                if not m:
                    continue
                name = m.group(1).strip()
                fields = [x.strip() for x in m.group(2).split("|")]
                rows.append({"name": name, "fields": fields, "raw": line})
    except FileNotFoundError:
        pass
    return rows


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50]


def _fetch(url, timeout=25, max_bytes=400000):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(max_bytes).decode(
                "utf-8", errors="replace")
    except Exception as e:
        return None, "FETCH_ERROR: %s" % e


# ---------------------------------------------------------------- draft_outreach
DRAFT_SYSTEM = (
    "You draft outreach emails for a dad's family freebie operation. "
    "Voice: warm, grateful dad, first person as Dakota. No em dashes ever. "
    "No PR/influencer/collab framing. Never invent personal details. "
    "Use [YOUR NAME], [CITY], [EMAIL] placeholders for personal details — "
    "never real ones. Keep it under 180 words."
)


def job_draft_outreach():
    rows = _parse_rows(DRAFT_QUEUE)
    drafted = _load_json(os.path.join(ROOT, "state", "drafted.json"), {})
    _ensure("drafts")
    made = 0
    for r in rows:
        if made >= 3 or r["name"] in drafted:
            continue
        email = r["fields"][0] if len(r["fields"]) > 0 else ""
        category = r["fields"][1] if len(r["fields"]) > 1 else "general"
        note = r["fields"][2] if len(r["fields"]) > 2 else ""
        prompt = (
            "Write a short, warm outreach email to this company.\n"
            "Company: %s\nContact: %s\nCategory: %s\n"
            "What I know about them: %s\n\n"
            "Include: one specific detail about THEM from the note, one "
            "honest line about why a dad writing for his family fits, and "
            "ONE ask matched to the category (samples for sample-givers, "
            "merch/sweepstakes for promo brands, never alcohol product asks). "
            "Subject line first as 'Subject: ...', then the body. Sign as "
            "[YOUR NAME]." % (r["name"], email, category, note))
        slug = _slug(r["name"])
        final = role_chain(
            slug, "email", prompt, DRAFT_SYSTEM,
            CRITIC_SYSTEM, FINALIZER_SYSTEM,
            os.path.join(ROOT, "drafts"), max_tokens=450)
        if not final:
            log("draft_outreach: chain failed for %s, stopping" % r["name"])
            break
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        drafted[r["name"]] = stamp
        made += 1
        log("draft_outreach: chained %s (draft+critique+final saved)" %
            r["name"])
    _save_json(os.path.join(ROOT, "state", "drafted.json"), drafted)
    return "chained %d" % made


# ---------------------------------------------------------------- gen_prompts
PROMPT_SYSTEM = (
    "You generate creative prompt packs for a content operation. "
    "Concrete, specific, usable prompts only — no fluff."
)


def job_gen_prompts():
    _ensure("prompts")
    bank = os.path.join(ROOT, "prompts", "idea-bank.md")
    prompt = (
        "Write 5 fresh, specific content prompts for a family deals/freebies "
        "operation, one per line, numbered. Mix: 2 deal-hunting research "
        "prompts, 1 kids-activity idea prompt, 1 money-saving prompt, "
        "1 seasonal prompt. Each under 25 words.")
    final = role_chain(
        datetime.now(timezone.utc).strftime("%Y%m%d-%H%M"), "prompts",
        prompt, PROMPT_SYSTEM, PROMPT_CRITIC_SYSTEM, PROMPT_FINALIZER_SYSTEM,
        os.path.join(ROOT, "prompts", "staged"), max_tokens=350)
    if not final:
        log("gen_prompts: chain failed, skipping")
        return "skipped (no inference)"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(bank, "a") as f:
        f.write("\n## %s\n\n%s\n" % (stamp, final))
    # cap file size: keep last ~400 lines
    with open(bank) as f:
        lines = f.readlines()
    if len(lines) > 400:
        with open(bank, "w") as f:
            f.writelines(lines[-400:])
    log("gen_prompts: chained 5 prompts (staged + bank)")
    return "chained 5"


# ---------------------------------------------------------------- digest
def job_digest():
    _ensure("digests")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(ROOT, "digests", "%s.md" % today)
    if os.path.exists(path):
        return "already exists"
    parts = ["# Mission digest — %s (UTC)\n" % today]
    cw = _load_json(os.path.join(ROOT, "status", "contest-deadlines.json"), {})
    urgent = cw.get("contests", [])
    parts.append("## Contests ending within 72h: %d" % len(urgent))
    for c in urgent[:10]:
        parts.append("- %s — ends %s — %s" % (
            c.get("name"), c.get("ends"), c.get("url")))
    rw = _load_json(os.path.join(ROOT, "status", "referral-watch.json"), {})
    pools = rw.get("pools", {})
    ok = sum(1 for p in pools.values() if p.get("code_found"))
    parts.append("\n## Referral code B3NYLG: %d/%d pools listing it" % (
        ok, len(pools)))
    hb = _load_json(os.path.join(ROOT, "status", "heartbeat.json"), {})
    parts.append("\n## Last heartbeat: %s" % hb.get("last_heartbeat_utc", "?"))
    parts.append("\n## Inference: %s" % inference.provider_status())
    with open(path, "w") as f:
        f.write("\n".join(parts) + "\n")
    log("digest: wrote %s" % path)
    return "wrote digest"


# ---------------------------------------------------------------- price_watch
PRICE_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)")


def job_price_watch():
    rows = _parse_rows(PRICE_LIST)
    state = _load_json(os.path.join(ROOT, "state", "price-state.json"), {})
    _ensure("alerts")
    for r in rows:
        if len(r["fields"]) < 2:
            continue
        url = r["fields"][0]
        tm = re.search(r"\$\s?([\d,]+\.?\d*)", r["fields"][1] or "")
        if not url.startswith("http") or not tm:
            continue
        target = float(tm.group(1).replace(",", ""))
        st = state.get(r["name"], {})
        if st.get("stale"):
            continue
        status, body = _fetch(url)
        m = PRICE_RE.search(body or "")
        if not status or not m:
            st["misses"] = st.get("misses", 0) + 1
            if st["misses"] >= 3:
                st["stale"] = True
                log("price_watch: %s STALE-CHECK (no price 3x)" % r["name"])
            state[r["name"]] = st
            continue
        price = float(m.group(1).replace(",", ""))
        st.update({"last_price": price, "misses": 0,
                   "checked": datetime.now(timezone.utc).isoformat()})
        state[r["name"]] = st
        if price <= target and not st.get("alerted_at_target"):
            ap = os.path.join(ROOT, "alerts",
                              "PRICE-%s.md" % _slug(r["name"]))
            with open(ap, "w") as f:
                f.write("# PRICE ALERT — %s\n\nPrice $%.2f is at/below your "
                        "target $%.2f.\n\n%s\n\nChecked: %s UTC\n" % (
                            r["name"], price, target, url,
                            datetime.now(timezone.utc).isoformat()))
            st["alerted_at_target"] = True
            state[r["name"]] = st
            log("price_watch: ALERT %s $%.2f <= $%.2f" % (
                r["name"], price, target))
        else:
            log("price_watch: %s $%.2f (target $%.2f)" % (
                r["name"], price, target))
        if price > target:
            st["alerted_at_target"] = False
            state[r["name"]] = st
    _save_json(os.path.join(ROOT, "state", "price-state.json"), state)
    return "checked %d" % len(rows)


# ---------------------------------------------------------------- sweepstakes_prep
SWEEP_SYSTEM = (
    "You analyze sweepstakes entry pages. Be precise and honest. "
    "Never invent rules, dates, or requirements not visible."
)


def job_sweepstakes_prep():
    rows = _parse_rows(SWEEP_QUEUE)
    prepped = _load_json(os.path.join(ROOT, "state", "sweeps-prepped.json"), {})
    _ensure("pending-approval")
    for r in rows:
        if r["name"] in prepped:
            continue
        url = r["fields"][0] if len(r["fields"]) > 0 else ""
        ends = r["fields"][1] if len(r["fields"]) > 1 else "unknown"
        prize = r["fields"][2] if len(r["fields"]) > 2 else "unknown"
        if not url.startswith("http"):
            continue
        status, body = _fetch(url, max_bytes=200000)
        snippet = re.sub(r"<[^>]+>", " ", body or "")
        snippet = re.sub(r"\s+", " ", snippet)[:6000]
        prompt = (
            "Analyze this sweepstakes entry page text and answer briefly:\n"
            "1. Is entry still open? 2. What does entry require "
            "(account? CAPTCHA? purchase? age? location limits)? "
            "3. Entry frequency (one-time/daily)? 4. Any red flags?\n\n"
            "Page text:\n%s" % snippet)
        text = _infer(None, prompt, SWEEP_SYSTEM, 400)
        if not text:
            log("sweepstakes_prep: inference unavailable, skipping")
            return "skipped (no inference)"
        slug = _slug(r["name"])
        path = os.path.join(ROOT, "pending-approval",
                            "sweepstakes-%s.md" % slug)
        with open(path, "w") as f:
            f.write(
                "# PENDING: sweepstakes entry — %s\n\n"
                "Date: %s UTC\n"
                "Type: sweepstakes-entry\n"
                "URL: %s\n"
                "Stated end: %s | Prize: %s\n\n"
                "## Why blocked (box cannot enter itself)\n"
                "Most entry forms need JavaScript, an account, or a CAPTCHA — "
                "none of which this box can do.\n\n"
                "## Page analysis (AI-read, verify before acting)\n\n%s\n\n"
                "## Exact next step for VM/human\n"
                "Open the URL above in a browser, complete the entry per the "
                "requirements listed, one entry per the stated frequency.\n\n"
                "## Expected value (honest)\n"
                "Lottery odds. A packet is a chance, not income.\n" % (
                    r["name"], datetime.now(timezone.utc).isoformat(), url,
                    ends, prize, text))
        prepped[r["name"]] = datetime.now(timezone.utc).isoformat()
        _save_json(os.path.join(ROOT, "state", "sweeps-prepped.json"), prepped)
        log("sweepstakes_prep: packet -> %s" % path)
        return "prepped 1"
    return "nothing new"


# ---------------------------------------------------------------- deal_scan
DEAL_SYSTEM = (
    "You extract freebie/deal opportunities from web page text. "
    "List only items that look genuinely free with no purchase. "
    "Never invent URLs."
)


def job_deal_scan():
    sources = []
    try:
        with open(DEAL_SOURCES, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- http"):
                    sources.append(line[2:].split("|")[0].strip())
    except FileNotFoundError:
        return "no sources"
    if not sources:
        return "no sources"
    idx = _load_json(os.path.join(ROOT, "state", "deal-source-idx.json"),
                     {"i": 0})["i"] % len(sources)
    url = sources[idx]
    _save_json(os.path.join(ROOT, "state", "deal-source-idx.json"),
               {"i": idx + 1})
    seen = _load_json(os.path.join(ROOT, "state", "seen-deals.json"), [])
    status, body = _fetch(url, max_bytes=300000)
    if not status:
        log("deal_scan: fetch failed %s" % url)
        return "fetch failed"
    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"\s+", " ", text)[:8000]
    prompt = (
        "From this freebie-guide page text, list up to 8 current freebie "
        "offers (free samples, free products, free subscriptions). For each: "
        "name, what is free, and its URL if visible. Format: '- name | what "
        "is free | url'. Skip anything needing purchase.\n\nPage text:\n%s"
        % text)
    out = _infer(None, prompt, DEAL_SYSTEM, 600)
    if not out:
        log("deal_scan: inference unavailable, skipping")
        return "skipped (no inference)"
    new_items = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        urls = re.findall(r"https?://[^\s\)\]]+", line)
        if any(u in seen for u in urls):
            continue
        new_items.append(line)
        seen.extend(urls)
    _save_json(os.path.join(ROOT, "state", "seen-deals.json"), seen[-500:])
    if new_items:
        _ensure("pending-approval")
        p = os.path.join(ROOT, "pending-approval", "freebie-candidates.md")
        with open(p, "a") as f:
            f.write("\n## %s UTC — from %s\n\n%s\n" % (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                url, "\n".join(new_items)))
        log("deal_scan: %d new candidates -> %s" % (len(new_items), p))
        return "%d new candidates" % len(new_items)
    log("deal_scan: no new candidates")
    return "no new candidates"


# ---------------------------------------------------------------- delegate
# Task-delegation inbox protocol (see VM-WATCHER-SPEC.md).
#
# The box cannot do browser work, logins, CAPTCHAs, or sends. When it builds
# something the VM's agents should act on, it writes a task-request JSON file
# to tasks-out/. sync.py pushes tasks-out/ to android-tv-inbox/tasks/ in the
# repo; the VM watcher (every 15 min) fans each request to subagents/workers
# and writes results to android-tv-outbox/, which sync.py pulls into tasks-in/.
#
# REQUEST schema:
#   { "id": "task-YYYYMMDD-HHMMSS-<slug>", "created_utc": iso,
#     "type": "entry_attempt|claim_attempt|send_review|research_deep|verify",
#     "priority": "high|normal|low", "title": "short human title",
#     "payload": { ...type-specific... },
#     "needs": ["browser"|"subagent"|"send-pipeline"|"freebie-pipeline"|...],
#     "source_file": "pending-approval/...", "status": "queued" }
#
# RESULT schema (written by the VM watcher into android-tv-outbox/):
#   { "id": "<same id>", "completed_utc": iso,
#     "status": "done|failed|blocked|partial", "summary": "one line",
#     "result": { ... }, "artifacts": ["repo paths..."] }

DELEGATABLE = {
    # (source dir prefix, file prefix, request type, needs, priority)
    "sweepstakes-": ("entry_attempt", ["browser"], "normal"),
    "freebie-candidates": ("claim_attempt", ["freebie-pipeline"], "normal"),
}


def _task_id(slug):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return "task-%s-%s" % (stamp, slug[:30])


def job_delegate():
    _ensure("tasks-out", "tasks-in")
    delegated = _load_json(
        os.path.join(ROOT, "state", "delegated.json"), {})
    made = 0
    pa = os.path.join(ROOT, "pending-approval")
    if not os.path.isdir(pa):
        return "no pending-approval dir"
    for fn in sorted(os.listdir(pa)):
        if fn.startswith(".") or not fn.endswith(".md"):
            continue
        key = "pending-approval/%s" % fn
        if key in delegated:
            continue
        stem = fn[:-3]
        matched = None
        for prefix, spec in DELEGATABLE.items():
            if stem.startswith(prefix):
                matched = spec
                break
        if not matched:
            continue
        rtype, needs, priority = matched
        with open(os.path.join(pa, fn), encoding="utf-8",
                  errors="replace") as f:
            body = f.read(4000)
        # extract URL if present
        m = re.search(r"https?://[^\s\)\]]+", body)
        url = m.group(0) if m else ""
        tid = _task_id(_slug(stem))
        req = {
            "id": tid,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "type": rtype,
            "priority": priority,
            "title": "Box request: %s" % stem.replace("-", " "),
            "payload": {"url": url, "packet_preview": body[:1500]},
            "needs": needs,
            "source_file": key,
            "status": "queued",
        }
        out = os.path.join(ROOT, "tasks-out", tid + ".json")
        _save_json(out, req)
        delegated[key] = tid
        made += 1
        log("delegate: queued %s -> %s" % (tid, rtype))
    # also delegate finalized drafts for VM send-pipeline review (once each)
    drafts_dir = os.path.join(ROOT, "drafts")
    if os.path.isdir(drafts_dir):
        for fn in sorted(os.listdir(drafts_dir)):
            if not fn.endswith("-final.md"):
                continue
            key = "drafts/%s" % fn
            if key in delegated:
                continue
            tid = _task_id(_slug(fn[:-9]))
            req = {
                "id": tid,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "type": "send_review",
                "priority": "normal",
                "title": "Review chained draft: %s" % fn,
                "payload": {"draft_file": key,
                            "note": "draft->critic->finalize chain output; "
                                    "run VM send gates before sending"},
                "needs": ["send-pipeline"],
                "source_file": key,
                "status": "queued",
            }
            _save_json(os.path.join(ROOT, "tasks-out", tid + ".json"), req)
            delegated[key] = tid
            made += 1
            log("delegate: queued %s -> send_review" % tid)
    _save_json(os.path.join(ROOT, "state", "delegated.json"), delegated)
    return "queued %d" % made


# ---------------------------------------------------------------- main
JOBS = [
    ("draft_outreach", job_draft_outreach),
    ("gen_prompts", job_gen_prompts),
    ("digest", job_digest),
    ("price_watch", job_price_watch),
    ("sweepstakes_prep", job_sweepstakes_prep),
    ("deal_scan", job_deal_scan),
    ("delegate", job_delegate),
]


def main():
    _ensure("drafts", "prompts", "digests", "pending-approval",
            "alerts", "state", "tasks-out", "tasks-in")
    log("worker run started — %s" % inference.provider_status())
    results = {}
    for name, fn in JOBS:
        try:
            results[name] = fn()
        except Exception as e:
            results[name] = "ERROR: %s: %s" % (type(e).__name__, e)
            log("%s failed: %s" % (name, results[name]))
    # optional: push new files to the repo for the VM to pick up,
    # and pull VM results for delegated tasks
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import sync
        results["sync_push"] = sync.push_new_files()
        results["sync_pull"] = sync.pull_outbox()
    except Exception as e:
        results["sync"] = "skipped: %s" % e
    log("worker run done: %s" % json.dumps(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
