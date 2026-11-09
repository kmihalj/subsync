#!/bin/bash
# Compile and run deterministic timing properties against the isolated PS5 build.
set -Eeuo pipefail
source "$(dirname "$0")/native-test-common.sh"
native_test_require_ffmpeg avformat avcodec avutil
MODEL_FIXTURE=$(native_test_speech_model speech-invariance)
trap 'rm -rf "$MODEL_FIXTURE"' EXIT
"${CXX:-clang++}" -std=c++14 -O1 -arch arm64 -mmacosx-version-min=11.0 \
    "${NATIVE_TEST_CFLAGS[@]}" \
    "$ROOT/gizmo/test/speech-invariance.cpp" "$ROOT/gizmo/media/speechrec.cpp" \
    "$ROOT/gizmo/general/exception.cpp" "$ROOT/gizmo/text/words.cpp" \
    "$ROOT/gizmo/text/utf8.cpp" "$FRONTEND_ARCHIVE" \
    "${NATIVE_TEST_LDFLAGS[@]}" -lavformat -lavcodec -lavutil -lpocketsphinx \
    -o "$BUILD/tests/speech-invariance-test"
"$BUILD/tests/speech-invariance-test" "$MODEL_FIXTURE" "$TEST_PCM"
