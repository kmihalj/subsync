#!/bin/bash
# Build owned, namespaced DSP into a static archive, with no legacy library.
set -Eeuo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BUILD=${SUBSYNC_FRONTEND_BUILD:-$ROOT/.build/native-frontend}
PS_PREFIX=${SUBSYNC_PS_PREFIX:-${SUBSYNC_DEPS_PREFIX:-$ROOT/.build/modern-prefix}}
mkdir -p "$BUILD/obj" "$BUILD/lib"
OBJECTS=()
for source in "$ROOT"/gizmo/frontend/fe/*.c "$ROOT"/gizmo/frontend/util/*.c "$ROOT"/gizmo/frontend/native_frontend.c; do
    name=$(basename "$source" .c)
    OBJECTS+=("$BUILD/obj/$name.o")
    clang -std=c17 -O2 -arch arm64 -mmacosx-version-min=11.0 \
        -fvisibility=hidden -DHAVE_CONFIG_H -I"$ROOT/gizmo/frontend" -I"$PS_PREFIX/include" \
        -include "$ROOT/gizmo/frontend/symbol_prefix.h" \
        -c "$source" -o "$BUILD/obj/$name.o"
done
rm -f "$BUILD/lib/libsubsyncfrontend.a"
ar rcs "$BUILD/lib/libsubsyncfrontend.a" "${OBJECTS[@]}"
printf 'Owned frontend archive: %s\n' "$BUILD/lib/libsubsyncfrontend.a"
