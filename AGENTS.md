# Project scope

Maintain a native macOS ARM64 fork of sc0ty/SubSync. Keep the existing wxPython
interface and CPU synchronization/correlation algorithm. Other platforms are
outside the maintained scope.

Never modify or replace `/Applications/subsync.app`, its original preferences
under `~/Library/Preferences/subsync`, or original Plex media/subtitle files.
Builds, downloaded sources, copied models, test outputs and private media
excerpts belong in ignored `.build/`, `.venv/`, `build/` or `dist/` directories.

`macos-arm64` preserves the legacy speech engine for behavioral comparisons.
Keep FFmpeg/PocketSphinx API and speech/VAD modernization in
`experimental/modern-deps` until its output has been compared with the legacy
build. Do not change matching thresholds merely to make a comparison pass.

Use separate app names, bundle identifiers and profiles for each variant.
Keep the upstream Intel application updater disabled.

For changed media/recognition code, run the meaningful media integration tests
and isolated synchronization comparisons. Verify final bundles with
`tools/macos/verify-bundle.py` and launch them with Python/dyld overrides unset.
Keep copyrighted media and model data out of Git and uploaded artifacts.
Public validation notes should describe private fixtures without their paths.

See `doc/macos-arm64.md` and, on the experimental branch,
`doc/macos-modern-deps.md` for build and validation commands.
