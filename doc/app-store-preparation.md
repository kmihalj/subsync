# Optional Mac App Store preparation

The public release is a free, native ARM64 community app distributed in a DMG.
It does not require an Apple account to build or run. The optional store target
uses the same maintained code and engine on `main`.

## Local preview

```sh
SUBSYNC_DISTRIBUTION=appstore \
SUBSYNC_RELEASE_VERSION=1.0 \
tools/macos/build-app.sh
```

This produces an ad-hoc signed `SubSync ARM Store Preview.app`, with a separate
bundle identifier. It is a development artifact, not an approved App Store app.
The packaged `SubSyncDistribution` property controls policy; a frozen public app
ignores environment attempts to switch it into store mode.

The preview includes:

- App Sandbox, user-selected read/write, app-scoped bookmark and network-client
  entitlements, without broad filesystem or root privileges.
- A container-aware profile/model directory obtained through public Foundation
  APIs. It never automatically imports the original app's preferences.
- Public CoreFoundation security-scoped bookmarks for explicitly selected files
  and directories; balanced access lifetimes for probing, background jobs,
  cancellation, output files, batch directories and YAML task files.
- Explicit output-directory authorization for derived/collision-adjusted names;
  a YAML path alone is not an authorization grant.
- Stale/revoked-grant recovery and persisted grants across launches.
- Signed speech/dictionary data downloads; executable updater entries are
  filtered and application self-updating is disabled.
- Three-part marketing version, independent numeric build, category and
  advertised metadata for all 46 UI languages.

Public mode keeps the existing profile and file-path behavior. It does not
load bookmark frameworks or create a bookmark store for normal file access.

## Checks and limits

Unit/caller tests cover scope ownership, Unicode paths, reference counts,
threading, stale bookmarks, moved paths, revoked grants, YAML imports, output
patterns, error/cancel cleanup and unchanged public behavior. Native wx tests
also exercise the BusyDlg timer and modal event loop. Real sandbox-preview
checks are recorded in the release validation report.

An externally configured log file is not automatically granted access; denied
external logging falls back to stderr. A container-local log path works.

## Before a real submission

A paid Apple Developer membership, appropriate distribution/installer
certificates, App Store Connect registration, any required provisioning profile,
production signing and Apple review are still required. No account enrollment,
payment, certificate purchase or App Store upload has been performed.

The GPLv3 application and all dependencies/models also require a licensing
review against the current distribution terms before submission. This technical
preview does not change licenses or assert Apple approval.

Apple references:
- https://developer.apple.com/app-store/review/guidelines/
- https://developer.apple.com/documentation/security/app-sandbox
- https://developer.apple.com/documentation/foundation/nsurl/startaccessingsecurityscopedresource()
- https://developer.apple.com/documentation/bundleresources/information-property-list/cfbundleversion
