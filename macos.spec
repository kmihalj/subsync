# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import copy_metadata

version = {}
exec(open(os.path.join(SPECPATH, 'subsync', 'version.py')).read(), version)
app_name = os.environ.get('SUBSYNC_APP_NAME', 'SubSync ARM Modern')
bundle_id = os.environ.get('SUBSYNC_BUNDLE_ID', 'org.kmihalj.subsync.arm64.modern')
prefix = os.environ.get('SUBSYNC_DEPS_PREFIX', os.path.join(SPECPATH, '.build', 'modern-prefix'))
data_files = [
    ('LICENSE', '.'),
    ('subsync/key.pub', '.'),
    ('subsync/img', 'img'),
    ('subsync/locale', 'locale'),
    ('doc/macos-arm64.md', 'documentation'),
    ('doc/macos-modern-deps.md', 'documentation'),
    (os.path.join(prefix, 'share', 'licenses'), 'licenses/native'),
    ('gizmo/frontend/LICENSE.compatibility', 'licenses/frontend'),
    ('gizmo/frontend/LICENSE.pocketsphinx', 'licenses/frontend'),
    ('gizmo/frontend/UPSTREAM.md', 'licenses/frontend'),
    # Preserve every retained per-file notice and provenance receipt in the
    # binary distribution, including the historical compatibility portions.
    ('gizmo/frontend', 'licenses/frontend/source'),
]
for distribution in ('wxPython', 'cryptography', 'certifi', 'requests', 'pysubs2', 'PyYAML', 'cffi', 'numpy'):
    data_files += copy_metadata(distribution)

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
    codesign_identity=None,
    entitlements_file=None,
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
        'CFBundleShortVersionString': version['version_short'],
        'CFBundleVersion': version['version_short'],
        'LSMinimumSystemVersion': os.environ.get('MACOSX_DEPLOYMENT_TARGET', '11.0'),
        'NSHighResolutionCapable': True,
    },
)
