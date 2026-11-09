#!/bin/bash
set -Eeuo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BUILD=${SUBSYNC_BUILD_ROOT:-$ROOT/.build}
PREFIX=${SUBSYNC_DEPS_PREFIX:-$BUILD/modern-prefix}
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
export PKG_CONFIG_LIBDIR="$PKG_CONFIG_PATH"
mkdir -p "$BUILD/tests"
read -r -a PC_FLAGS <<< "$(pkg-config --cflags --libs pocketsphinx)"
"${CC:-clang}" -std=c11 -O1 -Wall -Wextra -Werror -arch arm64 \
    -mmacosx-version-min=11.0 -Wl,-rpath,"$PREFIX/lib" \
    "$ROOT/gizmo/test/cep-tail.c" "${PC_FLAGS[@]}" -lm -o "$BUILD/tests/cep-tail-test"
"$BUILD/tests/cep-tail-test" "$PREFIX/share/pocketsphinx/model/en-us"
