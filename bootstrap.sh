#!/usr/bin/env bash
# bootstrap.sh -- create/refresh the local Python virtual environment for
# mu2edaq-commandline-tools and install the package into it, and optionally
# configure and build the C++ library and tools with CMake.
#
# Usage: ./bootstrap.sh [options]
#
# Options:
#   --dev            also install the dev extras (pytest)
#   --cpp            configure and build the CMake targets under build/
#   --clean          remove venv/ and build/ before doing anything
#   --python PATH    interpreter to build the venv with (default: $PYTHON or python3)
#   --version        print the package version and exit
#   -h, --help       show this help and exit
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/venv"
BUILD="$HERE/build"
DEV=0
CPP=0
CLEAN=0
PYTHON="${PYTHON:-python3}"

version() {
    sed -n 's/^__version__ = "\(.*\)"/\1/p' \
        "$HERE/src/mu2edaq_commandline_tools/__init__.py"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --dev)     DEV=1 ;;
        --cpp)     CPP=1 ;;
        --clean)   CLEAN=1 ;;
        --python)  shift; PYTHON="${1:?--python requires a path}" ;;
        --version) echo "mu2edaq-commandline-tools $(version)"; exit 0 ;;
        -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)         echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

if [ "$CLEAN" = 1 ]; then
    echo "Removing $VENV and $BUILD"
    rm -rf "$VENV" "$BUILD"
fi

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "error: $PYTHON not found. Install Python 3.9+ first." >&2
    exit 1
fi

PYVER=$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || {
    echo "error: Python >= 3.9 required, found $PYVER" >&2; exit 1;
}
echo "Using Python $PYVER at $(command -v "$PYTHON")"

[ -d "$VENV" ] || "$PYTHON" -m venv "$VENV"
VPY="$VENV/bin/python"
[ -x "$VPY" ] || VPY="$VENV/Scripts/python.exe"   # Windows layout

"$VPY" -m pip install --quiet --upgrade pip setuptools wheel

if [ "$DEV" = 1 ]; then
    "$VPY" -m pip install --editable "$HERE[dev]"
else
    "$VPY" -m pip install --editable "$HERE"
fi

if [ "$CPP" = 1 ]; then
    if ! command -v cmake >/dev/null 2>&1; then
        echo "error: cmake not found; skip --cpp or install CMake 3.16+." >&2
        exit 1
    fi
    cmake -S "$HERE" -B "$BUILD" -DCMAKE_BUILD_TYPE=RelWithDebInfo
    cmake --build "$BUILD" -j "$( (nproc || sysctl -n hw.ncpu) 2>/dev/null | head -1 )"
fi

echo
echo "mu2edaq-commandline-tools $(version) ready."
echo "  source $VENV/bin/activate && mu2edaq-tools list"
[ "$CPP" = 1 ] && echo "  $BUILD/mu2edaq-tools-info --paths"
exit 0
