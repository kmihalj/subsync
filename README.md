# SubSync for macOS ARM64

This fork focuses on native Apple Silicon builds while preserving SubSync's
existing wxPython interface and synchronization algorithm.

- `macos-arm64`: compatibility build using the original speech recognition API.
- `experimental/modern-deps`: separate FFmpeg / PocketSphinx modernization.

Current branch build instructions and validation status:
[modern macOS ARM64](doc/macos-modern-deps.md). This branch uses FFmpeg 9.0.2
and PocketSphinx 5.1.1 with documented compatibility corrections; deprecated
SphinxBase libraries are not required or bundled.

## Upstream deprecation notice
The original project is no longer actively maintained.

For details see [#197](https://github.com/sc0ty/subsync/issues/197).
