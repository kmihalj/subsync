"""Release versions and Apple bundle metadata, independent of the app runtime."""
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def release_version(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)(?:\.(\d+))?', value)
    if not match:
        raise ValueError('Release version must contain two or three numeric components')
    return '.'.join(str(int(part or 0)) for part in match.groups())


def source_version():
    override = os.environ.get('SUBSYNC_RELEASE_VERSION')
    if override:
        return override, release_version(override)
    try:
        description = subprocess.check_output(
            ['git', 'describe', '--tags', '--long'], cwd=ROOT,
            text=True, stderr=subprocess.DEVNULL).strip()
        tag, commits, _ = description.rsplit('-', 2)
        base = release_version(tag)
        return (tag if int(commits) == 0 else description,
                base if int(commits) == 0 else f'{base}.{int(commits)}')
    except (subprocess.CalledProcessError, ValueError):
        return 'development', '0.0.0'


def bundle_versions(short_version, build=None):
    # Development source versions may carry a commit count; Apple requires
    # a three-component marketing version and an independent numeric build.
    parts = short_version.split('.')
    if len(parts) < 3 or not all(part.isdigit() for part in parts):
        raise ValueError('Invalid source version')
    marketing = release_version('.'.join(parts[:3]))
    build = build or os.environ.get('SUBSYNC_BUILD_NUMBER')
    if not build:
        build = subprocess.check_output(['git', 'rev-list', '--count', 'HEAD'],
                                        cwd=ROOT, text=True).strip()
    if not re.fullmatch(r'[1-9]\d{0,3}(?:\.\d{1,2}){0,2}', build):
        raise ValueError('Build number must follow Apple CFBundleVersion format')
    return marketing, build
