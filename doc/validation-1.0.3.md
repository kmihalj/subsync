# SubSync 1.0.3 validation

Both DMGs contain SubSync.app 1.0.3 build 4 for Apple Silicon. They share
the same native runtime libraries and synchronization engine. Both bundles
passed the ARM64, dependency, localization, minimum macOS 11.0 metadata,
and strict ad hoc signature checks on macOS 27.2.1.

| Check | Result |
| --- | --- |
| Standard on a clean profile | Downloaded the English speech model and English–Croatian dictionary, verified their signatures and saved them locally. The SRT for a 20-minute film excerpt was byte-identical to 1.0.2. |
| Full Offline on a clean profile with networking denied | Used the bundled English model and English–Croatian dictionary. The film output matched Standard byte for byte. The profile contained no downloaded catalog or models. |
| Offline graphical interface with networking denied | Completed synchronization and saved a 24-cue SRT from a synthetic English recording. The SRT matched 1.0.2 byte for byte. |
| Bundled content | All 226 original archives passed signature verification. The installed Offline bundle contains all nine model descriptors, 217 dictionaries and the source notices. |
| Model and dictionary checks | The native decoder accepted and processed a short audio sample with each of the nine models. The Italian model also processed synthetic Italian speech. The Czech–English dictionary loaded successfully. These checks measure loading and decoding. The full alignment regression uses English audio. |
| Automated tests | 36 macOS tests, 13 localization tests and 5 version tests passed. The 433 core assertions and original-packet media and speech tests passed. |

The installed application and original preferences matched their pre-test
snapshots. The film and subtitle fixtures stayed in the local test workspace.
[Language data and license notices](offline-assets.md) · [1.0 validation](validation-1.0.md)
