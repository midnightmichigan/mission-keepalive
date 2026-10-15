# mission-keepalive — Android TV (Termux) build

Token-free watchdogs for Dakota's operation, running on his own Android TV
box instead of a cloud VM. Same four watchers as the systemd build, adapted
for an environment with no systemd, no `gh` CLI, and no journald.

## What runs

| Watcher | Every | What it does | Result file |
|---|---|---|---|
| `heartbeat.py` | 15 min | proof-of-life timestamp | `status/heartbeat.json` |
| `referral_watch.py` | 30 min | verifies **B3NYLG** still listed at usemuse.lol, museai-code.com, and the landing page; local alert after 2 consecutive misses | `status/referral-watch.json` |
| `contest_watch.py` | 6 h | scans the queue snapshot for contests ending within 72 h; keeps `alerts/contest-deadlines.md` updated | `status/contest-deadlines.json` |
| `placement_digest.py` | 24 h | HTTP-status-checks every URL in the placement log (200 = still live) | `status/placement-health.json` |

Scheduling is done by `run.sh`, a single foreground loop that wakes every
60 seconds and runs whichever watcher is due (last-run times in
`state/lastrun-*`). No cron, no systemd.

## Worker layer — real work, $0 inference

`scripts/worker.py` runs every 2 hours and does actual mission work (see
`lanes.md` for the OMEGA lane mapping and the honest ceiling):

| Job | What it makes | Where it lands |
|---|---|---|
| draft_outreach (3/run) | draft->critic->finalize chain per email, 3 staged files each | `drafts/` |
| gen_prompts | chained 5-prompt pack (staged + bank) | `prompts/idea-bank.md` |
| digest | deterministic daily summary | `digests/` |
| price_watch | price-drop alerts on your watchlist | `alerts/PRICE-*.md` |
| sweepstakes_prep (1/run) | pre-filled entry packet with requirements analysis | `pending-approval/` |
| deal_scan (1 source/run) | new freebie candidates from aggregators | `pending-approval/` |
| delegate | task-request JSONs for the VM's agents | `tasks-out/` -> repo `android-tv-inbox/tasks/` |

**Agent orchestration:** `scripts/inference.py` is a 4-provider $0 mesh —
Pollinations (keyless, primary), Groq (free key, ~30 RPM/~14,400 RPD),
OpenRouter `:free` (free key, 50/day), Gemini 2.5 Flash via AI Studio (free
key, ~15 RPM). No credit card for any of them. Every draft runs a
**role chain**: drafter (Pollinations) -> critic (Groq, enforces the
personalization standard) -> finalizer (Gemini), each a different
provider/model with a distinct system prompt. If a provider is down, the
chain degrades to mesh failover instead of dying. Calls are spaced ~16s
apart, capped per day (default 40), per-run budget 18. No PII ever goes
into a prompt.

**Task delegation:** the box can't browse, log in, or send — so
`job_delegate` writes task-request JSONs (`tasks-out/`) for the VM's real
agents: `entry_attempt`, `claim_attempt`, `send_review`, `research_deep`,
`verify`. `scripts/sync.py` pushes them to `android-tv-inbox/tasks/` and
pulls results from `android-tv-outbox/` into `tasks-in/`. The VM-side cron
spec is `VM-WATCHER-SPEC.md` (wired separately, every 15 min).

The box never sends, enters, claims, or buys anything — drafts and packets
wait in `drafts/` and `pending-approval/` for the VM pipelines or Dakota.
Optional: with a `github_token` in `config.local.json`, `scripts/sync.py`
pushes new outputs to `android-tv-inbox/` in the repo for the VM to collect.

## Files

- `run.sh` — the scheduler loop (4 watchers + AI worker). Start: `termux-wake-lock && nohup bash run.sh >/dev/null 2>&1 &`. Stop: `pkill -f mission-keepalive-androidtv/run.sh`.
- `install-termux.sh` — one-shot installer (run inside Termux; see INSTALL.md).
- `.boot/00-mission-keepalive` — Termux:Boot entry; the installer copies it to `~/.termux/boot/` so the loop restarts on reboot (needs the Termux:Boot app).
- `scripts/` — the four watchers + `worker.py` + `inference.py` + `sync.py`, pure Python stdlib.
- `data/` — point-in-time snapshots and worker input queues (refreshed on each install).
- `status/` — latest JSON results. `logs/` — per-job logs plus `runner.log`. `alerts/` — local alert files (replaces GitHub issues).
- `drafts/`, `pending-approval/`, `digests/`, `prompts/` — worker outputs.
- `lanes.md` — what the worker does per OMEGA lane, with honest limits.
- `config.local.json` — optional, gitignored: OpenRouter key, GitHub token, caps. Created by hand on the box only.
- `INSTALL.md` — step-by-step setup for Dakota.

## Differences from the systemd build

- Alerts are local files under `alerts/` (the box has no `gh` CLI and no
  business filing GitHub issues from a TV).
- The placement digest runs every 24 h from last run instead of on a fixed
  08:00 UTC clock (simpler and reboot-proof).
- Logs go to `logs/` files instead of journald.
- Everything is computed relative to the script location, so the package
  works from any path (Termux home is `/data/data/com.termux/files/home`).

## Honest limits

The watchers watch and flag only. The worker drafts, critiques, analyzes,
and monitors — but the box **never** sends email, enters sweepstakes,
creates accounts, solves CAPTCHAs, spends money, or runs models locally
(hardware too weak; inference is via the free API mesh). Without Muse
tokens it **cannot** do anything beyond the free lanes, and anything needing
accounts, logins, or judgment lands in `pending-approval/` or `tasks-out/`
for the VM or Dakota. It needs the box powered, on Wi-Fi, and Termux kept
out of battery optimization. The contest queue snapshot goes stale over
time — re-running `install-termux.sh` refreshes it (idempotent; restarts
the loop cleanly). See `lanes.md` "Honest ceiling" for the full CAN/CANNOT
list with real throughput numbers.

## Cost

$0. No accounts, no keys, no paid services. The only network traffic is the
same read-only HTTP checks the VM watchers already perform.
