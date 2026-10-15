#!/data/data/com.termux/files/usr/bin/bash
# install-termux.sh — one-shot installer for the mission-keepalive Android TV
# package. Run INSIDE Termux on the Android TV box:
#
#   curl -sL https://raw.githubusercontent.com/midnightmichigan/mission-keepalive/main/android-tv/install-termux.sh | bash
#
# What it does:
#   1. Installs python (via pkg) if missing.
#   2. Downloads this package (android-tv/) from the public GitHub repo.
#   3. Pulls the latest data snapshots (contest queue, placement log).
#   4. Installs the Termux:Boot autostart entry (needs the Termux:Boot app).
#   5. Acquires a wake lock and starts the watcher loop in the background.
# Pure stdlib Python, $0, no accounts, no keys.
set -e

REPO_RAW="https://raw.githubusercontent.com/midnightmichigan/mission-keepalive/main"
REPO_ZIP="https://github.com/midnightmichigan/mission-keepalive/archive/refs/heads/main.zip"
DEST="$HOME/mission-keepalive-androidtv"

echo "=== mission-keepalive Android TV installer ==="

# 1. python
if ! command -v python3 >/dev/null 2>&1; then
  echo "[1/5] installing python..."
  pkg update -y >/dev/null 2>&1 || true
  pkg install -y python
else
  echo "[1/5] python3 already installed: $(python3 --version 2>&1)"
fi
if ! command -v unzip >/dev/null 2>&1; then
  echo "      installing unzip..."
  pkg install -y unzip >/dev/null 2>&1 || true
fi

# 2. download package
echo "[2/5] downloading package..."
rm -rf "$DEST"
mkdir -p "$DEST"
cd "$DEST"
curl -sL --fail "$REPO_ZIP" -o mk.zip
unzip -o -q mk.zip "mission-keepalive-main/android-tv/*"
# move android-tv/* up one level (dotfiles included)
cp -r mission-keepalive-main/android-tv/. "$DEST"/
rm -rf mk.zip mission-keepalive-main

# 3. latest data snapshots
echo "[3/5] refreshing data snapshots..."
mkdir -p data
curl -sL --fail "$REPO_RAW/data/contests-queue-snapshot.md" -o data/contests-queue-snapshot.md
curl -sL --fail "$REPO_RAW/data/referral-placements-snapshot.md" -o data/referral-placements-snapshot.md
chmod +x run.sh scripts/*.py .boot/00-mission-keepalive

# 4. Termux:Boot autostart (needs the Termux:Boot app installed from F-Droid)
echo "[4/5] setting up autostart on reboot..."
mkdir -p "$HOME/.termux/boot"
cp .boot/00-mission-keepalive "$HOME/.termux/boot/00-mission-keepalive"
chmod +x "$HOME/.termux/boot/00-mission-keepalive"
if [ -d /data/data/com.termux.boot ]; then
  echo "      Termux:Boot app detected."
else
  echo "      NOTE: Termux:Boot app not detected. For auto-start after a"
  echo "      reboot, also install 'Termux:Boot' from F-Droid (same place"
  echo "      you got Termux). The watchers still run until reboot without it."
fi

# 5. wake lock + start
echo "[5/5] starting watchers..."
termux-wake-lock
# stop any previous copy first (idempotent re-install)
pkill -f "mission-keepalive-androidtv/run.sh" 2>/dev/null || true
sleep 1
nohup bash "$DEST/run.sh" >>"$DEST/logs/runner.log" 2>&1 &
disown 2>/dev/null || true

echo ""
echo "=== installed and running ==="
echo "Watchers: heartbeat 15m | referral 30m | contests 6h | placements 24h"
echo "Check status:  tail -n 20 $DEST/logs/runner.log"
echo "Latest results: ls $DEST/status/"
echo "Alerts land in: $DEST/alerts/  (open with any file manager)"
echo "Stop:           pkill -f mission-keepalive-androidtv/run.sh"
echo "Uninstall:      pkill -f mission-keepalive-androidtv/run.sh; termux-wake-unlock; rm -rf $DEST"
