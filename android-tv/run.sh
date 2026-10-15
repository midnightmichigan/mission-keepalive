#!/data/data/com.termux/files/usr/bin/bash
# run.sh — foreground scheduler loop for mission-keepalive on Android TV (Termux).
# Android has no systemd, so this one loop replaces the four systemd timers:
# every TICK seconds it checks which watcher is due and runs it.
#
#   heartbeat watch : every 15 min  (HB_INT,  default 900)
#   referral watch  : every 30 min  (REF_INT, default 1800)
#   contest watch   : every 6 h     (CON_INT, default 21600)
#   placement digest: every 24 h    (PLC_INT, default 86400)
#   AI worker       : every 2 h     (WORKER_INT, default 7200)
#
# Env overrides (mainly for testing): HB_INT REF_INT CON_INT PLC_INT WORKER_INT TICK.
# Keeps running as long as Termux stays alive. Start it with:
#   termux-wake-lock && nohup bash ~/mission-keepalive-androidtv/run.sh >/dev/null 2>&1 &
# Stop it with:  pkill -f mission-keepalive-androidtv/run.sh
set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"
STATE="$ROOT/state"
LOGS="$ROOT/logs"
RUNLOG="$LOGS/runner.log"

HB_INT="${HB_INT:-900}"
REF_INT="${REF_INT:-1800}"
CON_INT="${CON_INT:-21600}"
PLC_INT="${PLC_INT:-86400}"
WORKER_INT="${WORKER_INT:-7200}"
TICK="${TICK:-60}"

mkdir -p "$STATE" "$LOGS"

log() {
  # log line to runner.log and stdout (stdout lands in boot.log under Termux:Boot)
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$RUNLOG"
}

due() { # $1 = job name, $2 = interval seconds -> exit 0 if due
  local f="$STATE/lastrun-$1"
  local now
  now=$(date +%s)
  if [ ! -f "$f" ]; then
    return 0
  fi
  local last
  last=$(cat "$f" 2>/dev/null || echo 0)
  # guard against non-numeric content
  case "$last" in
    ''|*[!0-9]*) last=0 ;;
  esac
  [ $(( now - last )) -ge "$2" ]
}

mark() { # $1 = job name -> record run time
  date +%s > "$STATE/lastrun-$1"
}

run_job() { # $1 = job name, $2 = script file
  log "starting $1"
  if python3 "$ROOT/scripts/$2" >>"$LOGS/$1.log" 2>&1; then
    mark "$1"
    log "$1 ok"
  else
    log "$1 FAILED (exit $?) - will retry next tick"
  fi
}

command -v python3 >/dev/null 2>&1 || {
  echo "python3 not found. Run install-termux.sh first." >&2
  exit 1
}

log "runner started (tick=${TICK}s hb=${HB_INT}s ref=${REF_INT}s contest=${CON_INT}s placement=${PLC_INT}s worker=${WORKER_INT}s)"

while true; do
  due heartbeat "$HB_INT"   && run_job heartbeat heartbeat.py
  due referral  "$REF_INT"  && run_job referral  referral_watch.py
  due contest   "$CON_INT"   && run_job contest   contest_watch.py
  due placement "$PLC_INT"  && run_job placement placement_digest.py
  due worker    "$WORKER_INT" && run_job worker   worker.py
  sleep "$TICK"
done
