# Project scope

Maintain a native macOS ARM64 fork of sc0ty/SubSync. Keep the existing wxPython
interface and CPU synchronization/correlation algorithm. Other platforms are
outside the maintained scope.

Never modify or replace `/Applications/subsync.app`, its original preferences
under `~/Library/Preferences/subsync`, or original Plex media/subtitle files.
Builds, downloaded sources, copied models, test outputs and private media
excerpts belong in ignored `.build/`, `.venv/`, `build/` or `dist/` directories.

The single maintained version lives on `main` and uses the current FFmpeg
and PocketSphinx engine with the owned compatibility frontend. Do not change
matching thresholds merely to make a comparison pass. Do not link or bundle
deprecated SphinxBase, SphinxAD or legacy PocketSphinx libraries. Historical
libraries and immutable old app snapshots are test-only references in .build.

Keep generated apps inside the project; never install over the Intel app.
The public app is named `SubSync.app` at the user's request. Retain its separate
bundle identifier and profile so it cannot use the installed Intel app's data.
Keep the upstream Intel application updater disabled.

For changed media/recognition code, run the meaningful media integration tests
and isolated synchronization comparisons. Verify final bundles with
`tools/macos/verify-bundle.py` and launch them with Python/dyld overrides unset.
Keep copyrighted media and model data out of Git and uploaded artifacts.
Public validation notes should describe private fixtures without their paths.

See `doc/macos-modern-deps.md` for build and validation commands.
