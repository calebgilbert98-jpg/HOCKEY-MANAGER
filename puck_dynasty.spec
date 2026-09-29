# PyInstaller spec for Puck Dynasty.
# Built by GitHub Actions on every push to main; produces a standalone
# folder (not a single .exe) so startup stays fast with 95 modules.
# Adding new .py files requires no spec changes -- they're force-included
# below (see _first_party). Do NOT rely on Analysis auto-discovery alone:
# on 2026-09-28 the CI-built exe silently dropped ui_components even though
# main.py imports it at top level, breaking every launch.

import os as _os

block_cipher = None

# Every first-party top-level module, force-bundled. Excludes the entry
# script itself, QA scripts, and the headless dev loader.
_spec_dir = _os.path.dirname(_os.path.abspath(SPEC))
_first_party = sorted(
    _f[:-3] for _f in _os.listdir(_spec_dir)
    if _f.endswith('.py')
    and _f != 'main.py'
    and not _f.startswith(('qa_', 'pt'))
)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('*.png', '.'),
        ('icons', 'icons'),
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageDraw',
        'PIL.ImageFont', 'PIL.ImageOps',
        'customtkinter',
    ] + _first_party,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PuckDynasty',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed app -- no console popup
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PuckDynasty',
)
