#!/usr/bin/env bash
# Configures (first time) and builds celv2 into ./build. CUDA is used when nvcc is found
# (-DCELV2_CUDA=OFF in CELV2_CMAKE_ARGS to leave it out); without it decisions run on Vulkan or the CPU.
set -euo pipefail
. "$(dirname "$0")/env.sh"
# shellcheck disable=SC2086
cmake -S "$CELV2_ROOT" -B "$CELV2_ROOT/build" -G Ninja -DCMAKE_BUILD_TYPE=Release ${CELV2_CMAKE_ARGS:-}
cmake --build "$CELV2_ROOT/build" --parallel "$JOBS"
