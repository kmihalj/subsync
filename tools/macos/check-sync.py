#!/usr/bin/env python3
"""Generate local synchronization fixtures and compare SubSync CLI builds.

All output, model copies, HOME and TMPDIR stay under .build/fixtures. This
script never changes an installed application or the source model directory.
The speech fixture uses macOS's locally installed Samantha voice, not a film.

    python3 tools/macos/check-sync.py prepare
    python3 tools/macos/check-sync.py run --label intel \
        --command /Applications/subsync.app/Contents/MacOS/subsync
    python3 tools/macos/check-sync.py run --label arm --compare intel \
        --command .venv/bin/python run.py
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time
import wave


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = ROOT / ".build" / "fixtures"
TEXT = [
    "The morning train arrived at the station before the rain started.",
    "A woman carrying a yellow umbrella walked slowly across the platform.",
    "She was looking for her brother who had returned from the mountains.",
    "Their journey would take them through a valley beside the old river.",
    "The conductor checked the tickets and carefully closed every carriage door.",
    "Outside the window the houses became smaller and the fields grew wider.",
    "Some children watched a farmer driving his tractor along a narrow road.",
    "Beyond the village a stone bridge crossed the water near a forest.",
    "The travelers shared their breakfast and discussed their plans for the afternoon.",
    "They wanted to visit a museum and find a restaurant near the harbor.",
    "An elderly passenger recommended the market where local people sold fresh bread.",
    "He also described a beautiful garden behind the library in the center.",
    "When the train stopped everyone gathered their luggage and stepped onto the platform.",
    "The weather had improved and sunlight shone between the clouds above them.",
    "They followed a quiet street until they reached the square beside the church.",
    "A musician was playing a familiar song while people waited for the bus.",
    "The brother bought a newspaper and asked the shopkeeper for clear directions.",
    "After walking another block they discovered the entrance to the history museum.",
    "Inside the building they studied paintings and photographs from the previous century.",
    "A friendly guide explained how the town had changed during the railway construction.",
    "Later they ate a simple lunch and watched fishing boats return to the harbor.",
    "They wrote a postcard to their parents and promised to telephone that evening.",
    "Before returning to the station they purchased some flowers at the outdoor market.",
    "The final train carried them home as the orange sun disappeared behind the hills.",
]


def stamp(ms):
    ms = round(ms)
    seconds, fraction = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},{fraction:03}"


def write_srt(path, cues):
    path.write_text("\n\n".join(
        f"{index}\n{stamp(start)} --> {stamp(end)}\n{text}"
        for index, (start, end, text) in enumerate(cues, 1)
    ) + "\n", encoding="utf-8")


def read_srt(path):
    cues = []
    pattern = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)")
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip()):
        lines = block.splitlines()
        timing = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing is None:
            continue
        times = pattern.findall(lines[timing])
        if len(times) != 2:
            raise ValueError(f"Invalid subtitle timestamp in {path}: {lines[timing]}")
        start, end = [((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)
                      for h, m, s, ms in times]
        cues.append((start, end, "\n".join(lines[timing + 1:])))
    return cues


def tree_digest(path):
    """Include file names and bytes; ignore metadata such as access timestamps."""
    path = Path(path)
    if not path.exists():
        return None
    result = hashlib.sha256()
    files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
    for file in files:
        name = file.name if path.is_file() else str(file.relative_to(path))
        result.update(name.encode("utf-8"))
        result.update(b"\0")
        with file.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                result.update(chunk)
    return result.hexdigest()


def app_bundle(command):
    binary = Path(command[0]).resolve()
    for parent in (binary, *binary.parents):
        if parent.suffix.lower() == ".app":
            return parent
    return None


def prepare(args):
    fixtures = args.fixtures.resolve()
    fixtures.mkdir(parents=True, exist_ok=True)
    cues = [(2000 + i * 5500, 6500 + i * 5500, text) for i, text in enumerate(TEXT)]
    write_srt(fixtures / "text-reference.srt", cues)
    # Exact affine transform tests both a constant offset and playback-rate drift.
    write_srt(fixtures / "text-shifted.srt", [
        (start * 1.015 + 6500, end * 1.015 + 6500, text) for start, end, text in cues
    ])
    metadata = {"text_scale": 1.015, "text_offset_ms": 6500, "cues": len(cues)}
    if not args.no_speech:
        assets_source = args.assets_source.expanduser().resolve()
        if not (assets_source / "speech" / "eng.speech").is_file():
            raise FileNotFoundError(f"English SubSync model missing under {assets_source}")
        speech_target = fixtures / "home/Library/Preferences/subsync/assets/speech"
        shutil.copytree(assets_source / "speech", speech_target, dirs_exist_ok=True)
        parts = fixtures / "speech-parts"
        parts.mkdir(exist_ok=True)
        audio = bytearray(b"\0" * (16000 * 2 * 2))
        speech_cues = []
        for index, text in enumerate(TEXT):
            part = parts / f"{index:02}.wav"
            if not part.exists():
                subprocess.run(["say", "-v", "Samantha", "-r", "155", "-o", str(part),
                                "--file-format=WAVE", "--data-format=LEI16@16000", text], check=True)
            with wave.open(str(part), "rb") as source:
                if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
                    raise ValueError(f"Unexpected generated speech format in {part}")
                data = source.readframes(source.getnframes())
            start = len(audio) / 32
            audio.extend(data)
            end = len(audio) / 32
            speech_cues.append((start, end, text))
            audio.extend(b"\0" * (16000 * 2))
        with wave.open(str(fixtures / "speech.wav"), "wb") as target:
            target.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            target.writeframes(audio)
        write_srt(fixtures / "speech-reference.srt", speech_cues)
        write_srt(fixtures / "speech-shifted.srt", [
            (start + 6000, end + 6000, text) for start, end, text in speech_cues
        ])
        metadata.update(speech_offset_ms=6000, speech_duration_seconds=len(audio) / 32000,
                        voice="Samantha", speech_rate_wpm=155,
                        english_model_sha256=tree_digest(speech_target))
    (fixtures / "fixture.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"fixtures": str(fixtures), **metadata}, indent=2))


def prepare_media(args):
    """Copy a private audio excerpt and cropped subtitles; never write sources."""
    fixtures = args.fixtures.resolve()
    metadata_path = fixtures / "fixture.json"
    metadata = json.loads(metadata_path.read_text())
    media = args.media.expanduser().resolve()
    subtitle = args.subtitle.expanduser().resolve()
    source_before = {"subtitle": tree_digest(subtitle), "media_size": media.stat().st_size,
                     "media_mtime_ns": media.stat().st_mtime_ns}
    # Keep the real compressed audio and its channel layout. This also works
    # with a demux/remux-only FFmpeg executable such as Plex Transcoder.
    subprocess.run([str(args.ffmpeg.expanduser()), "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-ss", str(args.start), "-i", str(media), "-t", str(args.duration),
                    "-vn", "-map", f"0:a:{args.audio_stream}", "-c:a", "copy",
                    "-avoid_negative_ts", "make_zero", "-y", str(fixtures / "real.mka")], check=True)
    start_ms, duration_ms = round(args.start * 1000), round(args.duration * 1000)
    cues = [(start - start_ms, end - start_ms, text)
            for start, end, text in read_srt(subtitle)
            if start >= start_ms and end <= start_ms + duration_ms]
    if len(cues) < 20:
        raise ValueError(f"Only {len(cues)} subtitle cues in excerpt; choose a longer dialogue segment")
    write_srt(fixtures / "real-reference.srt", cues)
    write_srt(fixtures / "real-shifted.srt", [
        (start + 7500, end + 7500, text) for start, end, text in cues
    ])
    assets_source = args.assets_source.expanduser().resolve()
    target = fixtures / "home/Library/Preferences/subsync/assets/dict"
    target.mkdir(parents=True, exist_ok=True)
    if args.sub_lang != "eng":
        dictionary_name = "-".join(sorted(["eng", args.sub_lang])) + ".dict"
        shutil.copy2(assets_source / "dict" / dictionary_name, target / dictionary_name)
    source_after = {"subtitle": tree_digest(subtitle), "media_size": media.stat().st_size,
                    "media_mtime_ns": media.stat().st_mtime_ns}
    if source_before != source_after:
        raise AssertionError("Original media or subtitle changed while preparing excerpt")
    metadata["real"] = {"media": str(media), "subtitle": str(subtitle), "start": args.start,
                        "duration": args.duration, "cues": len(cues), "offset_ms": 7500,
                        "reference": "real.mka",
                        "sub_lang": args.sub_lang, "source_before": source_before,
                        "source_after": source_after, "source_unchanged": True}
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata["real"], indent=2))


def compare_cues(actual, expected):
    if len(actual) != len(expected):
        raise AssertionError(f"Cue count changed: {len(actual)} != {len(expected)}")
    if [cue[2] for cue in actual] != [cue[2] for cue in expected]:
        raise AssertionError("Subtitle text or cue ordering changed")
    errors = [a - e for output, reference in zip(actual, expected)
              for a, e in zip(output[:2], reference[:2])]
    return {"max_abs_error_ms": max(map(abs, errors)),
            "median_error_ms": statistics.median(errors),
            "mean_abs_error_ms": statistics.mean(map(abs, errors))}


def run(args):
    fixtures = args.fixtures.resolve()
    if not (fixtures / "fixture.json").is_file():
        raise FileNotFoundError("Run the prepare command first")
    metadata = json.loads((fixtures / "fixture.json").read_text())
    report_dir = fixtures / "results" / args.label
    report_dir.mkdir(parents=True, exist_ok=True)
    home = fixtures / "home"
    home.mkdir(exist_ok=True)
    temporary = report_dir / "tmp"
    temporary.mkdir(exist_ok=True)
    command = args.command
    if not command:
        raise ValueError("--command requires the SubSync executable (optionally with its Python runner)")
    # Preserve a virtualenv Python symlink: resolving it would bypass that
    # environment's site-packages and run the underlying standalone Python.
    command[0] = os.path.abspath(command[0]) if "/" in command[0] else command[0]
    env = dict(os.environ, HOME=str(home), TMPDIR=str(temporary))
    # Native forks can also honor this explicit override; original 0.17 honors HOME.
    env["SUBSYNC_CONFIG_DIR"] = str(home / "Library/Preferences/subsync")
    env["SUBSYNC_ASSET_DIR"] = str(home / "Library/Preferences/subsync/assets")
    bundle = app_bundle(command)
    original_app = Path("/Applications/subsync.app")
    protected_prefs = Path(os.environ["HOME"]) / "Library/Preferences/subsync"
    protected_before = {"installed_original_app": tree_digest(original_app),
                        "original_preferences": tree_digest(protected_prefs)}
    result = {"command": command, "label": args.label, "protected_before": protected_before,
              "tested_app_sha256": tree_digest(bundle) if bundle else None,
              "cases": {}}
    report_path = report_dir / "report.json"
    if args.case and report_path.is_file():
        previous = json.loads(report_path.read_text())
        if previous.get("command") == command:
            result["cases"] = previous.get("cases", {})
    cases = ["text"]
    if not args.no_speech and (fixtures / "speech.wav").is_file():
        cases.append("speech")
    if not args.no_speech and "real" in metadata:
        cases.append("real")
    if args.case:
        cases = [case for case in cases if case in args.case]
        if not cases:
            raise ValueError("No requested case has been prepared")
    for case in cases:
        output = report_dir / f"{case}.srt"
        reference = fixtures / (metadata["real"]["reference"] if case == "real" else
                                "speech.wav" if case == "speech" else "text-reference.srt")
        sub_lang = metadata["real"]["sub_lang"] if case == "real" else "eng"
        invocation = command + ["--cli", "--offline", "--verbose", "2", "--jobs", "2",
                                "--effort", "1", "--overwrite", "--loglevel", "INFO",
                                "--logfile", str(report_dir / f"{case}.log"),
                                "--dump-words", f"ref:{report_dir / (case + '-ref-words.srt')}",
                                "sync", "--sub", str(fixtures / f"{case}-shifted.srt"),
                                "--sub-lang", sub_lang, "--ref", str(reference),
                                "--ref-lang", "eng", "--out", str(output)]
        if output.exists():
            output.unlink()
        started = time.monotonic()
        process = subprocess.run(invocation, cwd=ROOT, env=env, capture_output=True,
                                 text=True, timeout=args.timeout)
        (report_dir / f"{case}.stdout.txt").write_text(process.stdout)
        (report_dir / f"{case}.stderr.txt").write_text(process.stderr)
        case_result = {"returncode": process.returncode, "seconds": time.monotonic() - started}
        if process.returncode == 0 and output.exists():
            actual = read_srt(output)
            expected = read_srt(fixtures / f"{case}-reference.srt")
            case_result.update(compare_cues(actual, expected))
            if case == "text":
                case_result["passed"] = case_result["max_abs_error_ms"] <= 30
            else:
                # Speech timings are estimated from recognition, not exact cue boundaries.
                tolerance = 2000 if case == "real" else 1000
                case_result["passed"] = (case_result["max_abs_error_ms"] <= tolerance)
            if args.compare:
                baseline = fixtures / "results" / args.compare / f"{case}.srt"
                case_result["versus_baseline"] = compare_cues(actual, read_srt(baseline))
                tolerance = 30 if case == "text" else 500
                case_result["baseline_tolerance_ms"] = tolerance
                case_result["passed"] = case_result["passed"] and (
                    case_result["versus_baseline"]["max_abs_error_ms"] <= tolerance)
        else:
            case_result["passed"] = False
            case_result["error"] = process.stderr[-2000:] or process.stdout[-2000:]
        result["cases"][case] = case_result
        print(json.dumps({case: case_result}, indent=2), flush=True)
    protected_after = {"installed_original_app": tree_digest(original_app),
                       "original_preferences": tree_digest(protected_prefs)}
    result["protected_after"] = protected_after
    result["protected_unchanged"] = protected_before == protected_after
    result["passed"] = result["protected_unchanged"] and all(
        case["passed"] for case in result["cases"].values())
    report_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"report": str(report_path), "passed": result["passed"],
                      "protected_unchanged": result["protected_unchanged"]}, indent=2))
    return 0 if result["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    commands = parser.add_subparsers(dest="action", required=True)
    prepare_parser = commands.add_parser("prepare", help="create deterministic subtitles and local TTS audio")
    prepare_parser.add_argument("--no-speech", action="store_true")
    prepare_parser.add_argument("--assets-source", type=Path,
                                default=Path.home() / "Library/Preferences/subsync/assets")
    prepare_parser.set_defaults(function=prepare)
    media_parser = commands.add_parser("prepare-media", help="make a private read-only real-media fixture")
    media_parser.add_argument("--media", type=Path, required=True)
    media_parser.add_argument("--subtitle", type=Path, required=True)
    media_parser.add_argument("--start", type=float, default=600)
    media_parser.add_argument("--duration", type=float, default=300)
    media_parser.add_argument("--audio-stream", type=int, default=0)
    media_parser.add_argument("--sub-lang", default="hrv")
    media_parser.add_argument("--ffmpeg", type=Path, default=Path("/Applications/Plex Media Server.app/Contents/MacOS/Plex Transcoder"))
    media_parser.add_argument("--assets-source", type=Path,
                              default=Path.home() / "Library/Preferences/subsync/assets")
    media_parser.set_defaults(function=prepare_media)
    run_parser = commands.add_parser("run", help="test one SubSync CLI build in an isolated home")
    run_parser.add_argument("--label", required=True)
    run_parser.add_argument("--compare", help="label of a previous run to compare")
    run_parser.add_argument("--case", choices=["text", "speech", "real"], action="append",
                            help="run only a selected case (repeatable)")
    run_parser.add_argument("--no-speech", action="store_true")
    run_parser.add_argument("--timeout", type=float, default=600)
    run_parser.add_argument("--command", nargs=argparse.REMAINDER, required=True)
    run_parser.set_defaults(function=run)
    args = parser.parse_args()
    return args.function(args)


if __name__ == "__main__":
    sys.exit(main())
