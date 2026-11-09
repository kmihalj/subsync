"""Read the distribution policy without touching preferences or model data."""
import os
from pathlib import Path
import plistlib
import sys


def distribution_name(*, environ=None, frozen=None, bundle_info=None):
    """Frozen public apps ignore environment attempts to enable store policy."""
    if frozen is None:
        frozen = bool(getattr(sys, 'frozen', False))
    if frozen:
        if bundle_info is None:
            try:
                with (Path(sys.executable).parent.parent / 'Info.plist').open('rb') as stream:
                    bundle_info = plistlib.load(stream)
            except (OSError, ValueError, plistlib.InvalidFileException):
                bundle_info = {}
        value = bundle_info.get('SubSyncDistribution', 'public')
    else:
        value = (os.environ if environ is None else environ).get(
            'SUBSYNC_DISTRIBUTION', 'public')
    return 'appstore' if value == 'appstore' else 'public'


def is_appstore_build():
    return sys.platform == 'darwin' and distribution_name() == 'appstore'
