# Install SubSync for macOS Apple Silicon

Download the DMG from [the current release](https://github.com/kmihalj/subsync/releases/latest),
open it, and drag `SubSync ARM.app` into Applications. The current community
build is ad-hoc signed and is not notarized by Apple; see the release notes
for the macOS first-launch approval process.

Only native macOS ARM64 is maintained. No Rosetta or separately installed
Python/FFmpeg/PocketSphinx is needed to run the compiled app.

For building from source, see [the Mac build guide](macos-modern-deps.md).
