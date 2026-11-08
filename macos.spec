# -*- mode: python ; coding: utf-8 -*-
import os

version = {}
exec(open(os.path.join(SPECPATH, 'subsync', 'version.py')).read(), version)
app_name = os.environ.get('SUBSYNC_APP_NAME', 'SubSync ARM')
bundle_id = os.environ.get('SUBSYNC_BUNDLE_ID', 'org.kmihalj.subsync.arm64')

a = Analysis(
    ['bin/subsync'],
    pathex=[SPECPATH],
    binaries=[],
    datas=[
        ('LICENSE', '.'),
        ('subsync/key.pub', '.'),
        ('subsync/img', 'img'),
        ('subsync/locale', 'locale'),
    ],
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
