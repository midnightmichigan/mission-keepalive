# Worker lanes — what the box does per OMEGA mission lane

The worker (`scripts/worker.py`, every 2h) advances these lanes with $0
inference and deterministic tools. Everything it produces is a draft, packet,
or alert — the VM pipelines and Dakota do the acting.

## 1. Outreach drafting → `drafts/`
- Worker drafts up to 3 outreach emails per run from
  `data/outreach-draft-queue.md`, using [PLACEHOLDER] tokens for personal
  details (real details never go to the free inference API).
- Drafts are NOT sent. The VM send pipeline reviews each one through all its
  quality gates (personalization, dedupe, truthfulness) before sending.
- Honest value: token-free first drafts. The VM still does the real work of
  verifying and sending.

## 2. Contest entry prep → `pending-approval/sweepstakes-*.md`
- Worker preps 1 sweepstakes packet per run: fetches the entry page, analyzes
  requirements (account? CAPTCHA? purchase? location limits?), flags red flags.
- The box cannot enter anything itself — most forms need JavaScript, accounts,
  or CAPTCHAs.
- Honest value: lottery odds per entry. A packet is a chance, not income.
  Packets needing purchase are marked SKIPPED, never written.

## 3. Freebie discovery → `pending-approval/freebie-candidates.md`
- Worker scans one aggregator page per run (rotating through
  `data/deal-sources.md`), extracts genuinely-free offers, dedupes against
  previously seen URLs.
- The box never claims anything. Candidates go to the VM freebie pipeline,
  which runs its own dedupe and safety gates.
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
Store credentials anywhere except `config.local.json` (gitignored, on the box
only, created by Dakota's own hand). Attempt anything flagged SKIPPED twice.
