# Experimental macOS ARM build with current libraries

This branch targets Apple Silicon only. It builds FFmpeg 9.0.2 and
PocketSphinx 5.1.1 from the sources and SHA256 hashes recorded in
`tools/macos/modern-deps.json`. No separate Sphinxbase library is used.

The original CPU word matching and correlation code and the graphical
interface remain in use. PocketSphinx 5 no longer provides the old decoder
voice-activity detection. This branch therefore uses its supported endpointer,
buffers incomplete 30 ms frames, and offsets each utterance's word times back
onto the media timeline. Recognition results can differ from the legacy
speech engine; compare real media before selecting this build for daily use.

The application uses the separate `SubSync ARM Modern` preference directory.
`SUBSYNC_CONFIG_DIR` can override it for isolated tests.
Existing `.speech` models and dictionaries are read through the existing asset
loader. Model data is not embedded in the application bundle.

## Build

From an Apple Silicon Mac, use the shared macOS build script with these
experimental selections:

```sh
SUBSYNC_APP_NAME='SubSync ARM Modern' \
SUBSYNC_BUNDLE_ID='org.kmihalj.subsync.arm64.modern' \
SUBSYNC_DEPS_PREFIX="$PWD/.build/modern-prefix" \
SUBSYNC_DEPS_SCRIPT="$PWD/tools/macos/build-deps-modern.sh" \
tools/macos/build-app.sh
```

The default minimum target is macOS 11.0. All build products stay inside the
checkout. The script does not replace an installed application.

## Regression checks

`tools/macos/test-modern-media.sh` builds a standalone native integration test.
It uses the downloaded PocketSphinx source's `goforward.raw` fixture and model
and checks silence, multiple utterances, nonzero media timestamps, EOF speech
drain, repeated flush, a discontinuity, custom stereo mixing and resampler
drain. It needs the dependencies produced by `build-deps-modern.sh`.

`make -C gizmo/test` runs the existing algorithm tests.
`tools/macos/check-sync.py` compares complete CLI synchronizations against the
original Intel application, using isolated preferences and output files. Run
it against the final packaged app as well as the source build.

### Initial packaged validation (2026-11-09)

Tested on Apple M1 / macOS 27.2, using the same copied models as the original
Intel application. The final bundle has 28 arm64-only Mach-O files; library
closure, minimum-OS metadata and deep/strict code signature checks pass.
It runs without Python or dynamic-library path overrides.

| Fixture | Maximum output timing difference from original Intel 0.17.0 |
| --- | ---: |
| Subtitle offset and 1.5% playback-rate drift | 0 ms |
| Generated English speech, 118.93 seconds | 17 ms |
| Private 20-minute English AAC 5.1 / Croatian subtitle excerpt | 483 ms |

All three packaged comparisons pass the documented regression tolerances,
and the original app and preferences/models are unchanged by content hash.
The modern recognizer's real-media output is measurably different; the
`macos-arm64` branch remains the preferred build for preserving existing
SubSync results. More representative film comparisons are needed before
promoting this experimental branch.

The 433 existing algorithm assertions pass. Additional native integration
checks cover silence, separated utterances, media timestamps, discontinuity,
EOF draining, repeated flush, 48 kHz to 16 kHz conversion and custom speaker
ordering. A reversed FR/FL layout with explicit RIGHT selection produces
the expected signal and exact final sample count.
