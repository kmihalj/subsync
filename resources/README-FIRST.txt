SubSync 1.0.2 — macOS Apple Silicon

INSTALL
Open this DMG and drag SubSync.app to Applications.
To keep an existing Intel SubSync.app, choose another folder such as
~/Applications instead of replacing it.
This is a native ARM64 app for Apple Silicon, with no Rosetta requirement.
Python, FFmpeg and PocketSphinx are included; separate installations are not needed.

FIRST LAUNCH
This community release is ad-hoc signed, but is not signed with a paid Apple
Developer ID and has not been notarized by Apple. macOS may therefore block
the first launch. If you trust this release and choose to approve it, first
attempt to open the app, then use System Settings > Privacy & Security >
Open Anyway. Follow Apple's instructions:
https://support.apple.com/102445

No script in this download changes your system security settings.

LANGUAGES AND MODELS
The interface offers 46 languages. The first run uses the system language;
you can choose another language in Settings and restart the app.
Drop a subtitle or reference file from Finder onto the corresponding input.
Translations are machine-assisted drafts; native-language corrections are welcome.
Interface languages are separate from speech-recognition models. Required
models and translation dictionaries are offered for download when needed.
English audio with Croatian subtitles is covered by the regression tests.
Other catalog models have not all been runtime-tested in this fork.

PRIVACY
Audio, video and subtitle processing stays on your Mac. Model/catalog downloads
require network access. Source media and subtitles are not uploaded.
See https://github.com/kmihalj/subsync/blob/main/doc/privacy.md

FREE SOFTWARE AND SUPPORT
All features are free. Optional support: https://github.com/sponsors/kmihalj
Source and issue reports: https://github.com/kmihalj/subsync

Fork author and maintainer: Krešimir Mihalj (kmihalj)
Original SubSync author: Michał Szymaniak (sc0ty)
GPLv3; original and third-party notices are included in the application.

HRVATSKI
Povucite SubSync.app u Applications.
Ako čuvate postojeću Intel aplikaciju, novu stavite u drugu mapu, npr.
~/Applications, kako je ne biste zamijenili.
Ovo izdanje nije Apple notarizirano; za prvo pokretanje, ako mu vjerujete,
odobrite ga kroz Postavke sustava > Privatnost
i sigurnost > Svejedno otvori. Jezik sučelja mijenja se u postavkama aplikacije.
Aplikacija je besplatna; dobrovoljna podrška razvoju dostupna je preko Sponsors.
