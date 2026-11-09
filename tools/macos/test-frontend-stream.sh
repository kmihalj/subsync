#!/bin/bash
# Test frontend queue handling, EOF and callback-error recovery.
set -Eeuo pipefail
source "$(dirname "$0")/native-test-common.sh"
if [[ ! -f "$TEST_PCM" ]]; then
    printf 'Missing upstream PCM fixture: %s\n' "$TEST_PCM" >&2
    exit 1
fi
SANITIZER_FLAGS=(-fno-omit-frame-pointer)
if [[ -n "${SUBSYNC_TEST_SANITIZERS:-}" ]]; then
    SANITIZER_FLAGS+=(-fsanitize="$SUBSYNC_TEST_SANITIZERS")
fi
"${CC:-clang}" -std=c17 -O1 -g -arch arm64 -mmacosx-version-min=11.0 \
    "${SANITIZER_FLAGS[@]}" "${NATIVE_TEST_CFLAGS[@]}" \
    "$ROOT/gizmo/test/frontend-stream.c" "$FRONTEND_ARCHIVE" \
    "${NATIVE_TEST_LDFLAGS[@]}" -lpocketsphinx \
    -o "$BUILD/tests/frontend-stream-test"
"$BUILD/tests/frontend-stream-test" "$TEST_PCM"
