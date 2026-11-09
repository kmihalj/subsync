# Experimental macOS ARM build with current libraries

This branch targets Apple Silicon only. It builds FFmpeg 9.0.2 and
PocketSphinx 5.1.1 from the sources and SHA256 hashes recorded in
`tools/macos/modern-deps.json`. No separate Sphinxbase library is used.

The original CPU word matching, correlation code and graphical interface
remain in use. An owned, namespaced audio frontend retains the original
energy/SNR speech detection and streaming context while the current
PocketSphinx decoder performs recognition through its public CEP API.
Current PocketSphinx DSP implementations and explicitly attributed
compatibility code are compiled into SubSync; deprecated SphinxBase/SphinxAD
libraries and the old decoder are not linked or bundled. See
`gizmo/frontend/UPSTREAM.md` and the per-file provenance manifests.

PocketSphinx 5.1.1 has a small local correction for the public streaming CEP
API: utterance termination drains all dynamic-feature lookahead frames,
including when the output ring wraps. The source patch and its hash are
recorded in `tools/macos/modern-deps.json` and included in native licenses.
The fix leaves the raw PCM input path unchanged. No matching thresholds
are relaxed to obtain successful comparisons.

The application uses the separate `SubSync ARM Modern` preference directory.
`SUBSYNC_CONFIG_DIR` can override it for isolated tests.
Existing `.speech` models and dictionaries are read through the existing asset
loader. Model data is not embedded in the application bundle.

## Build

From an Apple Silicon Mac:

```sh
tools/macos/build-app.sh
```

On this experimental branch the default dependency script, prefix, app name
and bundle identifier all select the modern build. Optional
`SUBSYNC_DEPS_PREFIX` and `SUBSYNC_APP_NAME` overrides support isolated builds.
The historical build instructions belong to the `macos-arm64` branch.

The default minimum target is macOS 11.0. All build products stay inside the
checkout. The script does not replace an installed application.

## Regression checks

`tools/macos/test-modern-media.sh` builds a standalone native integration test.
It uses the downloaded PocketSphinx source's `goforward.raw` fixture and model
and checks silence, multiple utterances, nonzero media timestamps, EOF speech
drain, repeated flush, a discontinuity, custom stereo mixing and resampler
drain. It needs the dependencies produced by `build-deps-modern.sh`.

`make -C gizmo/test` runs the existing algorithm tests.
`tools/macos/test-speech-invariance.sh` checks that changing decoder packet
sizes or the media timestamp origin cannot change recognized words, scores
or relative word times. It covers both enabled and disabled noise removal.
`tools/macos/check-sync.py` compares complete CLI synchronizations against the
original Intel application, using isolated preferences and output files. Run
it against the final packaged app as well as the source build.

### Initial packaged validation (2026-11-09)

Tested on Apple M1 / macOS 27.2, using the same copied models as the original
Intel application. The final bundle has 28 arm64-only Mach-O files; library
closure, minimum-OS metadata and deep/strict code signature checks pass.
It runs without Python or dynamic-library path overrides.

| Fixture | Maximum output timing difference from original Intel 0.17.0 |
| --- | ---: |
| Subtitle offset and 1.5% playback-rate drift | 0 ms |
| Generated English speech, 118.93 seconds | 17 ms |
| Private 20-minute English AAC 5.1 / Croatian subtitle excerpt | 483 ms |

All three packaged comparisons pass the documented regression tolerances,
and the original app and preferences/models are unchanged by content hash.
The modern recognizer's real-media output is measurably different; the
`macos-arm64` branch remains the preferred build for preserving existing
SubSync results. More representative film comparisons are needed before
promoting this experimental branch.

The 433 existing algorithm assertions pass. Additional native integration
checks cover silence, separated utterances, media timestamps, discontinuity,
EOF draining, repeated flush, 48 kHz to 16 kHz conversion and custom speaker
ordering. A reversed FR/FL layout with explicit RIGHT selection produces
the expected signal and exact final sample count.

### Speech context update (2026-11-09)

The initial PS5 adapter used the library endpointer defaults and silently
inherited `remove_noise=no`, unlike the original SphinxBase front end.
The updated adapter retains real PCM around short utterances, confirms
speech sooner and restores the original preprocessing default. It does not
change the correlation algorithm, minimum point count or confidence thresholds.

All comparisons below use standalone packaged apps, the same models and
default matching thresholds. Films and copied captions remain private.

| Private film fixture | Previous modern maximum difference vs Intel | Updated modern |
| --- | ---: | ---: |
| Original 20-minute AAC 5.1 / Croatian sample | 483 ms | 215 ms |
| Independent E-AC3 5.1 sample, +9.25 s | 214 ms | 160 ms |
| Same E-AC3 sample, 0.985 rate / +14.5 s | 215 ms | 160 ms |
| Independent AC3 5.1 sample, +9.25 s | 671 ms | 213 ms |
| Same AC3 sample, 0.985 rate / +14.5 s | 672 ms | 213 ms |

The two independent samples have 453 and 223 Croatian cues respectively.
For the updated app their offset-versus-drift outputs agree within 1 and
2 ms. Both original Intel and modern apps successfully synchronized all
four holdout tasks. Updated output passes the unchanged 500 ms comparison
tolerance; the previous modern app exceeded it on the AC3 sample.
Film-caption times are not verified ground truth: these are measurements
of consistency with the original, not an absolute accuracy guarantee.

Generated clean English speech remains within 20 ms of its known cue times.
All 433 algorithm assertions and additional media, context, partial-EOF and
timing-property checks pass. Identical PCM with decoder blocks of 997, 320
or 4096 samples gives identical words/scores/times; shifting media PTS by
123.375 s changes times by that exact amount within 0.008 ms of float rounding.

A separate fixed caption-window proxy found 148 time-matched English word
occurrences versus 132 for the initial modern app, using identical audio,
models and thresholds. Noise removal alone produced 159, but gave a worse
timing comparison on the original film (734 ms). This is a tradeoff between
imperfect proxies, not proof of universally better recognition. A severe
12 dB synthetic white-noise stress case still fails the default minimum
point count in both original and updated engines.

The branch remains experimental. The installed original app, its profiles
and all source media/captions remain unchanged by the recorded safety checks.

`tools/macos/compare-suite.py` prepares private multi-film offset/drift
fixtures and compares immutable app snapshots. It verifies the tested app
hash before reusing results; its public summary excludes private source paths.
