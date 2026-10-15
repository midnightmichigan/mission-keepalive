# Outreach draft queue — for the Android TV worker
Rows the box's AI worker drafts outreach emails for. Drafts are NOT sent —
they land in drafts/ for the VM send pipeline (which runs all its quality
gates) to review and send.

Row format (in code block so the worker doesn't read this line as a row):
```
- [ ] **Brand Name** | contact@example.com | category | one-line note about them
```

Rules for this file:
- The VM refreshes this file with real staged rows (re-run install-termux.sh
  to pull the latest).
- The worker drafts max 3 per run, oldest undrafted first, and records them
  in state/drafted.json so it never drafts the same row twice.
- Drafts use [PLACEHOLDER] tokens for personal details — real details are
  filled by the VM at send time, never sent to the free inference API.

## Seed rows (EXAMPLES — replace on refresh)
- [ ] [EXAMPLE] **Example Brand Co** | hello@example.com | snacks | EXAMPLE ROW — makes granola bars; known to send sample boxes
- [ ] [EXAMPLE] **Example Outfitters** | team@example.com | outdoor gear | EXAMPLE ROW — family camping gear; runs a tester program
