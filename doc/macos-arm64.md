# Native macOS ARM64 development

This fork maintains the existing wxPython interface, text correlation and
synchronization flow for Apple Silicon. It does not replace the speech engine
with another recognizer.

## Branches

- `macos-arm64`: first native build using FFmpeg 4.4.8 and the legacy
  SphinxBase/PocketSphinx API, for comparison with upstream SubSync 0.17.0.
- `experimental/modern-deps`: separate experiment using current FFmpeg and
  PocketSphinx, including adaptation of utterance detection and timestamps.
  A successful compile alone does not establish equivalent synchronization.

## Build on an Apple Silicon Mac

Install Xcode Command Line Tools and provide `python3`, `autoconf`, `pkg-config`
and GNU libtool (`glibtoolize`). Build tools and runtime dependencies are then
installed in `.build/` and `.venv/` within the checkout.

```sh
git clone https://github.com/kmihalj/subsync.git
cd subsync
git switch macos-arm64
tools/macos/build-app.sh
```

The build script pins an ARM Python runtime and Python packages, builds native
libraries from the checksummed sources recorded in
`tools/macos/legacy-deps.json`, compiles the extension, runs existing core tests,
then packages and verifies the `.app` and creates a `.dmg` in `dist/`.
The initial deployment target is macOS 11; actual compatibility with older
macOS versions still requires testing on those systems.

The output is `dist/SubSync ARM.app`, with executable
`Contents/MacOS/subsync`. Builds are signed locally with an ad hoc signature;
Developer ID signing and Apple notarization are not part of this first build.

## Separate application and settings

The build never installs or replaces `/Applications/subsync.app`.
Its bundle identifier is `org.kmihalj.subsync.arm64`; its default profile is
`~/Library/Application Support/SubSync ARM`. It cannot install the upstream
Intel updater. The signed upstream language-model feed remains available.

Copy existing models and dictionaries without changing the original:

```sh
.venv/bin/python tools/macos/import-assets.py
```

This copies only missing destinations and does not migrate personal settings.
For isolated tests or another profile, set `SUBSYNC_CONFIG_DIR` to a separate
directory; models belong in its `assets/` subdirectory.

## Verification

```sh
make -C gizmo/test
.venv/bin/python tools/macos/verify-bundle.py 'dist/SubSync ARM.app'
```

The bundle check rejects any non-arm64 Mach-O binary, absolute non-system
library links, a misleading minimum-OS declaration and invalid signatures.
All required libraries must be included in the app.

Synchronization regression fixtures, private media excerpts and build logs
stay in ignored `.build/`; no user media or downloaded models are committed.
Run `tools/macos/check-sync.py --help` for the comparison fixture commands.

### Initial validation (2026-11-09)

Tested on an Apple M1 running macOS 27.2. The standalone app contains 30
arm64-only Mach-O files. Code signing, internal library resolution, symlinks
and minimum-OS metadata pass the bundle verifier. No build-directory or
Homebrew runtime libraries are required.

All 433 assertions in the five existing C++ core test cases pass. The packaged
app was also tested with Python and dynamic-library override variables unset:

| Fixture | Maximum output timing difference from original Intel 0.17.0 |
| --- | ---: |
| Subtitles with a known offset and 1.5% playback-rate drift | 0 ms |
| Generated English speech, 118.93 seconds | 0 ms |
| Private film excerpt: 20 minutes of English 5.1 audio and 221 Croatian cues | 1 ms |

The real film test produced the same 36 synchronization points and correction
formula as the original. Existing film subtitle timings are not ground truth;
this test measures equivalence to the original application's output.
It is a sample comparison, not a claim of exhaustive media compatibility or
a performance benchmark. The original app and preferences/models were
unchanged by content hash.

The main window, settings, synchronization options and batch window open
successfully. An actual GUI synchronization also completed successfully.
Only integer conversions required by newer wxPython controls were added;
the UI layout and synchronization settings are preserved.

## License

Upstream SubSync remains GPLv3; see `LICENSE`. Native dependency sources and
license notices are recorded by the dependency build scripts. A distributable
release must include the corresponding source and notices for its components.
