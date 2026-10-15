# Put the mission watchers + AI worker on your Android TV box

This puts a small watchdog AND a real AI worker on your TV box. The watchers
check four things on a schedule (code listings, contest deadlines, link
health, plus a proof-of-life ping). The worker uses free AI (no cost, no
tokens) to draft outreach emails, prep sweepstakes entries, spot price drops,
find new freebies, and generate ideas. Everything it makes lands in folders
for review — the box never sends, enters, or buys anything itself.

You will need: your Android TV box, its remote, and Wi-Fi.

## Steps

**1. Install the Downloader app.**
On the TV box home screen, open the Play Store, search for "Downloader"
(orange icon), and install it.

**2. Open Downloader and allow installs.**
Open Downloader. If it asks to allow installing unknown apps, say yes.

**3. Install Termux.**
In Downloader's address bar, type exactly:

`https://f-droid.org/en/packages/com.termux/`

Press Go. Scroll down to the "Download APK" button and select it. When the
download finishes, choose Install, then Done.

**4. Install Termux:Boot (makes it survive reboots).**
In Downloader's address bar, type exactly:

`https://f-droid.org/en/packages/com.termux.boot/`

Download the APK and install it the same way.

**5. Open Termux.**
Find Termux in your apps list and open it. The first launch downloads its
base system — stay on this screen until you see a `$` prompt (about 1–2
minutes on Wi-Fi).

**6. Keep Termux awake.**
Go to the box's Settings → Apps → Termux → Battery, and set it to
"Unrestricted" (wording varies: "Don't optimize" / "Allow background
activity"). This stops the box from killing the watchers to save power.

**7. Run the one-line installer.**
In Termux, paste this single command and press Enter. (Long-press in Termux
to paste.)

```text
curl -sL https://raw.githubusercontent.com/midnightmichigan/mission-keepalive/main/android-tv/install-termux.sh | bash
```

Wait until it prints "installed and running" (about 1–3 minutes).

**8. Check that it works.**
Still in Termux, type:

```text
tail -n 20 ~/mission-keepalive-androidtv/logs/runner.log
```

You should see lines like "runner started" and "heartbeat ok". If you see
that, you're done — the watchers are running.

**9. Where results live.**
Everything is under `mission-keepalive-androidtv` in Termux's home folder:
`status/` has the latest check results, `alerts/` has anything that needs
attention, `drafts/` has AI-drafted emails waiting for review,
`pending-approval/` has sweepstakes packets and freebie finds,
`digests/` has a short daily summary. You can also view these with any
file-manager app on the box.

**10. Optional: give the box a free AI upgrade (2 minutes).**
The box's AI works out of the box with no setup. If you want a backup AI
source, do this once: on your phone or computer, go to openrouter.ai, sign
up free (no card needed), create a key, then in Termux type:

```text
cat > ~/mission-keepalive-androidtv/config.local.json << 'EOF'
{
  "openrouter_key": "PASTE-YOUR-KEY-HERE",
  "openrouter_model": "openrouter/free"
}
EOF
```

Long-press to paste your key over PASTE-YOUR-KEY-HERE. The key stays on the
box only — it is never uploaded anywhere.

**11. After a reboot.**
If you installed Termux:Boot (step 4), the watchers start by themselves when
the box restarts. If not, just open Termux and type:

```text
termux-wake-lock; nohup bash ~/mission-keepalive-androidtv/run.sh >/dev/null 2>&1 &
```

## Honest limits

- The watchers watch and report only. The worker drafts, analyzes, and
  monitors — but the box never sends emails, enters sweepstakes, creates
  accounts, solves CAPTCHAs, or spends money. Anything needing those lands in
  `pending-approval/` for review.
- Sweepstakes and contests are lottery odds — a prepped entry is a chance,
  not income. Price-drop alerts save money on planned purchases; they are not
  income either.
- It needs the box on and connected to Wi-Fi. If the box fully sleeps or
  loses power, checks pause until it wakes.
- The contest list it watches is a snapshot from install day. Re-run the
  command in step 7 any time to pull a fresh copy (it restarts cleanly).
