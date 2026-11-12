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

Choose one DMG from the [latest release](https://github.com/kmihalj/subsync/releases/latest).

| Download | Which one should I choose? |
| --- | --- |
| **Standard** (`SubSync-…-arm64.dmg`) | Choose this for a smaller download and the full online language catalog. SubSync downloads each required speech model or dictionary the first time you use it and saves it for later. |
| **Offline** (`SubSync-…-arm64-offline.dmg`) | Choose this if you want to synchronize without an internet connection right away. This package includes nine speech models and 217 bilingual dictionaries. See the [included languages and data sources](doc/offline-assets.md). |

Both DMGs contain the same version of `SubSync.app` with the same interface and
synchronization engine. Drag the app from the DMG you choose to Applications.
The app uses a speech model for the language spoken in the reference audio and
a dictionary when the subtitle and reference languages differ. For example, a
Croatian subtitle synced to English audio uses the English model and the
English–Croatian dictionary.

[Upute na hrvatskom](doc/downloads-hr.md)

The current community build is ad-hoc signed and is not Apple notarized.
See the installation notes in the release and DMG for first-launch instructions.

## Development

The single maintained version is on `main` and targets macOS ARM64 only.
See [build and validation details](doc/macos-modern-deps.md),
[release validation](doc/validation-1.0.3.md),
[privacy information](doc/privacy.md) and the optional
[App Store preparation target](doc/app-store-preparation.md).

Fork author and maintainer: **[Krešimir Mihalj (kmihalj)](https://github.com/kmihalj)**.
This fork adds native macOS ARM support, current media/speech libraries,
compatibility improvements and expanded interface translations.

Original SubSync author: **[Michał Szymaniak (sc0ty)](https://github.com/sc0ty/subsync)**.
Original copyright notices and third-party licenses are retained.

## Support development

The application remains free. Optional support helps maintain this native Mac
version: [GitHub Sponsors](https://github.com/sponsors/kmihalj).
The About window also offers a **Support development** button that opens this
page in your browser.
