#!/bin/bash
# Build the original SubSync speech engine and compatible media libraries for
# Apple Silicon. Nothing is installed outside this checkout's .build directory.
set -Eeuo pipefail
trap 'status=$?; if [[ -n ${CURRENT_LOG:-} ]]; then tail -n 70 "$CURRENT_LOG" >&2; fi; exit "$status"' ERR

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BUILD="$ROOT/.build"
SOURCES="$BUILD/src-legacy"
PREFIX="$BUILD/legacy-prefix"
TOOL_PREFIX="$BUILD/legacy-tools"
LOGS="$BUILD/logs"
JOBS=${JOBS:-$(sysctl -n hw.logicalcpu)}
export MACOSX_DEPLOYMENT_TARGET=${MACOSX_DEPLOYMENT_TARGET:-11.0}
export CC=${CC:-clang}
export CXX=${CXX:-clang++}
export PATH="$TOOL_PREFIX/bin:/opt/homebrew/bin:$PATH"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
# Avoid accidentally linking a legacy dependency against a Homebrew library.
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig"
export CFLAGS="-O2 -arch arm64 -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET"
export CXXFLAGS="$CFLAGS"
export LDFLAGS="-arch arm64 -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET"

if [[ $(uname -s) != Darwin || $(uname -m) != arm64 ]]; then
    echo "Run this build natively on an Apple Silicon Mac." >&2
    exit 1
fi
mkdir -p "$SOURCES" "$PREFIX" "$TOOL_PREFIX" "$LOGS"
for tool in curl tar shasum make autoconf pkg-config; do
    command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
done
if command -v glibtoolize >/dev/null; then
    export LIBTOOLIZE=glibtoolize
elif command -v libtoolize >/dev/null; then
    export LIBTOOLIZE=libtoolize
else
    echo "GNU libtoolize is required (Apple's libtool is a different tool)." >&2
    exit 1
fi

fetch() {
    local name=$1 url=$2 digest=$3
    if [[ ! -f "$SOURCES/$name" ]]; then
        curl --fail --location --retry 3 --output "$SOURCES/$name.part" "$url"
        mv "$SOURCES/$name.part" "$SOURCES/$name"
    fi
    printf '%s  %s\n' "$digest" "$SOURCES/$name" | shasum -a 256 -c -
}

run_logged() {
    local name=$1
    shift
    echo "Building $name (log: $LOGS/$name.log)"
    CURRENT_LOG="$LOGS/$name.log"
    "$@" >"$CURRENT_LOG" 2>&1
    echo "Finished $name"
    CURRENT_LOG=
}

AUTOMAKE_VERSION=1.18.1
FFMPEG_VERSION=4.4.8
SPHINXBASE_COMMIT=617e53691889336a482631380f75b453445d0dae
POCKETSPHINX_COMMIT=5da71f0a05350c923676b02a69423d1291825d5b
fetch "automake-$AUTOMAKE_VERSION.tar.xz" \
    "https://ftp.gnu.org/gnu/automake/automake-$AUTOMAKE_VERSION.tar.xz" \
    168aa363278351b89af56684448f525a5bce5079d0b6842bd910fdd3f1646887
fetch "ffmpeg-$FFMPEG_VERSION.tar.xz" \
    "https://ffmpeg.org/releases/ffmpeg-$FFMPEG_VERSION.tar.xz" \
    c73848c4ae283d9eaee7be3b276affbc3543380483555500d0dd2c9b7e1c39c3
fetch "sphinxbase-$SPHINXBASE_COMMIT.tar.gz" \
    "https://codeload.github.com/cmusphinx/sphinxbase/tar.gz/$SPHINXBASE_COMMIT" \
    d09942840bd8c70c7fc19396407c37def1342f6f8ad08671e1e2a70561aa3829
fetch "pocketsphinx-$POCKETSPHINX_COMMIT.tar.gz" \
    "https://codeload.github.com/cmusphinx/pocketsphinx/tar.gz/$POCKETSPHINX_COMMIT" \
    1bfc90ae0ec7e3bfa6f4d26d8ec8df60b6834e531849fa8fb3821ca9e901bc9a

