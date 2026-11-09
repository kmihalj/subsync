#!/bin/bash
# Shared paths for standalone tests. The search library and FFmpeg may use
# separate isolated prefixes while the public CEP patch is being validated.
# This file is sourced; it never rebuilds the app or its frontend archive.
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
BUILD=${SUBSYNC_BUILD_ROOT:-$ROOT/.build}
DEPS_PREFIX=${SUBSYNC_DEPS_PREFIX:-$BUILD/modern-prefix}
PS_PREFIX=${SUBSYNC_PS_PREFIX:-$DEPS_PREFIX}
if [[ -n "${SUBSYNC_PS_SOURCE:-}" ]]; then
    PS_SOURCE=$SUBSYNC_PS_SOURCE
elif [[ -f "$PS_PREFIX/.subsync-pocketsphinx-source" ]]; then
    PS_SOURCE=$(< "$PS_PREFIX/.subsync-pocketsphinx-source")
else
    PS_SOURCE="$BUILD/modern-sources/pocketsphinx-5.1.1"
fi
FRONTEND_BUILD=${SUBSYNC_FRONTEND_BUILD:-$ROOT/.build/native-frontend}
FRONTEND_ARCHIVE="$FRONTEND_BUILD/lib/libsubsyncfrontend.a"
TEST_MODEL=${SUBSYNC_TEST_MODEL:-$PS_PREFIX/share/pocketsphinx/model/en-us}
TEST_PCM=${SUBSYNC_TEST_PCM:-$PS_SOURCE/test/data/goforward.raw}

if [[ ! -f "$FRONTEND_ARCHIVE" ]]; then
    printf 'Missing frontend archive: %s\nBuild it with tools/macos/build-native-frontend.sh first.\n' "$FRONTEND_ARCHIVE" >&2
    exit 1
fi
if [[ ! -f "$PS_PREFIX/include/pocketsphinx.h" || ! -f "$PS_PREFIX/lib/libpocketsphinx.dylib" ]]; then
    printf 'Missing PocketSphinx prefix: %s\n' "$PS_PREFIX" >&2
    exit 1
fi
mkdir -p "$BUILD/tests"
NATIVE_TEST_CFLAGS=(-I"$ROOT/gizmo" -I"$PS_PREFIX/include" -I"$DEPS_PREFIX/include")
NATIVE_TEST_LDFLAGS=(-L"$PS_PREFIX/lib" -Wl,-rpath,"$PS_PREFIX/lib")
if [[ "$DEPS_PREFIX" != "$PS_PREFIX" ]]; then
    NATIVE_TEST_LDFLAGS+=(-L"$DEPS_PREFIX/lib" -Wl,-rpath,"$DEPS_PREFIX/lib")
fi

native_test_speech_model() {
    # The bundled model's feat.params forces remove_noise=yes during ps_init,
    # overriding the recognizer option and making the disabled-noise test a
    # duplicate. Keep all acoustic/model data unchanged; omit just that default
    # from an isolated test copy so both requested preprocessing modes run.
    local original destination asset name
    original=$(cd "$TEST_MODEL" && pwd) || return 1
    destination=$(mktemp -d "$BUILD/tests/$1-model.XXXXXX") || return 1
    mkdir "$destination/en-us"
    for asset in "$original"/*; do
        name=$(basename "$asset")
        [[ "$name" == en-us ]] || ln -s "$asset" "$destination/$name"
    done
    for asset in "$original/en-us"/*; do
        name=$(basename "$asset")
        if [[ "$name" == feat.params ]]; then
            awk '$1 != "-remove_noise"' "$asset" > "$destination/en-us/feat.params"
        else
            ln -s "$asset" "$destination/en-us/$name"
        fi
    done
    printf '%s\n' "$destination"
}

native_test_require_ffmpeg() {
    local library
    for library in "$@"; do
        if [[ ! -f "$DEPS_PREFIX/lib/lib$library.dylib" || ! -d "$DEPS_PREFIX/include/lib$library" ]]; then
            printf 'Missing isolated FFmpeg dependency: %s/lib/lib%s.dylib\n' "$DEPS_PREFIX" "$library" >&2
            return 1
        fi
    done
}
