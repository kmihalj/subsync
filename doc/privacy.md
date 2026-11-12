# Privacy

SubSync processes selected video, audio and subtitle files locally on your Mac.
It does not upload their contents, perform cloud transcription, require an
account, include advertising, or send analytics/crash reports to the maintainer.

The app retrieves the asset catalog from GitHub over HTTPS. It can contact the
locations listed in the catalog to download speech models and translation
dictionaries, and verifies each downloaded archive's signature before installing
it. Those hosts receive normal network request information, such as your IP
address. Opening project or GitHub Sponsors links uses your browser and the
privacy policies of those services.

Preferences, downloaded model data and optional diagnostic logs are stored
locally. Logs and user-exported diagnostic word lists can contain filenames or
recognized/subtitle words; inspect them before choosing to share a report.
The optional sandbox build additionally stores local security-scoped bookmarks
for files/directories you authorize. These grants are not sent to the maintainer.

You choose output locations. The application writes synchronized subtitles
only as requested; keeping a copy of your input subtitles remains useful.

Privacy questions and issue reports:
https://github.com/kmihalj/subsync/issues
