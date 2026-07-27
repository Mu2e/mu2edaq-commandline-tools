#!/usr/bin/env bash
# stop-mu2edaq-commandline-tools.sh -- stop anything left running by
# start-mu2edaq-commandline-tools.sh and clean up its temporary files.
#
# Sends SIGTERM, waits, then SIGKILL if the process is still alive.
#
# Usage: ./stop-mu2edaq-commandline-tools.sh [options]
#
# Options:
#   --timeout SECS   seconds to wait for a clean exit before SIGKILL (default 10)
#   --keep-logs      do not remove the log directory
#   -h, --help       show this help and exit
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="${MU2EDAQ_TOOLS_PIDFILE:-$HERE/.mu2edaq-tools.pid}"
LOGDIR="${MU2EDAQ_TOOLS_LOG_DIR:-$HERE/logs}"
TIMEOUT=10
KEEP_LOGS=0

while [ $# -gt 0 ]; do
    case "$1" in
        --timeout)   shift; TIMEOUT="${1:?--timeout requires seconds}" ;;
        --keep-logs) KEEP_LOGS=1 ;;
        -h|--help)   grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)           echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        echo "==> Stopping mu2edaq-tools (pid $PID)"
        kill -TERM "$PID" 2>/dev/null || true
        waited=0
        while kill -0 "$PID" 2>/dev/null && [ "$waited" -lt "$TIMEOUT" ]; do
            sleep 1
            waited=$((waited + 1))
        done
        if kill -0 "$PID" 2>/dev/null; then
            echo "    still alive after ${TIMEOUT}s, sending SIGKILL"
            kill -KILL "$PID" 2>/dev/null || true
        fi
    else
        echo "==> Stale pidfile (pid ${PID:-unknown} not running)"
    fi
    rm -f "$PIDFILE"
else
    echo "==> Nothing to stop (no $PIDFILE)"
fi

find "$HERE" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
if [ "$KEEP_LOGS" = 0 ] && [ -d "$LOGDIR" ]; then
    echo "==> Removing $LOGDIR"
    rm -rf "$LOGDIR"
fi

echo "Done."
