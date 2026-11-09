#!/bin/bash
# Run owned frontend input-boundary and upstream overflow regressions.
set -Eeuo pipefail
source "$(dirname "$0")/native-test-common.sh"
AWFUL_WAV=${SUBSYNC_TEST_AWFUL_WAV:-$PS_SOURCE/test/data/awful.wav}
if [[ ! -f "$AWFUL_WAV" ]]; then
    printf 'Missing upstream overflow fixture: %s\n' "$AWFUL_WAV" >&2
    exit 1
fi
"${CC:-clang}" -std=c17 -O1 -arch arm64 -mmacosx-version-min=11.0 \
    "${NATIVE_TEST_CFLAGS[@]}" "$ROOT/gizmo/test/frontend-invalid.c" \
    "$FRONTEND_ARCHIVE" "${NATIVE_TEST_LDFLAGS[@]}" -lpocketsphinx \
    -o "$BUILD/tests/frontend-invalid-test"
"$BUILD/tests/frontend-invalid-test" "$AWFUL_WAV"
