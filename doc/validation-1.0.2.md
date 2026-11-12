# SubSync 1.0.2 validation

Empty subtitle and reference fields show a localized drop hint. The main window
accepts file drops on both input rows and their labels. The stream selector
accepts drops on its path field and Browse button when file selection is enabled.
It loads the selected file after the drop callback returns.

The hint was checked in both native input fields for all 46 interface languages.
Each of the 45 compiled catalogs contains 396 messages. Catalog checks,
13 localization tests, 5 version tests and 34 macOS tests passed. A simulated file
drop in the native stream dialog replaced the selected subtitle and left the
read-only stream selector protected. The maintainer approved the test build for
release. The automated dialog test supplies the drop to the registered target.

The release uses the same application bundle as the test DMG. The bundle passed
the standalone verifier with 28 ARM64 Mach-O files, minimum macOS 11.0 metadata,
build 3 and a valid ad hoc signature. It was launched on macOS 27.2.1 with an
isolated profile and development library paths unset.

The 27 native runtime libraries and extensions are byte-identical to 1.0.1.
The packaged subtitle-to-subtitle smoke test reproduced the 1.0 output timings
exactly and stayed within 20 ms of known fixture timing. The broader speech and
media test results are recorded in the [1.0 validation](validation-1.0.md).
