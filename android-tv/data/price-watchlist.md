# Price watchlist — for the Android TV worker
The worker fetches each URL, extracts the first $ price it finds, and writes
an alert to alerts/ when the price is at or below your target.

Row format (in code block so the worker doesn't read this line as a row):
```
- [ ] **Product name** | https://example.com/product | target $29.99 | note
```

Rules:
- Only pages that show the price in plain HTML work (no login walls, no
  JavaScript-only prices). If a page never yields a price after 3 checks, the
  worker marks it STALE-CHECK and stops wasting fetches on it.
- This SAVES money on things you were going to buy anyway — it is not income.
- Add your own rows with any file manager on the box, one per line.

## Your watchlist (add rows below)
- [ ] [EXAMPLE] **Example headphones** | https://example.com/headphones | target $49.99 | EXAMPLE ROW — replace with a real product you want
