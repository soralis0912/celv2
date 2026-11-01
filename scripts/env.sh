# Environment for the Linux build scripts. Usage: . "$(dirname "$0")/env.sh"
# AVM v1.0.0 source tree: $AVM_ROOT, else ~/avm. Exported so CMake sees it too.
export AVM_ROOT="${AVM_ROOT:-$HOME/avm}"
AVM_LIB_BUILD="$AVM_ROOT/_build_lib"
CELV2_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JOBS="${JOBS:-$(nproc)}"