build_automake() {
    tar -xf "$SOURCES/automake-$AUTOMAKE_VERSION.tar.xz" -C "$SOURCES"
    cd "$SOURCES/automake-$AUTOMAKE_VERSION"
    ./configure --prefix="$TOOL_PREFIX"
    make -j "$JOBS"
    make install
}
if [[ ! -x "$TOOL_PREFIX/bin/automake" ]]; then
    run_logged legacy-automake build_automake
fi

build_ffmpeg() {
    tar -xf "$SOURCES/ffmpeg-$FFMPEG_VERSION.tar.xz" -C "$SOURCES"
    cd "$SOURCES/ffmpeg-$FFMPEG_VERSION"
    # Keep the complete built-in demuxer, parser, audio and subtitle decoder set.
    # SubSync does not encode or mux media, nor use FFmpeg devices/filters.
    ./configure --prefix="$PREFIX" --arch=aarch64 --target-os=darwin \
        --cc="$CC" --cxx="$CXX" --enable-shared --disable-static \
        --disable-autodetect --enable-securetransport --enable-iconv --disable-programs \
        --disable-doc --disable-encoders --disable-muxers --disable-devices \
        --disable-filters --extra-cflags="$CFLAGS" --extra-ldflags="$LDFLAGS" \
        --extra-libs=-liconv
    make -j "$JOBS"
    make install
}
if [[ ! -f "$PREFIX/.ffmpeg-$FFMPEG_VERSION-built" ]]; then
    run_logged legacy-ffmpeg build_ffmpeg
    touch "$PREFIX/.ffmpeg-$FFMPEG_VERSION-built"
fi

build_sphinxbase() {
    tar -xf "$SOURCES/sphinxbase-$SPHINXBASE_COMMIT.tar.gz" -C "$SOURCES"
    cd "$SOURCES/sphinxbase-$SPHINXBASE_COMMIT"
    NOCONFIGURE=1 ./autogen.sh
    ./configure --prefix="$PREFIX" --host=aarch64-apple-darwin \
        --with-python=no --without-lapack --enable-shared --disable-static
    make -j "$JOBS"
    make install
}
if [[ ! -f "$PREFIX/.sphinxbase-$SPHINXBASE_COMMIT-built" ]]; then
    run_logged legacy-sphinxbase build_sphinxbase
    touch "$PREFIX/.sphinxbase-$SPHINXBASE_COMMIT-built"
fi

build_pocketsphinx() {
    tar -xf "$SOURCES/pocketsphinx-$POCKETSPHINX_COMMIT.tar.gz" -C "$SOURCES"
    cd "$SOURCES/pocketsphinx-$POCKETSPHINX_COMMIT"
    NOCONFIGURE=1 ./autogen.sh
    ./configure --prefix="$PREFIX" --host=aarch64-apple-darwin \
        --with-python=no --enable-shared --disable-static
    make -j "$JOBS"
    make install
}
if [[ ! -f "$PREFIX/.pocketsphinx-$POCKETSPHINX_COMMIT-built" ]]; then
    run_logged legacy-pocketsphinx build_pocketsphinx
    touch "$PREFIX/.pocketsphinx-$POCKETSPHINX_COMMIT-built"
fi

for library in "$PREFIX"/lib/*.dylib; do
    [[ -L "$library" ]] && continue
    if [[ $(lipo -archs "$library") != arm64 ]]; then
        echo "Expected an arm64-only dependency: $library" >&2
        exit 1
    fi
done
mkdir -p "$PREFIX/share/licenses/ffmpeg" "$PREFIX/share/licenses/sphinxbase" \
    "$PREFIX/share/licenses/pocketsphinx"
cp "$SOURCES/ffmpeg-$FFMPEG_VERSION/LICENSE.md" \
    "$SOURCES/ffmpeg-$FFMPEG_VERSION/COPYING.LGPLv2.1" \
    "$PREFIX/share/licenses/ffmpeg/"
cp "$SOURCES/sphinxbase-$SPHINXBASE_COMMIT/LICENSE" "$PREFIX/share/licenses/sphinxbase/"
cp "$SOURCES/pocketsphinx-$POCKETSPHINX_COMMIT/LICENSE" "$PREFIX/share/licenses/pocketsphinx/"
cp "$ROOT/tools/macos/legacy-deps.json" "$PREFIX/share/licenses/legacy-deps.json"
pkg-config --modversion libavcodec libavformat libswresample sphinxbase pocketsphinx
echo "Native legacy dependencies ready: $PREFIX"
