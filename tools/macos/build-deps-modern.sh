#!/bin/bash
# Experimental modern dependencies, confined to this checkout's .build.
set -Eeuo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BUILD=${SUBSYNC_BUILD_ROOT:-$ROOT/.build}
SOURCES="$BUILD/modern-sources"
PREFIX=${SUBSYNC_DEPS_PREFIX:-$BUILD/modern-prefix}
JOBS=${JOBS:-6}
export MACOSX_DEPLOYMENT_TARGET=${MACOSX_DEPLOYMENT_TARGET:-11.0}
export PATH="$ROOT/.venv/bin:$PATH"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig"
export CC=${CC:-clang}
export CXX=${CXX:-clang++}
export CFLAGS="-O2 -arch arm64 -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET"
export LDFLAGS="-arch arm64 -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET"
if [[ $(uname -s) != Darwin || $(uname -m) != arm64 ]]; then
    echo 'Run natively on an Apple Silicon Mac.' >&2
    exit 1
fi
for tool in curl tar shasum make pkg-config cmake ninja patch; do
    command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 1; }
done
mkdir -p "$SOURCES" "$PREFIX" "$BUILD/logs"
fetch() {
    local name=$1 url=$2 digest=$3
    if [[ ! -f "$SOURCES/$name" ]]; then
        curl --fail --location --retry 3 --output "$SOURCES/$name.part" "$url"
        mv "$SOURCES/$name.part" "$SOURCES/$name"
    fi
    printf '%s  %s\n' "$digest" "$SOURCES/$name" | shasum -a 256 -c -
}
FFMPEG_VERSION=9.0.2
POCKETSPHINX_VERSION=5.1.1
PS_PATCH="$ROOT/tools/macos/patches/pocketsphinx-5.1.1-cep-tail.patch"
PS_PATCH_SHA256=bd7e04b8a0a8a0f063de03cdb0076d941f00a9b0de67d1e97d5305be23288bde
printf '%s  %s\n' "$PS_PATCH_SHA256" "$PS_PATCH" | shasum -a 256 -c -
PS_MARKER="$PREFIX/.pocketsphinx-$POCKETSPHINX_VERSION-cep-$PS_PATCH_SHA256"
fetch "ffmpeg-$FFMPEG_VERSION.tar.xz" \
    "https://ffmpeg.org/releases/ffmpeg-$FFMPEG_VERSION.tar.xz" \
    8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e
fetch "pocketsphinx-$POCKETSPHINX_VERSION.tar.gz" \
    "https://codeload.github.com/cmusphinx/pocketsphinx/tar.gz/refs/tags/v$POCKETSPHINX_VERSION" \
    e2db414eb66618cd0a98de77507db32517a48f6900b06bfb94c0acc4bef5761d
if [[ ! -f "$PREFIX/.ffmpeg-$FFMPEG_VERSION" ]]; then
    tar -xf "$SOURCES/ffmpeg-$FFMPEG_VERSION.tar.xz" -C "$SOURCES"
    (
        cd "$SOURCES/ffmpeg-$FFMPEG_VERSION"
        ./configure --prefix="$PREFIX" --arch=aarch64 --target-os=darwin \
            --cc="$CC" --cxx="$CXX" --enable-shared --disable-static \
            --disable-autodetect --enable-iconv --enable-securetransport --extra-libs=-liconv \
            --disable-doc --disable-debug --disable-programs \
            --extra-cflags="$CFLAGS" --extra-ldflags="$LDFLAGS"
        make -j "$JOBS"
        make install
    ) >"$BUILD/logs/modern-ffmpeg.log" 2>&1
    touch "$PREFIX/.ffmpeg-$FFMPEG_VERSION"
fi
if [[ ! -f "$PS_MARKER" ]]; then
    # A patch-specific source/build directory prevents a previous unpatched
    # install marker or CMake cache from silently reusing a different decoder.
    PS_SOURCE="$SOURCES/pocketsphinx-$POCKETSPHINX_VERSION-subsync-$PS_PATCH_SHA256"
    mkdir -p "$PS_SOURCE"
    tar -xf "$SOURCES/pocketsphinx-$POCKETSPHINX_VERSION.tar.gz" \
        --strip-components=1 -C "$PS_SOURCE"
    patch --batch --forward -p1 -d "$PS_SOURCE" < "$PS_PATCH"
    (
        cmake -S "$PS_SOURCE" -B "$PS_SOURCE/build-subsync" -G Ninja \
            -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES=arm64 \
            -DCMAKE_OSX_DEPLOYMENT_TARGET="$MACOSX_DEPLOYMENT_TARGET" \
            -DCMAKE_INSTALL_PREFIX="$PREFIX" -DCMAKE_INSTALL_NAME_DIR="$PREFIX/lib" \
            -DBUILD_SHARED_LIBS=ON -DBUILD_TESTING=OFF
        cmake --build "$PS_SOURCE/build-subsync" -j "$JOBS"
        cmake --install "$PS_SOURCE/build-subsync"
    ) >"$BUILD/logs/modern-pocketsphinx.log" 2>&1
    touch "$PS_MARKER"
fi
mkdir -p "$PREFIX/share/licenses/ffmpeg" "$PREFIX/share/licenses/pocketsphinx"
cp "$SOURCES/ffmpeg-$FFMPEG_VERSION/COPYING.LGPLv2.1" \
    "$SOURCES/ffmpeg-$FFMPEG_VERSION/LICENSE.md" "$PREFIX/share/licenses/ffmpeg/"
tar -xOf "$SOURCES/pocketsphinx-$POCKETSPHINX_VERSION.tar.gz" \
    "pocketsphinx-$POCKETSPHINX_VERSION/LICENSE" > "$PREFIX/share/licenses/pocketsphinx/LICENSE"
cp "$PS_PATCH" "$PREFIX/share/licenses/pocketsphinx/"
cp "$ROOT/tools/macos/modern-deps.json" "$PREFIX/share/licenses/"
pkg-config --modversion libavcodec pocketsphinx
printf 'Native dependency prefix: %s\n' "$PREFIX"
