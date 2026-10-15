# pending-approval/ — the box's outbox

The Android TV box can draft, analyze, and monitor — but it cannot send
emails, enter sweepstakes, create accounts, pass CAPTCHAs, or spend money.
Anything needing those lands here as a packet for the VM pipelines (which run
all their safety gates) or for Dakota to do by hand.

## File format

Every packet is a Markdown file named `<type>-<slug>.md`:

```text
# PENDING: <short title>

Date: <UTC timestamp>
Type: sweepstakes-entry | referral-placement | freebie-candidate-batch | account-needed | other
URL: <relevant link, if any>

## Why blocked (box cannot do this itself)
<one honest line>

## What's ready
<pre-filled data, drafts, analysis — everything the VM/human needs>

## Exact next step for VM/human
<the concrete action>

## Expected value (honest)
<lottery odds / saves-money / unknown — never inflated>
```

## Types the worker writes

- `sweepstakes-<slug>.md` — pre-filled entry packet (requirements analyzed,
  red flags noted). Next step: open in a browser and enter.
- `freebie-candidates.md` — appended batches of new freebie links found by
  the deal scan. Next step: VM freebie pipeline claims them.
- `referral-placement-<slug>.md` — placement opportunities the box found but
  cannot post to (needs login). Written only when the worker spots one.

## What never lands here

Purchases, anything requiring a credit card, anything pay-to-enter. The box
does not do money-out, ever.
