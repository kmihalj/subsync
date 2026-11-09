# SubSync 1.0.1 validation

This patch adds the About window's optional **Support development** button,
opening `https://github.com/sponsors/kmihalj` in the default browser. It also
renames the public bundle to `SubSync.app`. Its bundle identifier and existing
native preference/model directory are preserved. The installed Intel app is
not replaced by the build or validation process.

## Interface

- 395 messages in each of the 45 compiled catalogs, plus built-in English:
  46 interface languages in total. Only the new button message was added;
  previous translations are unchanged. Machine-assisted translations remain
  drafts for native-language review.
- Catalog validation, GNU msgfmt and 13 localization tests pass.
- Actual wx Settings and About dialogs were checked for all 46 languages.
  The support button has a translated label, is enabled and visible, and fits
  both its parent and the test display. A dispatched button event opens the
  exact Sponsors URL, verified with a browser-launch spy.
- The final packaged app was launched on Apple M1 / macOS 27.2 through macOS,
  without development Python or dynamic-library path overrides. Croatian About
  displays version 1.0.1, both authors and **Podrži razvoj**. Clicking it opened
  the exact Sponsors URL in Safari. The app menu displays **SubSync**.
- Five version metadata tests and 34 macOS boundary/caller/native-wx tests pass.

## Native bundle and existing synchronization validation

The final public bundle passes the standalone bundle verifier: all 28 Mach-O
files are arm64-only, dependencies resolve within the app or macOS, the minimum
OS is 11.0, localization metadata advertises 46 languages, and deep/strict
signature verification succeeds. Marketing version is 1.0.1, build 2. Older
supported macOS releases have not been tested on hardware.

All 27 native runtime libraries/extensions are byte-identical to release 1.0,
including gizmo, all seven FFmpeg libraries and PocketSphinx. The main executable
has identical native sections; its embedded archive differs only in the About
module and version module. Synchronization code, settings and recognition
libraries are unchanged. The nine synchronization cases from the
[1.0 validation](validation-1.0.md) were not repeated for this interface-only
patch; their results remain the recorded engine regression evidence.

The community app is ad-hoc signed and not Apple notarized. Installation and
first-launch instructions accompany the DMG. This is not an App Store release.
