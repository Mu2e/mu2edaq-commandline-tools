#!/usr/bin/env bash
# start-mu2edaq-commandline-tools.sh -- bring the venv up to date (creating it
# on first run) and hand off to the mu2edaq-tools dispatcher.
#
# Usage: ./start-mu2edaq-commandline-tools.sh [tool-arguments ...]
#
# Any arguments are passed straight through to mu2edaq-tools, so:
#   ./start-mu2edaq-commandline-tools.sh config --json
# is equivalent to `mu2edaq-tools config --json` inside the venv.
#
# Options handled here:
#   --no-update      skip the dependency refresh and start immediately
#   -h, --help       show this help and exit
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/venv"
PIDFILE="${MU2EDAQ_TOOLS_PIDFILE:-$HERE/.mu2edaq-tools.pid}"
UPDATE=1

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    grep '^#' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi
if [ "${1:-}" = "--no-update" ]; then
    UPDATE=0
    shift
fi

if [ ! -d "$VENV" ]; then
    echo "==> No venv yet, bootstrapping"
    "$HERE/bootstrap.sh"
elif [ "$UPDATE" = 1 ]; then
    echo "==> Refreshing dependencies"
    "$HERE/bootstrap.sh" >/dev/null
fi

VPY="$VENV/bin/python"
[ -x "$VPY" ] || VPY="$VENV/Scripts/python.exe"   # Windows layout

echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

exec "$VPY" -m mu2edaq_commandline_tools.cli "$@"
