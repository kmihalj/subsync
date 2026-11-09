#!/bin/bash
set -euo pipefail
BASE=$(cd "$(dirname "$0")/.." && pwd)
APP_NAME=${SUBSYNC_APP_NAME:-SubSync ARM}
DIST=${SUBSYNC_DIST_DIR:-$BASE/dist}
APP=${SUBSYNC_APP_PATH:-$DIST/$APP_NAME.app}
VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")
DMG_NAME=${SUBSYNC_DMG_NAME:-${APP_NAME// /-}-$VERSION-arm64.dmg}
[[ "$DMG_NAME" != */* && "$DMG_NAME" == *.dmg ]] || { echo 'DMG name must be a .dmg filename' >&2; exit 1; }
mkdir -p "$BASE/.build" "$DIST"
STAGING=$(mktemp -d "$BASE/.build/dmg.XXXXXX")
trap 'rm -rf "$STAGING"' EXIT
ditto "$APP" "$STAGING/$APP_NAME.app"
ln -s /Applications "$STAGING/Applications"
cp "$BASE/resources/README-FIRST.txt" "$STAGING/README FIRST.txt"
hdiutil create -ov -format UDZO -volname "$APP_NAME" \
    -srcfolder "$STAGING" "$DIST/$DMG_NAME"
