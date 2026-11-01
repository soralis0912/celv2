#!/usr/bin/env bash
# Runs CTest. Usage: scripts/test.sh [-R regex]
set -euo pipefail
. "$(dirname "$0")/env.sh"
exec ctest --test-dir "$CELV2_ROOT/build" --output-on-failure -j "${CTEST_JOBS:-4}" "$@"
