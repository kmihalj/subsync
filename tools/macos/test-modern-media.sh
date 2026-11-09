#!/bin/bash
# Pass --original-packets for the original streaming contract; the default
# and --strict-packets retain the stricter packet-invariance assertions.
set -Eeuo pipefail
source "$(dirname "$0")/native-test-common.sh"
native_test_require_ffmpeg avformat avcodec swresample avutil
MODEL_FIXTURE=$(native_test_speech_model modern-media)
trap 'rm -rf "$MODEL_FIXTURE"' EXIT
"${CXX:-clang++}" -std=c++14 -O1 -arch arm64 -mmacosx-version-min=11.0 \
    "${NATIVE_TEST_CFLAGS[@]}" \
    "$ROOT/gizmo/test/modern-media.cpp" \
    "$ROOT/gizmo/media/speechrec.cpp" "$ROOT/gizmo/media/resampler.cpp" \
    "$ROOT/gizmo/media/stream.cpp" "$ROOT/gizmo/general/exception.cpp" \
    "$ROOT/gizmo/text/words.cpp" "$ROOT/gizmo/text/utf8.cpp" "$FRONTEND_ARCHIVE" \
    "${NATIVE_TEST_LDFLAGS[@]}" -lavformat -lavcodec -lswresample -lavutil -lpocketsphinx \
    -o "$BUILD/tests/modern-media-test"
"$BUILD/tests/modern-media-test" "$MODEL_FIXTURE" "$TEST_PCM" "$@"
