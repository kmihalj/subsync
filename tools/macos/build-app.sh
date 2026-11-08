#!/bin/bash
# Build entirely inside this checkout; never install into /Applications.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
if [[ $(uname -s) != Darwin || $(uname -m) != arm64 ]]; then
    echo 'This build requires an Apple Silicon Mac running native arm64.' >&2
    exit 1
fi
export MACOSX_DEPLOYMENT_TARGET=${MACOSX_DEPLOYMENT_TARGET:-11.0}
export ARCHFLAGS='-arch arm64'
export UV_CACHE_DIR="$ROOT/.build/cache"
export UV_PYTHON_INSTALL_DIR="$ROOT/.build/python"
export UV_PYTHON_BIN_DIR="$ROOT/.build/bin"
export PYTHONNOUSERSITE=1
export SUBSYNC_CONFIG_DIR="$ROOT/.build/build-profile"
mkdir -p "$ROOT/.build/logs"
if [[ ! -x .build/bootstrap/bin/uv ]]; then
    python3 -m venv .build/bootstrap
    .build/bootstrap/bin/python -m pip install 'uv==0.13.7'
fi
UV="$ROOT/.build/bootstrap/bin/uv"
if [[ ! -x .build/bin/python3.12 ]]; then
    "$UV" python install '3.12.16'
fi
if [[ ! -x .venv/bin/python ]]; then
    "$UV" venv --python "$ROOT/.build/bin/python3.12" .venv
fi
PYTHON="$ROOT/.venv/bin/python"
"$UV" pip sync --python "$PYTHON" tools/macos/requirements-build.txt
export PATH="$ROOT/.venv/bin:$ROOT/.build/bin:$PATH"
PREFIX=${SUBSYNC_DEPS_PREFIX:-$ROOT/.build/legacy-prefix}
DEPS_SCRIPT=${SUBSYNC_DEPS_SCRIPT:-$ROOT/tools/macos/build-deps-legacy.sh}
"$DEPS_SCRIPT"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig"
export DYLD_LIBRARY_PATH="$PREFIX/lib"
cp subsync/config.py.template subsync/config.py
"$PYTHON" setup.py build_ext --inplace
"$PYTHON" setup.py gen_version
"$PYTHON" -c 'import platform, gizmo; assert platform.machine() == "arm64"; print("Native gizmo:", gizmo.__file__)'
make -C gizmo/test -j4
"$PYTHON" -m PyInstaller --noconfirm --clean macos.spec
APP_NAME=${SUBSYNC_APP_NAME:-SubSync ARM}
"$PYTHON" tools/macos/verify-bundle.py "dist/$APP_NAME.app"
tools/package-macos.sh
echo "Built: $ROOT/dist/$APP_NAME.app"
