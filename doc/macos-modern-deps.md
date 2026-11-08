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
