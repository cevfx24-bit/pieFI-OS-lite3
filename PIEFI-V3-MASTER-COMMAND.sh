#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$HOME/piefi-build-v3"
LOG="$ROOT/build-piefi-v3-updated.log"
STATUS="$ROOT/build-piefi-v3-updated.status"
PIDFILE="$ROOT/build-piefi-v3-updated.pid"
[[ -d "$ROOT" ]] || { echo "ERROR: Missing $ROOT"; exit 1; }
[[ -x "$ROOT/pieFi-V3-build.sh" ]] || chmod +x "$ROOT/pieFi-V3-build.sh"
[[ -f "$HOME/piefi-build/openwrt-imagebuilder-25.12.6-x86-64.Linux-x86_64/Makefile" ]] || { echo "ERROR: Existing ImageBuilder missing; no build started."; exit 1; }
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then echo "Build already running; log: $LOG"; exit 0; fi
rm -f "$STATUS"
nohup bash -c 'ROOT="$HOME/piefi-build-v3"; cd "$ROOT" || exit 1; ulimit -c 0; env PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" MAKEFLAGS="-j1" ./pieFi-V3-build.sh; RC=$?; printf "%s\n" "$RC" > "$ROOT/build-piefi-v3-updated.status"; exit "$RC"' > "$LOG" 2>&1 < /dev/null &
PID=$!; echo "$PID" > "$PIDFILE"
echo "PieFi V3 build started. PID=$PID; Log=$LOG; Output=$ROOT/output/PIEFI-V3-UPDATED"
