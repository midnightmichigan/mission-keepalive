# mission-keepalive

Token-independent monitoring for Dakota McCall's operation. These GitHub
Actions workflows run on GitHub's free tier for public repos — they keep
working even if the Muse token pool hits zero. No AI, no logins, no CAPTCHAs,
no spending. Read-only checks plus timestamped status files.

## Workflows

| Workflow | Schedule (UTC) | What it does | Status file |
|---|---|---|---|
| `referral-watch` | every 30 min | Verifies invite code **B3NYLG** is still listed at usemuse.lol/invite-code, museai-code.com, and the landing page. Alerts (GitHub issue) only after 2 consecutive misses. | `status/referral-watch.json` |
| `contest-watch` | every 6 h | Parses the contest queue snapshot for entries ending within 72 h and keeps one persistent issue updated. | `status/contest-deadlines.json` |
| `placement-digest` | daily 08:00 | HTTP-status-checks every public URL in the referral-placement log (200 = still live). | `status/placement-health.json` |
| `heartbeat` | every 15 min | Writes a UTC timestamp and commits it — proof the system is alive. | `status/heartbeat.json` |

## Reading the dashboard

- Latest results: open the files under [`status/`](status/).
- Active alerts: [Issues](../../issues) — anything titled `ALERT:` or
  `Contest deadlines` needs a human or a token-funded agent.

## Data snapshots

`data/` holds point-in-time copies of the operation's registries
(`referral-placements-snapshot.md`, `contests-queue-snapshot.md`) taken when
this repo was built. They are inputs for the watchers, not live mirrors.

## LIMITS — what this system cannot do

This is a monitor, not a replacement for the operation. Without Muse tokens
it **cannot**:

- write or send personalized outreach emails
- enter sweepstakes or instant-win games
- solve CAPTCHAs or pass bot checks
- create accounts (email, social, panels)
- do any AI inference, research, or judgment calls
- place new referral codes or re-submit missing ones (it only *detects* absence)

If the token pool is empty, this system keeps watch and raises flags. Acting
on those flags needs tokens back or a human.

## Cost

$0. GitHub Actions is free for public repositories. No paid services, no keys,
no secrets beyond the built-in `GITHUB_TOKEN`.
