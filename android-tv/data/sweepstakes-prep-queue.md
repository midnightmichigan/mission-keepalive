# Sweepstakes prep queue — for the Android TV worker
The box CANNOT enter sweepstakes itself (most need JavaScript, accounts, or
CAPTCHAs). What it CAN do: fetch the entry page, figure out what's required,
and write a pre-filled entry packet to pending-approval/ so the VM or Dakota
can enter in one shot.

Row format (in code block so the worker doesn't read this line as a row):
```
- [ ] **Sweepstakes name** | https://example.com/enter | ends 12/31/26 | prize
```

Rules:
- The worker preps max 1 per run (inference is the bottleneck).
- Each packet states honestly what's required: account? CAPTCHA? purchase?
  If a packet needs anything paid or shady, the worker marks it SKIPPED with
  the reason instead of writing a packet.
- Expected value note: sweepstakes are lottery tickets. A packet is a chance,
  not income.

## Queue (add rows below)
- [ ] [EXAMPLE] **Example $500 Gift Card Sweepstakes** | https://example.com/sweeps | ends 12/31/26 | EXAMPLE ROW — $500 gift card
