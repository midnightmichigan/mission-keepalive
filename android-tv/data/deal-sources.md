# Deal sources — for the Android TV worker's freebie scan
One source is scanned per worker run (rotating). The worker fetches the page,
extracts candidate freebie/deal links, dedupes against state/seen-deals.json,
and writes genuinely new candidates to pending-approval/freebie-candidates.md.

Row format:
- https://example.com/freebies/ | note

Rules:
- Keep this list SHORT (3–6 sources). These are high-signal freebie
  aggregators only — no forums, no login walls.
- The worker never claims anything itself. Candidates go to pending-approval
  for the VM's freebie pipeline, which runs all its dedupe and safety gates.

## Sources
- https://thefreebieguy.com/ultimate-freebies-guide/ | standing freebie guide, updates often
