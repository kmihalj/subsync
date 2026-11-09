# SubSync 1.0 validation

Validated on Apple M1 / macOS 27.2. The app targets macOS 11.0 and newer;
older supported OS releases have not been tested on hardware.

## Native engine

FFmpeg 9.0.2, PocketSphinx 5.1.1 and the owned compatibility frontend remain
unchanged from the validated v3 recognition engine. The public 1.0 candidate
passed all nine complete synchronization cases with Python/dyld overrides
cleared. All SRT outputs were byte-identical to v3.

Maximum subtitle-time differences from the original Intel app:

| Fixture | Difference |
| --- | ---: |
| Text offset/rate drift | 0 ms |
| Generated English speech | 2 ms |
| Original 20-minute AAC 5.1 excerpt | 24 ms |
| E-AC3 5.1 excerpt, offset/rate drift | 203 / 202 ms |
| AC3 5.1 excerpt, offset/rate drift | 165 / 31 ms |
| AC3 stereo excerpt, offset/rate drift | 249 / 154 ms |

Film values measure agreement with the original, not absolute timing accuracy.
Generated speech remains within 9 ms of known timing. Matching thresholds and
minimum point counts are unchanged. The original app/preferences and all
source media/subtitles remained unchanged in protection checks. Private films,
captions and copied model data are not included in Git or release assets.

The inherited dependence of adaptation on decoder packet boundaries is
intentional; exact cross-packet word-score equality is not claimed.

## Interface and packaging

- 46 UI languages, 45 compiled catalogs with 394 messages each plus English.
- The set is the union of 45 media-selector languages and 24 official EU
  languages; Irish is the additional member. Media support stays unchanged.
- Format fields, filename-pattern tokens, whitespace, newlines, mnemonics,
  author attribution and GNU MO round trips are checked for every catalog.
- 12 localization tests pass; native Settings/selector and About construction
  for all 46 languages preserves both author credits and fits the test display.
- Packaged visual checks covered Croatian, German, Arabic and Hebrew; native
  framework menus can follow the OS language. No full RTL layout mirroring is
  claimed on wxCocoa. Translations are machine-assisted drafts for community
  linguistic review.
- All 28 Mach-O files in both public and sandbox-preview bundles are arm64;
  dependency closure, numeric versions, 46-language metadata and deep/strict
  signatures are checked. Full Python/PSF, pybind11, PyInstaller, frontend and
  native-library notices are included.

## Optional sandbox preparation

34 boundary/caller/native-wx tests pass, including independent review of
permission lifetimes, revoked grants, YAML/output names, error/cancel cleanup
and unchanged public behavior. The native BusyDlg timer is exercised with a
real wx event loop.

A real ad-hoc-signed App Sandbox preview also completed this workflow:

1. Native dialogs selected two synthetic English SRT files.
2. GUI synchronization found 24 points; a save dialog and explicit writable
   output-directory grant produced 24 cues within 20 ms of known timing.
3. A fresh CLI process reused all three stored grants and produced the same
   successful 24-cue/20 ms result without new authorization.
4. A separate unselected test file was denied and created no output.

This does not establish paid App Store distribution-signing or App Review
approval. No Apple membership was purchased. The community DMG remains
ad-hoc signed and unnotarized; first-launch instructions accompany it.
