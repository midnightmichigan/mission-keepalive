# Worker lanes — what the box does per OMEGA mission lane

The worker (`scripts/worker.py`, every 2h) advances these lanes with $0
inference and deterministic tools. Everything it produces is a draft, packet,
or alert — the VM pipelines and Dakota do the acting.

## 0. Agent orchestration — the multi-agent mesh (NEW)

The box now runs OTHER agents, not just one model:

- **Inference mesh** (`scripts/inference.py`): 4 providers, all $0, no
  credit card — Pollinations (keyless, primary), Groq (free key, ~30 RPM /
  ~14,400 RPD), OpenRouter `:free` (free key, 50/day), Gemini 2.5 Flash via
  AI Studio (free key, ~15 RPM). Mesh failover tries them in order.
- **Role chaining**: every draft runs draft -> critic -> finalize, each on
  a DIFFERENT provider/model with a distinct system prompt. The drafter
  (Pollinations) writes, the critic (Groq) scores it against the
  personalization standard (10-point test, no em dashes, no PR framing),
  the finalizer (Gemini) reconciles both into the final output. All three
  stages are saved (`-draft`, `-critique`, `-final`) so the VM can see the
  reasoning, not just the answer.
- **Task delegation** (`job_delegate` + `VM-WATCHER-SPEC.md`): the box
  writes task-request JSONs to `tasks-out/` for anything it can't do
  itself (browser entries, claims, send-gate reviews, deep research). The
  VM watcher (every 15 min) fans each request to real subagents/workers
  and writes results to `android-tv-outbox/` for the box to collect.
- Realistic throughput: ~40-60 inference calls/day across all free tiers
  (default cap 40; per-run budget 18). A full outreach chain costs 3 calls;
  a worker run with 3 chained drafts + chained prompts + analysis uses
  ~12-15 calls.

## 1. Outreach drafting → `drafts/`
- Worker chains up to 3 outreach emails per run from
  `data/outreach-draft-queue.md`, using [PLACEHOLDER] tokens for personal
  details (real details never go to the free inference API).
- Each email gets three staged files: `-draft` (drafter), `-critique`
  (critic's scored review), `-final` (finalizer's reconciled version).
- The `-final` files are ALSO delegated as `send_review` tasks so the VM
  send pipeline runs them through all quality gates.
- Drafts are NOT sent. The VM send pipeline reviews each one through all its
  quality gates (personalization, dedupe, truthfulness) before sending.
- Honest value: token-free first drafts with a built-in second opinion.
  The VM still does the real work of verifying and sending.

## 2. Contest entry prep → `pending-approval/sweepstakes-*.md`
- Worker preps 1 sweepstakes packet per run: fetches the entry page, analyzes
  requirements (account? CAPTCHA? purchase? location limits?), flags red flags.
- Each packet is ALSO delegated as an `entry_attempt` task so the VM contest
  pipeline can attempt the actual entry with a browser.
- The box cannot enter anything itself — most forms need JavaScript, accounts,
  or CAPTCHAs.
- Honest value: lottery odds per entry. A packet is a chance, not income.
  Packets needing purchase are marked SKIPPED, never written.

## 3. Freebie discovery → `pending-approval/freebie-candidates.md`
- Worker scans one aggregator page per run (rotating through
  `data/deal-sources.md`), extracts genuinely-free offers, dedupes against
  previously seen URLs.
- Candidates are ALSO delegated as `claim_attempt` tasks so the VM freebie
  pipeline can attempt claims with its own dedupe and safety gates.
- The box never claims anything itself.
- Honest value: a steady trickle of candidates. Most are small (samples,
  trial offers); big wins are rare.

## 4. Prompt / idea generation → `prompts/idea-bank.md`
- Worker appends 5 fresh, specific prompts per run (deal research, kids
  activities, money-saving, seasonal), capped at ~400 lines.
- Honest value: creative fuel for content and research. Ideas are free;
  execution is what earns.

## 5. Price-drop monitoring → `alerts/PRICE-*.md`
- Worker watches `data/price-watchlist.md` (Dakota's own list): fetches each
  product page, extracts the price, alerts when it hits his target.
- Only works on pages with server-rendered prices; JS-only or login-walled
  pages get marked stale after 3 misses.
- Honest value: SAVES money on planned purchases. This is not income.

## 6. Money lanes — what is and isn't real
- REAL, automatable: price-drop alerts (above); referral-pool health checks
  (watchdog); contest-deadline flags so entries aren't missed (watchdog).
- REAL but needs a human/VM: referral code placements (need logins —
  prepped to pending-approval when spotted); sweepstakes entries (need a
  browser).
- NOT real from this box: anything resembling "guaranteed income",
  auto-claiming paid offers, crypto/NFT schemes, or entering anything that
  costs money. The box does $0-out, always.

## 7. Daily digest → `digests/YYYY-MM-DD.md`
- Deterministic (no inference): urgent contest count, referral-pool status,
  last heartbeat, inference usage. Dakota's morning read.

## What the box will never do
Send email. Enter anything. Create accounts. Solve CAPTCHAs. Spend money.
Run local models (the box hardware is far too weak — inference is via the
free API mesh, not on-device). Store credentials anywhere except
`config.local.json` (gitignored, on the box only, created by Dakota's own
hand). Attempt anything flagged SKIPPED twice.

## Honest ceiling (read before expecting more)

CAN: draft outreach with a 3-agent critique chain; generate and critique
prompt/idea packs; summarize research; monitor prices, deadlines, referral
pools, and placement health; build sweepstakes/freebie packets; delegate
real execution to the VM's agents via the task inbox (the VM does the
acting, the box does the prep).

CANNOT: logins of any kind; CAPTCHAs; JavaScript-heavy browsing; moving
money; creating accounts; running models locally; anything needing judgment
about Dakota's identity, finances, or reputation — those stay with the VM
pipelines and Dakota.

THROUGHPUT: ~40-60 inference calls/day across the four free tiers (capped
at 40 by default). A worker run does ~12-15 calls. The free tiers can and
do rate-limit or change terms — the mesh degrades gracefully (Pollinations
keyless alone still runs the whole chain, just on one provider).

MONEY: the box earns nothing directly. It multiplies the pipelines that do:
better drafts -> more sends -> more packages; price alerts -> saved money;
entry packets -> lottery chances. Anyone promising the box "prints money"
is lying; this file isn't.
