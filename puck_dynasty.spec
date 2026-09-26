# PyInstaller spec for Puck Dynasty.
# Built by GitHub Actions on every push to main; produces a standalone
# folder (not a single .exe) so startup stays fast with 95 modules.
# Adding new .py files requires no spec changes -- they're auto-discovered.

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('*.png', '.'),
        ('icons', 'icons'),
    ],
    hiddenimports=[
        'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageDraw',
        'PIL.ImageFont', 'PIL.ImageOps',
    ],
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
