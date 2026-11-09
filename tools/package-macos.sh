#!/bin/bash
set -euo pipefail
BASE=$(cd "$(dirname "$0")/.." && pwd)
APP_NAME=${SUBSYNC_APP_NAME:-SubSync ARM}
APP="$BASE/dist/$APP_NAME.app"
VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")
mkdir -p "$BASE/.build" "$BASE/dist"
STAGING=$(mktemp -d "$BASE/.build/dmg.XXXXXX")
trap 'rm -rf "$STAGING"' EXIT
ditto "$APP" "$STAGING/$APP_NAME.app"
ln -s /Applications "$STAGING/Applications"
cp "$BASE/resources/README-FIRST.txt" "$STAGING/README FIRST.txt"
hdiutil create -ov -format UDZO -volname "$APP_NAME" \
    -srcfolder "$STAGING" "$BASE/dist/${APP_NAME// /-}-$VERSION-arm64.dmg"
