#!/bin/bash
set -Eeuo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BUILD=${SUBSYNC_BUILD_ROOT:-$ROOT/.build}
PREFIX="$BUILD/modern-prefix"
PS_SOURCE="$BUILD/modern-sources/pocketsphinx-5.1.1"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
export PKG_CONFIG_LIBDIR="$PKG_CONFIG_PATH"
mkdir -p "$BUILD/tests"
# pkg-config output consists solely of paths under the build prefix.
read -r -a PC_FLAGS <<< "$(pkg-config --cflags --libs libavformat libavcodec libavutil libswresample pocketsphinx)"
"${CXX:-clang++}" -std=c++14 -O1 -arch arm64 -mmacosx-version-min=11.0 \
    -Wl,-rpath,"$PREFIX/lib" -I"$ROOT/gizmo" "${PC_FLAGS[@]}" \
    "$ROOT/gizmo/test/modern-media.cpp" \
    "$ROOT/gizmo/media/speechrec.cpp" "$ROOT/gizmo/media/resampler.cpp" \
    "$ROOT/gizmo/media/stream.cpp" "$ROOT/gizmo/general/exception.cpp" \
    "$ROOT/gizmo/text/words.cpp" "$ROOT/gizmo/text/utf8.cpp" \
    -o "$BUILD/tests/modern-media-test"
"$BUILD/tests/modern-media-test" "$PREFIX/share/pocketsphinx/model/en-us" \
    "$PS_SOURCE/test/data/goforward.raw"
