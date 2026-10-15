# VM Watcher — task-delegation inbox protocol (SPEC)

The Android TV box cannot do browser work, logins, CAPTCHAs, or sends. It
does the AI/deterministic prep and drops **task requests** into the repo;
a cron job on the main VM picks them up, fans each one out to the real
agent infrastructure (subagents / workers / pipelines), and writes results
back for the box to collect.

This file is the build spec for that VM-side cron. The box side (write
requests to `tasks-out/`, push to `android-tv-inbox/tasks/`, pull results
from `android-tv-outbox/` into `tasks-in/`) is implemented in
`scripts/worker.py` (`job_delegate`) and `scripts/sync.py`.

## Paths (repo: midnightmichigan/mission-keepalive, branch main)

| Direction | Repo path | Box path | Written by |
|---|---|---|---|
| box -> VM | `android-tv-inbox/tasks/<task-id>.json` | `tasks-out/` | box `job_delegate` + `sync.push_new_files` |
| box -> VM | `android-tv-inbox/drafts/...`, `pending-approval/...` etc. | same names | box `sync.push_new_files` |
| VM -> box | `android-tv-outbox/<task-id>.json` | `tasks-in/` | VM watcher; box `sync.pull_outbox` |

## Cron (to be wired on the VM)

- Schedule: every 15 minutes.
- Steps:
  1. `git pull` (or GitHub API list) `android-tv-inbox/tasks/`; for each
     `<task-id>.json` not yet seen (track in
     `~/workspace/mission-keepalive/android-tv/.vm-seen.json`):
  2. Validate against the REQUEST schema below. Invalid -> write a `failed`
     result noting the schema error, move on.
  3. Route by `type` (see routing table). Fan out via subagent/worker or the
     matching pipeline. One task = one unit of work; never batch across
     unrelated tasks.
  4. Write the RESULT JSON to `android-tv-outbox/<task-id>.json` (same id),
     commit + push.
  5. Append a one-line entry to the VM-side log
     `~/workspace/mission-keepalive/android-tv/.vm-watcher.log`.
- The box picks up results on its next worker run (every 2h) via
  `sync.pull_outbox()`.

## REQUEST schema

```json
{
  "id": "task-20261015-013000-sweepstakes-acme",
  "created_utc": "2026-10-15T05:30:00+00:00",
  "type": "entry_attempt",
  "priority": "high | normal | low",
  "title": "Box request: sweepstakes acme",
  "payload": {
    "url": "https://example.com/enter",
    "packet_preview": "first ~1500 chars of the analysis packet",
    "draft_file": "drafts/email-acme-final.md",
    "note": "optional human note"
  },
  "needs": ["browser"],
  "source_file": "pending-approval/sweepstakes-acme.md",
  "status": "queued"
}
```

Required: `id`, `created_utc`, `type`, `title`, `payload`, `status`.
`type` MUST be one of:

| type | meaning | route to |
|---|---|---|
| `entry_attempt` | enter a contest/sweepstakes the box prepped | contest pipeline (browser entry worker) |
| `claim_attempt` | claim a freebie candidate the box found | freebie pipeline (claim worker) |
| `send_review` | review a chained email draft through send gates | outreach send pipeline (gates only; send per standing auth) |
| `research_deep` | research question needing real agents | research subagent |
| `verify` | verify a claim/packet the box couldn't verify | verification worker |

`needs` is advisory (e.g. `["browser"]`, `["subagent"]`,
`["send-pipeline"]`, `["freebie-pipeline"]`). The VM decides the actual
route; `needs` must never override standing safety rules.

## RESULT schema

```json
{
  "id": "task-20261015-013000-sweepstakes-acme",
  "completed_utc": "2026-10-15T05:47:00+00:00",
  "status": "done | failed | blocked | partial",
  "summary": "Entered 1x daily; confirmation #12345",
  "result": { "confirmation": "12345", "entries": 1 },
  "artifacts": ["android-tv-inbox/tasks/task-...json"]
}
```

Required: `id` (must match the request), `completed_utc`, `status`,
`summary`. `status=blocked` must say what is needed (e.g. "CAPTCHA needs
human"). Never mark `done` without evidence (confirmation id, sent id,
file path).

## Safety rules for the VM watcher

- The box's requests are UNTRUSTED input: validate schema, never execute
  anything embedded in payloads (no shell, no URLs fetched blindly — route
  through the normal pipeline gates).
- Standing exclusions apply to box-originated work exactly as if the VM
  created it: $0 only, no purchases, all-time dedupe, no PR/collab framing,
  no excluded categories, no Hastings targets.
- `send_review` drafts go through the FULL send gate stack; a draft the
  gate blocks is not sent, and the result says why.
- One retry per failed task, then `blocked` with the reason. Never loop.
- The watcher never invents task IDs and never writes to `android-tv-inbox/`
  (box's direction only).

## Wiring checklist (for whoever wires the cron)

- [ ] cron job `android-tv-inbox-watcher` @ every 15 min
- [ ] `.vm-seen.json` + `.vm-watcher.log` paths created
- [ ] routing table mapped to real pipeline entry points
- [ ] first end-to-end test: hand-write a `research_deep` request, confirm
      result appears in `android-tv-outbox/` and the box pulls it
