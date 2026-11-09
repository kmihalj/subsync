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

PocketSphinx 5.1.1 has two documented local compatibility corrections.
The public streaming CEP API now drains all dynamic-feature lookahead frames
at utterance termination,
including when the output ring wraps. The source patch and its hash are
recorded in `tools/macos/modern-deps.json` and included in native licenses.
That fix leaves the raw PCM input path unchanged. A new bounded
`cmninit_frames` configuration option preserves the upstream 500-frame
initial history by default and allows SubSync to request the original empty
history explicitly. No matching thresholds are relaxed to obtain successful
comparisons.

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

`tools/macos/test-modern-media.sh --original-packets` builds a standalone
native integration test with the restored packet-handling contract.
It uses the downloaded PocketSphinx source's `goforward.raw` fixture and model
and checks silence, multiple utterances, nonzero media timestamps, EOF speech
drain, repeated flush, a discontinuity, custom stereo mixing and resampler
drain. It needs the dependencies produced by `build-deps-modern.sh`.

`make -C gizmo/test` runs the existing algorithm tests.
`tools/macos/test-cep-tail.sh` checks 64 public CEP tail/reset cases around
feature and ring boundaries. `tools/macos/test-frontend-invalid.sh` checks
malformed input configurations and upstream warp/FFT overflow regressions.
`tools/macos/test-frontend-stream.sh` checks 400 queue/EOF/reset cases and
consumer-callback failure recovery. The application build script runs these
checks before packaging.
`tools/macos/test-speech-invariance.sh --original-packets` checks repeatable
recognition and exact timestamp-origin shifts in both noise-removal modes,
and reports changes caused by different decoder block sizes. The original
frontend's live adaptation and utterance endings depend on packet boundaries;
this behavior is intentionally retained for compatibility. The earlier v2
contract remains available with `--strict-packets`; exact cross-packet score
and timing equality is not promised by this restored frontend.
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

### Compatibility frontend (v3, 2026-11-09)

The selected frontend restores original energy/SNR detection, streaming MFCC
ring boundaries and an empty initial CMN history. Formerly FLOAT32 decoder
options retain their original float32 numeric values; original FLOAT64
search beams retain their full precision. Current PocketSphinx still owns
feature expansion and recognition. FFmpeg remains 9.0.2; PocketSphinx remains
5.1.1 with the two explicitly recorded local compatibility corrections.

The selected source candidate was compared with the same immutable original
Intel outputs, models and unchanged matching thresholds:

| Fixture | v2 maximum difference vs Intel | v3 source candidate |
| --- | ---: | ---: |
| Generated speech | 18 ms | 2 ms |
| Original 20-minute AAC 5.1 sample | 215 ms | 24 ms |
| E-AC3 5.1 sample, offset / rate drift | 160 / 160 ms | 203 / 202 ms |
| AC3 5.1 sample, offset / rate drift | 213 / 213 ms | 165 / 31 ms |
| Additional AC3 stereo sample, offset / rate drift | failed / failed | 249 / 154 ms |

Generated speech is within 9 ms of its known cue times. Film values measure
agreement with the original app, not absolute timing accuracy: the supplied
captions are not verified ground truth. The E-AC3 result is slightly farther
from the original than v2; the other listed comparisons improve, and both
previously unsuccessful stereo-film cases complete without relaxing the
minimum point count or confidence/distance thresholds.

Offset-versus-rate-drift output agreement is 1 ms, 135 ms and 14 ms for the
three additional films. This reflects the retained matching/point selection
algorithm; it is not uniformly identical under transformed input captions.

A separate independent frontend oracle compared exact coefficients, ring
batches, stream frame offsets, VAD states and EOF behavior with the historical
test-only reference: both noise modes passed on all 19,250,859 PCM samples
and 56,400 real decoder chunks (20 minutes), using the actual model geometry.
The old library is not needed by the app or the normal build/test scripts.

The restored original packet contract deliberately retains live adaptation
and utterance boundaries at decoder block boundaries. Controlled tests of
both old and new frontends observe 5–10 ms word-time changes on the clean
speech fixture when block sizes change; probabilities can change too.
Repeating the same blocks and shifting only the media timestamp origin are
covered independently. No exact cross-packet equality is claimed.

Two globally packet-invariant alternatives were evaluated and rejected:
fixed seven-frame handoff failed both stereo-film jobs; canonical PCM steps
with the original ring exceeded the unchanged 500 ms comparison limit on one
stereo-film job (571 ms). No per-film engine selection is used.

The existing 433 algorithm assertions and all 105 upstream PocketSphinx tests
pass. Additional checks cover 64 CEP tail/reset cases, malformed/overflow
configurations and 400 streaming/partial-EOF/reset cases with callback-error
recovery. Sanitized checks and final packaged comparisons are recorded in the
separate v3 validation report; the installed original app is never replaced.
