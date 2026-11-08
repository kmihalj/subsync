#!/usr/bin/env python3
"""Compare app builds on private, independently selected media excerpts.

Only this utility is suitable for source control. The input manifest, copied
audio/subtitles/models, application snapshots and results stay under .build.
Film subtitle timings are comparison input, never verified ground truth.

    python3 tools/macos/compare-suite.py prepare .build/private-suite-input.json
    python3 tools/macos/compare-suite.py run --label intel --binary /path/to/subsync
    python3 tools/macos/compare-suite.py run --label modern-before \
        --compare intel --binary /path/to/SubSync.app
    python3 tools/macos/compare-suite.py summary

The private manifest contains ``samples``, each with a generic ``id``, absolute
``media`` and ``subtitle`` paths, optional ``english_subtitle_stream`` (global
stream index), ``start``/``duration`` in seconds, and audio stream ordinal.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK = ROOT / ".build/improvement-fixtures"
DEFAULT_CHECKER = Path(__file__).with_name("check-sync.py")
VARIANTS = {"offset": {"scale": 1.0, "offset_ms": 9250},
            "drift": {"scale": 0.985, "offset_ms": 14500}}
DROP_ENV = ("DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH", "PYTHONPATH", "PYTHONHOME")


def helpers(checker):
    spec = importlib.util.spec_from_file_location("check_sync", checker)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(path, value):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent,
                                     prefix=path.name + ".", suffix=".tmp",
                                     encoding="utf-8", delete=False) as target:
        target.write(json.dumps(value, indent=2) + "\n")
        temporary = Path(target.name)
    temporary.replace(path)


def source_identity(media, subtitle, digest):
    stat = media.stat()
    return {"media_size": stat.st_size, "media_mtime_ns": stat.st_mtime_ns,
            "subtitle_sha256": digest(subtitle)}


def prepare(args):
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    helper = helpers(args.checker)
    supplied = json.loads(args.manifest.read_text())
    ffmpeg = Path(supplied.get("ffmpeg", "/Applications/Plex Media Server.app/Contents/MacOS/Plex Transcoder"))
    assets_source = Path(supplied.get("assets_source", str(Path.home() / "Library/Preferences/subsync/assets")))
    assets = work / "assets"
    shutil.copytree(assets_source / "speech", assets / "speech", dirs_exist_ok=True)
    (assets / "dict").mkdir(exist_ok=True)
    shutil.copy2(assets_source / "dict/eng-hrv.dict", assets / "dict/eng-hrv.dict")
    model_digest = helper.tree_digest(assets)
    suite = {"schema": 1, "variants": VARIANTS, "samples": [], "assets_sha256": model_digest,
             "timing_ground_truth": False, "equivariance_tolerance_ms": 500}
    for source in supplied["samples"]:
        sample_id = source["id"]
        if not sample_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for char in sample_id):
            raise ValueError("Use a generic lowercase sample id, not a film title or path")
        sample_dir = work / "media" / sample_id
        sample_dir.mkdir(parents=True, exist_ok=True)
        media, subtitle = Path(source["media"]), Path(source["subtitle"])
        start, duration = float(source.get("start", 600)), float(source.get("duration", 1200))
        audio_ordinal = int(source.get("audio_stream", 0))
        before = source_identity(media, subtitle, helper.tree_digest)
        audio = sample_dir / "audio.mka"
        clip_identity = {"media": str(media.resolve()), "source": before,
                         "start": start, "duration": duration, "audio_stream": audio_ordinal}
        clip_stamp = sample_dir / "clip-source.json"
        if audio.exists() and (not clip_stamp.exists() or json.loads(clip_stamp.read_text()) != clip_identity):
            raise ValueError(f"{sample_id}: cached audio has no matching source/window identity; use a new work directory")
        if not audio.exists():
            subprocess.run([str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error",
                            "-ss", str(start), "-i", str(media), "-t", str(duration), "-vn",
                            "-map", f"0:a:{audio_ordinal}", "-c:a", "copy", "-avoid_negative_ts",
                            "make_zero", "-y", str(audio)], check=True)
            save(clip_stamp, clip_identity)
        # The input files used here are UTF-8; decoding is explicit and lossless.
        start_ms, end_ms = round(start * 1000), round((start + duration) * 1000)
        cues = [(begin - start_ms, end - start_ms, text)
                for begin, end, text in helper.read_srt(subtitle)
                if begin >= start_ms and end <= end_ms]
        if len(cues) < 220:
            raise ValueError(f"{sample_id}: {len(cues)} cues; select a dialogue excerpt with at least 220")
        helper.write_srt(sample_dir / "supplied-reference.srt", cues)
        english = None
        if source.get("english_subtitle_stream") is not None:
            english = sample_dir / "english-excerpt.srt"
            if not english.exists():
                subprocess.run([str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error",
                                "-ss", str(start), "-i", str(media), "-t", str(duration),
                                "-map", f"0:{int(source['english_subtitle_stream'])}",
                                "-c:s", "copy", "-y", str(english)], check=True)
        sample = {"id": sample_id, "start": start, "duration": duration, "cues": len(cues),
                  "source": source, "source_before": before, "variants": {}}
        if english:
            sample["english_cues"] = len(helper.read_srt(english))
            sample["english_excerpt"] = str(english)
        for variant, transform in VARIANTS.items():
            fixtures = work / "fixtures" / sample_id / variant
            fixtures.mkdir(parents=True, exist_ok=True)
            helper.write_srt(fixtures / "real-reference.srt", cues)
            helper.write_srt(fixtures / "real-shifted.srt", [
                (begin * transform["scale"] + transform["offset_ms"],
                 end * transform["scale"] + transform["offset_ms"], text)
                for begin, end, text in cues])
            profile = fixtures / "home/Library/Preferences/subsync"
            profile.mkdir(parents=True, exist_ok=True)
            link = profile / "assets"
            if not link.exists():
                link.symlink_to(assets, target_is_directory=True)
            save(fixtures / "fixture.json", {"real": {
                "reference": str(audio), "sub_lang": "hrv", "cues": len(cues),
                "timing_ground_truth": False, "transform": transform}})
            sample["variants"][variant] = str(fixtures)
        sample["source_after"] = source_identity(media, subtitle, helper.tree_digest)
        sample["source_unchanged"] = sample["source_before"] == sample["source_after"]
        if not sample["source_unchanged"]:
            raise AssertionError(f"{sample_id}: source file metadata/content changed")
        suite["samples"].append(sample)
        print(json.dumps({"prepared": sample_id, "cues": len(cues),
                          "english_cues": sample.get("english_cues"),
                          "source_unchanged": True}), flush=True)
    save(work / "suite.json", suite)


def executable(path):
    path = path.absolute()
    if path.suffix == ".app":
        with (path / "Contents/Info.plist").open("rb") as source:
            name = plistlib.load(source)["CFBundleExecutable"]
        return path / "Contents/MacOS" / name
    return path


def run(args):
    work = args.work.resolve()
    suite = json.loads((work / "suite.json").read_text())
    binary = executable(args.binary)
    env = {key: value for key, value in os.environ.items() if key not in DROP_ENV}
    log_dir = work / "logs" / args.label
    log_dir.mkdir(parents=True, exist_ok=True)
    helper = helpers(args.checker)
    bundle = helper.app_bundle([str(binary)])
    bundle_digest = helper.tree_digest(bundle) if bundle else None
    jobs = []
    for sample in suite["samples"]:
        for variant, fixture_dir in sample["variants"].items():
            fixtures = Path(fixture_dir)
            report = fixtures / "results" / args.label / "report.json"
            job = {"sample": sample["id"], "variant": variant}
            if report.exists() and not args.force:
                previous = json.loads(report.read_text())
                if (bundle_digest and previous.get("tested_app_sha256") == bundle_digest
                        and previous.get("command") == [str(binary)]
                        and previous.get("cases", {}).get("real", {}).get("returncode") == 0):
                    job["cached"] = True
                else:
                    report.unlink()
            if not job.get("cached"):
                command = [sys.executable, str(args.checker.resolve()), "--fixtures", str(fixtures),
                           "run", "--label", args.label, "--case", "real"]
                if args.compare:
                    command += ["--compare", args.compare]
                command += ["--command", str(binary)]
                print(json.dumps({"starting": job, "label": args.label}), flush=True)
                started = time.monotonic()
                process = subprocess.run(command, env=env, cwd=ROOT, capture_output=True, text=True)
                log = log_dir / f"{sample['id']}-{variant}.log"
                log.write_text(process.stdout + process.stderr)
                job.update(runner_returncode=process.returncode, seconds=time.monotonic() - started)
            if report.exists():
                result = json.loads(report.read_text())
                job.update(case=result.get("cases", {}).get("real", {}),
                           protected_unchanged=result.get("protected_unchanged"), report=str(report))
            else:
                job["case"] = {"passed": False, "error": "Runner did not produce a report; inspect private log"}
            jobs.append(job)
            print(json.dumps({"finished": job, "label": args.label}), flush=True)
    save(work / f"summary-{args.label}.json", {"label": args.label, "binary": str(binary),
                                             "unset_environment": list(DROP_ENV), "jobs": jobs})
    summary(args)


def summary(args):
    work = args.work.resolve()
    suite = json.loads((work / "suite.json").read_text())
    helper = helpers(args.checker)
    summaries = []
    for path in sorted(work.glob("summary-*.json")):
        result = json.loads(path.read_text())
        result["equivariance"] = []
        for sample in suite["samples"]:
            offset = Path(sample["variants"]["offset"]) / "results" / result["label"] / "real.srt"
            drift = Path(sample["variants"]["drift"]) / "results" / result["label"] / "real.srt"
            if offset.exists() and drift.exists():
                metrics = helper.compare_cues(helper.read_srt(drift), helper.read_srt(offset))
                metrics.update(sample=sample["id"], tolerance_ms=suite["equivariance_tolerance_ms"])
                metrics["passed"] = metrics["max_abs_error_ms"] <= metrics["tolerance_ms"]
                result["equivariance"].append(metrics)
        # Compare completed outputs independently of run order, so separate
        # app builds can run concurrently without repeating ASR work.
        public_jobs = []
        for job in result["jobs"]:
            public = {key: job.get(key) for key in ("sample", "variant", "protected_unchanged")}
            allowed = ("returncode", "seconds", "max_abs_error_ms", "median_error_ms",
                       "mean_abs_error_ms", "expected_timing_is_ground_truth", "passed")
            public["case"] = {key: job["case"][key] for key in allowed if key in job["case"]}
            if job["case"].get("error"):
                public["case"]["error_present"] = True
            sample = next(item for item in suite["samples"] if item["id"] == job["sample"])
            outputs = Path(sample["variants"][job["variant"]]) / "results"
            reference = outputs / "intel/real.srt"
            actual = outputs / result["label"] / "real.srt"
            reference_report = outputs / "intel/report.json"
            reference_complete = reference_report.exists() and json.loads(reference_report.read_text()).get(
                "cases", {}).get("real", {}).get("returncode") == 0
            if result["label"] != "intel" and reference_complete and reference.exists() and actual.exists():
                metrics = helper.compare_cues(helper.read_srt(actual), helper.read_srt(reference))
                metrics["tolerance_ms"] = 500
                metrics["passed"] = metrics["max_abs_error_ms"] <= 500
                public["versus_intel"] = metrics
            public_jobs.append(public)
        # Generic report intentionally excludes private paths, source names
        # and raw diagnostic errors, which can include filenames.
        complete = len(public_jobs) == len(suite["samples"]) * len(VARIANTS)
        passed = complete and all(job["case"].get("passed") and job.get("protected_unchanged")
                                  for job in public_jobs)
        passed = passed and len(result["equivariance"]) == len(suite["samples"]) and all(
            item["passed"] for item in result["equivariance"])
        if result["label"] != "intel":
            passed = passed and all(job.get("versus_intel", {}).get("passed") for job in public_jobs)
        summaries.append({"label": result["label"], "passed": bool(passed),
                          "equivariance": result["equivariance"], "jobs": public_jobs})
    save(work / "comparison.json", {"timing_ground_truth": False, "builds": summaries})
    print(json.dumps({"comparison": str(work / "comparison.json"), "builds": summaries}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--checker", type=Path, default=DEFAULT_CHECKER)
    sub = parser.add_subparsers(dest="action", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("manifest", type=Path)
    prepare_parser.set_defaults(function=prepare)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--label", required=True)
    run_parser.add_argument("--binary", type=Path, required=True)
    run_parser.add_argument("--compare")
    run_parser.add_argument("--force", action="store_true")
    run_parser.set_defaults(function=run)
    sub.add_parser("summary").set_defaults(function=summary)
    args = parser.parse_args()
    return args.function(args)


if __name__ == "__main__":
    sys.exit(main())
