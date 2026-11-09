# SubSync for macOS Apple Silicon

SubSync synchronizes subtitles with audio or with another subtitle track.
This maintained fork runs natively on Apple Silicon and preserves the familiar
interface and synchronization algorithm.

- Native macOS ARM64; no Rosetta dependency.
- FFmpeg 9.0.2 and PocketSphinx 5.1.1 with documented compatibility fixes.
- 46 interface languages: the union of 24 official EU languages and the
  45 subtitle-selector languages. Translations are machine-assisted drafts;
  native-language corrections are welcome.
- Free and open source under GPLv3. All features are available without payment.

## Download

Download the compiled DMG from [release 1.0](https://github.com/kmihalj/subsync/releases/tag/1.0).
It contains `SubSync ARM.app` and an Applications shortcut.
The current community build is ad-hoc signed and is not Apple notarized.
See the installation notes in the release and DMG for first-launch instructions.

## Development

The single maintained version is on `main` and targets macOS ARM64 only.
See [build and validation details](doc/macos-modern-deps.md).

Fork author and maintainer: **[Krešimir Mihalj (kmihalj)](https://github.com/kmihalj)**.
This fork adds native macOS ARM support, current media/speech libraries,
compatibility improvements and expanded interface translations.

Original SubSync author: **[Michał Szymaniak (sc0ty)](https://github.com/sc0ty/subsync)**.
Original copyright notices and third-party licenses are retained.

## Support development

The application remains free. Optional support helps maintain this native Mac
version: [GitHub Sponsors](https://github.com/sponsors/kmihalj).
