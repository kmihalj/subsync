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
    framework_dir = app / 'Contents/Frameworks'
    executable_dir = app / 'Contents/MacOS'

    def inside_bundle(path):
        return path.resolve().is_relative_to(app)

    def expand_path(value, loader):
        return pathlib.Path(value.replace('@loader_path', str(loader)).replace(
            '@executable_path', str(executable_dir)))

    for path in sorted(app.rglob('*')):
        if re.search(r'(?:libsphinxbase|libsphinxad|libpocketsphinx\.[0-4](?:\.|$))', path.name, re.I):
            errors.append(f'{path.relative_to(app)}: obsolete speech library is forbidden in the modern app')
        if path.is_symlink():
            if not path.exists() or not inside_bundle(path):
                errors.append(f'{path.relative_to(app)}: dangling or external symlink')
            continue
        if not path.is_file():
            continue
        if 'Mach-O' not in output('/usr/bin/file', '-b', str(path)):
            continue
        relative = str(path.relative_to(app))
        archs = output('/usr/bin/lipo', '-archs', str(path)).strip().split()
        binaries.append(relative)
        if archs != ['arm64']:
            errors.append(f'{relative}: expected arm64 only, got {archs}')
        load_commands = output('/usr/bin/otool', '-l', str(path))
        rpaths = []
        install_ids = set()
        for block in re.split(r'Load command \d+', load_commands):
            if re.search(r'cmd LC_RPATH\s', block):
                match = re.search(r'^\s*path (.+) \(offset \d+\)', block, re.M)
                if match:
                    rpaths.append(expand_path(match.group(1), path.parent))
            if re.search(r'cmd LC_ID_DYLIB\s', block):
                match = re.search(r'^\s*name (.+) \(offset \d+\)', block, re.M)
                if match:
                    install_ids.add(match.group(1))
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
            if re.search(r'(?:libsphinxbase|libsphinxad|libpocketsphinx\.[0-4](?:\.|$))', dependency, re.I):
                errors.append(f'{relative}: obsolete speech dependency {dependency}')
            if dependency in install_ids or dependency.startswith(('/System/Library/', '/usr/lib/')):
                continue
            if dependency.startswith('/'):
                errors.append(f'{relative}: external library {dependency}')
            elif dependency.startswith('@rpath/'):
                # Frameworks is also the PyInstaller bootloader's runtime
                # library directory; extension modules add their own rpaths.
                suffix = dependency[len('@rpath/'):]
                candidates = [base / suffix for base in [*rpaths, framework_dir]]
                if not any(candidate.exists() and inside_bundle(candidate) for candidate in candidates):
                    errors.append(f'{relative}: unresolved library {dependency}')
            elif dependency.startswith(('@loader_path/', '@executable_path/')):
                target = expand_path(dependency, path.parent)
                if not target.exists() or not inside_bundle(target):
                    errors.append(f'{relative}: unresolved or external library {dependency}')
            else:
                errors.append(f'{relative}: unsupported library path {dependency}')
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
