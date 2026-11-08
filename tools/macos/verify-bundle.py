#!/usr/bin/env python3
"""Reject non-arm64 binaries and dependencies outside a standalone Mac bundle."""
import argparse
import json
import pathlib
import plistlib
import re
import subprocess
import sys


def output(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def verify(app):
    app = app.resolve(strict=True)
    errors, binaries, minimums = [], [], set()
    for path in sorted(app.rglob('*')):
        if path.is_symlink() or not path.is_file():
            continue
        if 'Mach-O' not in output('/usr/bin/file', '-b', str(path)):
            continue
        relative = str(path.relative_to(app))
        archs = output('/usr/bin/lipo', '-archs', str(path)).strip().split()
        binaries.append(relative)
        if archs != ['arm64']:
            errors.append(f'{relative}: expected arm64 only, got {archs}')
        load_commands = output('/usr/bin/otool', '-l', str(path))
        for block in re.split(r'Load command \d+', load_commands):
            field = None
            if re.search(r'cmd LC_BUILD_VERSION\s', block):
                field = 'minos'
            elif re.search(r'cmd LC_VERSION_MIN_MACOSX\s', block):
                field = 'version'
            if field:
                match = re.search(r'^\s*' + field + r'\s+(\d+\.\d+(?:\.\d+)?)', block, re.M)
                if match:
                    minimums.add(match.group(1))
        for line in output('/usr/bin/otool', '-L', str(path)).splitlines()[1:]:
            dependency = line.strip().split(' (compatibility version', 1)[0]
            if dependency.startswith('/') and not dependency.startswith(('/System/Library/', '/usr/lib/')):
                errors.append(f'{relative}: external library {dependency}')
    if not binaries:
        errors.append('No Mach-O binaries found')
    version_tuple = lambda value: tuple((list(map(int, value.split('.'))) + [0, 0])[:3])
    required = max(minimums, key=version_tuple) if minimums else None
    with (app / 'Contents/Info.plist').open('rb') as stream:
        declared = plistlib.load(stream).get('LSMinimumSystemVersion', '0.0')
    if required and version_tuple(required) > version_tuple(declared):
        errors.append(f'Bundle declares macOS {declared}, but a binary requires {required}')
    try:
        output('/usr/bin/codesign', '--verify', '--deep', '--strict', str(app))
    except subprocess.CalledProcessError as exc:
        errors.append(f'Code signature verification: {exc.output.strip()}')
    result = {'app': str(app), 'mach_o_count': len(binaries), 'architecture': 'arm64',
              'declared_minimum_macos': declared, 'binary_minimum_macos': required,
              'errors': errors}
    print(json.dumps(result, indent=2))
    return not errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', type=pathlib.Path)
    sys.exit(0 if verify(parser.parse_args().app) else 1)
