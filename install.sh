#!/bin/bash
# install.sh — installs the token-free mission-keepalive systemd timers.
# Re-run after any VM replacement: unit files live in /etc (ephemeral),
# this script and everything it needs lives in ~ (persistent).
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

unit() { # $1=name $2=script $3=description
cat > "/etc/systemd/system/mission-keepalive-$1.service" <<EOF
[Unit]
Description=mission-keepalive: $3
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=$ROOT
ExecStart=/usr/bin/python3 $ROOT/scripts/$2
StandardOutput=append:$ROOT/logs/$1.log
StandardError=append:$ROOT/logs/$1.log
EOF
}

timer() { # $1=name $2=calendar|interval $3=spec
if [ "$2" = "calendar" ]; then
spec="OnCalendar=$3"
else
# Intervals map to repeating OnCalendar expressions. A bare
# OnUnitActiveSec= fires ONCE per timer-unit activation and never re-arms
# (verified 2026-10-15: heartbeat/referral/contest ran only at install time),
# so it must not be used for repeating watchers.
case "$3" in
  15min) spec="OnCalendar=*:0/15" ;;
  30min) spec="OnCalendar=*:0/30" ;;
  6h)    spec="OnCalendar=*-*-* 00/6:00:00" ;;
  *) echo "unknown interval: $3" >&2; exit 1 ;;
esac
fi
cat > "/etc/systemd/system/mission-keepalive-$1.timer" <<EOF
[Unit]
Description=mission-keepalive timer: $1

[Timer]
$spec
Persistent=true

[Install]
WantedBy=timers.target
EOF
}

mkdir -p "$ROOT/logs"
unit heartbeat heartbeat.py "proof-of-life heartbeat"
unit referral referral_watch.py "referral pool watch (B3NYLG)"
unit contest contest_watch.py "contest deadline watch"
unit placement placement_digest.py "placement health digest"

timer heartbeat interval 15min
timer referral interval 30min
timer contest interval 6h
timer placement calendar "*-*-* 08:00:00 UTC"

systemctl daemon-reload
for t in heartbeat referral contest placement; do
  # restart (not just enable --now): an already-active timer keeps its old
  # in-memory schedule after daemon-reload unless restarted
  systemctl enable "mission-keepalive-$t.timer"
  systemctl restart "mission-keepalive-$t.timer"
done
echo "installed. Active timers:"
systemctl list-timers 'mission-keepalive-*' --no-pager
