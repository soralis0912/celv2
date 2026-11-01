#!/usr/bin/env bash
# Builds AVM v1.0.0 as a plain (non-LTO) static library for the Linux build (clang, nasm).
set -euo pipefail
. "$(dirname "$0")/env.sh"
command -v nasm >/dev/null || { echo 'nasm not found (apt install nasm)' >&2; exit 1; }
cc="${CELV2_AVM_CC:-clang}" cxx="${CELV2_AVM_CXX:-clang++}"
# __FILE__ in AVM and its TFLite dependencies says avm/... instead of the full path (and the user name in it).
map="-ffile-prefix-map=$AVM_ROOT=avm"
cmake -S "$AVM_ROOT" -B "$AVM_LIB_BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER="$cc" -DCMAKE_CXX_COMPILER="$cxx" \
  -DCMAKE_C_FLAGS="$map" -DCMAKE_CXX_FLAGS="$map" \
  -DENABLE_TESTS=0 -DENABLE_DOCS=0
# avmenc pulls in every third-party library (TFLite, absl, ...) that libavm.a's objects reference;
# avmdec is for scripts/bench_vs_avm.sh.
cmake --build "$AVM_LIB_BUILD" --target avmenc avmdec --parallel "$JOBS"
ls -l "$AVM_LIB_BUILD/libavm.a"
