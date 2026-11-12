#!/bin/bash
set -euo pipefail
BASE=$(cd "$(dirname "$0")/.." && pwd)
APP_NAME=${SUBSYNC_APP_NAME:-SubSync}
DIST=${SUBSYNC_DIST_DIR:-$BASE/dist}
APP=${SUBSYNC_APP_PATH:-$DIST/$APP_NAME.app}
VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")
BUNDLED=$(/usr/libexec/PlistBuddy -c 'Print :SubSyncBundledAssets' "$APP/Contents/Info.plist" 2>/dev/null || true)
if [[ "$BUNDLED" == true ]]; then
    SUFFIX=-offline
    VARIANT='Offline'
else
    SUFFIX=''
    VARIANT='Standard'
fi
DMG_NAME=${SUBSYNC_DMG_NAME:-${APP_NAME// /-}-$VERSION-arm64$SUFFIX.dmg}
[[ "$DMG_NAME" != */* && "$DMG_NAME" == *.dmg ]] || { echo 'DMG name must be a .dmg filename' >&2; exit 1; }
mkdir -p "$BASE/.build" "$DIST"
STAGING=$(mktemp -d "$BASE/.build/dmg.XXXXXX")
trap 'rm -rf "$STAGING"' EXIT
ditto "$APP" "$STAGING/$APP_NAME.app"
ln -s /Applications "$STAGING/Applications"
sed -e "s/@VERSION@/$VERSION/g" -e "s/@VARIANT@/$VARIANT/g" \
    "$BASE/resources/README-FIRST.txt" > "$STAGING/README FIRST.txt"
VOLUME_NAME=$APP_NAME
if [[ "$BUNDLED" == true ]]; then
    VOLUME_NAME="$APP_NAME Offline"
fi
hdiutil create -ov -format UDZO -volname "$VOLUME_NAME" \
    -srcfolder "$STAGING" "$DIST/$DMG_NAME"
