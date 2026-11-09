# -*- mode: python ; coding: utf-8 -*-
import os
import runpy
import sysconfig
from PyInstaller.utils.hooks import copy_metadata

version = {}
exec(open(os.path.join(SPECPATH, 'subsync', 'version.py')).read(), version)
distribution = os.environ.get('SUBSYNC_DISTRIBUTION', 'public')
if distribution not in ('public', 'appstore'):
    raise ValueError('SUBSYNC_DISTRIBUTION must be public or appstore')
store = distribution == 'appstore'
app_name = os.environ.get('SUBSYNC_APP_NAME', 'SubSync ARM Store Preview' if store else 'SubSync ARM')
bundle_id = os.environ.get('SUBSYNC_BUNDLE_ID', 'org.kmihalj.subsync.arm64.store' if store else 'org.kmihalj.subsync.arm64.modern')
metadata = runpy.run_path(os.path.join(SPECPATH, 'tools/macos/version_metadata.py'))
marketing_version, build_number = metadata['bundle_versions'](version['version_short'])
ui_languages = runpy.run_path(os.path.join(SPECPATH, 'subsync/data/uilanguages.py'))['NAMES']
identity = os.environ.get('SUBSYNC_CODESIGN_IDENTITY') or None
entitlements = os.path.join(SPECPATH, 'resources/appstore.entitlements') if store else None
prefix = os.environ.get('SUBSYNC_DEPS_PREFIX', os.path.join(SPECPATH, '.build', 'modern-prefix'))
data_files = [
    ('LICENSE', '.'),
    ('subsync/key.pub', '.'),
    ('subsync/img', 'img'),
    ('subsync/locale', 'locale'),
    ('doc/macos-modern-deps.md', 'documentation'),
    (os.path.join(prefix, 'share', 'licenses'), 'licenses/native'),
    ('gizmo/frontend/LICENSE.compatibility', 'licenses/frontend'),
    ('gizmo/frontend/LICENSE.pocketsphinx', 'licenses/frontend'),
    ('gizmo/frontend/UPSTREAM.md', 'licenses/frontend'),
    # Preserve every retained per-file notice and provenance receipt in the
    # binary distribution, including the historical compatibility portions.
    ('gizmo/frontend', 'licenses/frontend/source'),
    (os.path.join(sysconfig.get_path('stdlib'), 'LICENSE.txt'), 'licenses/python'),
]
for dependency in ('wxPython', 'cryptography', 'certifi', 'requests', 'pysubs2', 'PyYAML', 'cffi', 'numpy', 'pybind11', 'pyinstaller'):
    data_files += copy_metadata(dependency)

a = Analysis(
    ['bin/subsync'],
    pathex=[SPECPATH],
    binaries=[],
    datas=data_files,
    hiddenimports=['certifi'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='subsync',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=identity,
    entitlements_file=entitlements,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=app_name)
app = BUNDLE(
    coll,
    name=app_name + '.app',
    icon='resources/icon.icns',
    bundle_identifier=bundle_id,
    info_plist={
        'CFBundleName': app_name,
        'CFBundleDisplayName': app_name,
        'CFBundleShortVersionString': marketing_version,
        'CFBundleVersion': build_number,
        'CFBundleDevelopmentRegion': 'en',
        'CFBundleLocalizations': sorted(ui_languages),
        'LSApplicationCategoryType': 'public.app-category.video',
        'SubSyncDistribution': distribution,
        'LSMinimumSystemVersion': os.environ.get('MACOSX_DEPLOYMENT_TARGET', '11.0'),
        'NSHighResolutionCapable': True,
    },
)
