#!/usr/bin/env python3
"""Prepare the pinned speech models and dictionaries for the offline bundle."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
SOURCE = 'https://github.com/sc0ty/subsync/releases/download/assets/'
PINS = Path(__file__).with_name('offline-assets.json')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def archive_for(entry, cache):
    identifier, expected = entry
    name = identifier.replace('/', '-') + '.zip'
    archive = cache / name
    if not archive.is_file():
        with tempfile.TemporaryDirectory(dir=cache) as temp:
            pending = Path(temp) / name
            with urlopen(SOURCE + name, timeout=45) as response, pending.open('wb') as output:
                shutil.copyfileobj(response, output)
            if digest(pending) != expected:
                raise ValueError(f'Checksum mismatch for {name}')
            pending.replace(archive)
    elif digest(archive) != expected:
        raise ValueError(f'Checksum mismatch for cached {archive}')
    return identifier, archive


def prepare(output, cache):
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    entries = json.loads(PINS.read_text()).items()
    with ThreadPoolExecutor(max_workers=8) as pool:
        archives = list(pool.map(lambda entry: archive_for(entry, cache), entries))

    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        stage = Path(temp) / 'bundled-assets'
        stage.mkdir()
        seen = set()
        for identifier, archive in archives:
            kind, name = identifier.split('/')
            descriptor = PurePosixPath(kind, f'{name}.{kind}')
            with ZipFile(archive) as source:
                paths = {PurePosixPath(member.filename) for member in source.infolist()
                         if not member.is_dir()}
                if descriptor not in paths or paths & seen or any(
                        path.parts[0] != kind or '..' in path.parts for path in paths):
                    raise ValueError(f'Unexpected contents in {archive.name}')
                source.extractall(stage)
                seen.update(paths)

        shutil.copyfile(ROOT / 'doc/offline-assets.md', stage / 'SOURCES-AND-LICENSES.md')
        shutil.copyfile(ROOT / 'resources/GFDL-1.1.txt', stage / 'GFDL-1.1.txt')
        shutil.copyfile(PINS, stage / 'ARCHIVE-SHA256.json')
        stage.rename(output)
    print(f'Prepared {len(archives)} verified archives in {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--cache', type=Path, default=ROOT / '.build/offline-archives')
    args = parser.parse_args()
    prepare(args.output, args.cache)
