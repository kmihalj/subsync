#!/usr/bin/env python3
"""Copy existing models and dictionaries to the ARM app without altering originals."""
import argparse
import pathlib
import shutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=pathlib.Path,
                    default=pathlib.Path.home() / 'Library/Preferences/subsync')
parser.add_argument('--destination', type=pathlib.Path,
                    default=pathlib.Path.home() / 'Library/Application Support/SubSync ARM')
args = parser.parse_args()
source = args.source.expanduser().resolve(strict=True)
destination = args.destination.expanduser().resolve()
if source == destination or source in destination.parents or destination in source.parents:
    parser.error('Source and destination must be separate directories')
destination.mkdir(parents=True, exist_ok=True)
for name in ('assets', 'assets.json'):
    src, dst = source / name, destination / name
    if not src.exists():
        continue
    if dst.exists():
        print(f'Skipping existing destination: {dst}')
    elif src.is_dir():
        shutil.copytree(src, dst)
        print(f'Copied {src} to {dst}')
    else:
        shutil.copy2(src, dst)
        print(f'Copied {src} to {dst}')
