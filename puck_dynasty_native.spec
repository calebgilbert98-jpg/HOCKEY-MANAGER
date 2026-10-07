# PyInstaller spec for Puck Dynasty NATIVE (PySide6/Qt).
# Built by GitHub Actions on push to native-ui branch.
# No Flask, no browser, no web_ui -- pure Qt native application.

import os as _os

# Collect every native_ui screen/widget submodule.  Screens are loaded via
# dynamic __import__ in MainWindow._register_all_screens, which PyInstaller's
# static analysis cannot see -- without this, the Windows bundle ships with
# NO screens (setup wizard never appears, all nav clicks silently fail).
#
# NOTE: We scan the filesystem directly instead of using
# PyInstaller.utils.hooks.collect_submodules, because collect_submodules
# needs the package importable at spec-parse time and can return empty
# silently on the GitHub runner.  This scan cannot fail silently.
from PyInstaller.utils.hooks import collect_submodules as _collect_submodules  # noqa: F401 (kept for reference)

block_cipher = None

_spec_dir = _os.path.dirname(_os.path.abspath(SPEC))
_first_party = sorted(
    _f[:-3] for _f in _os.listdir(_spec_dir)
    if _f.endswith('.py')
    and _f not in ('main.py', 'puck_dynasty_native.py')
    and not _f.startswith(('qa_', 'pt'))
)

def _collect_screens():
    """Scan native_ui/screens/*.py and native_ui/widgets/*.py directly."""
    mods = []
    for pkg, subdir in [('native_ui.screens', 'native_ui/screens'),
                        ('native_ui.widgets', 'native_ui/widgets')]:
        d = _os.path.join(_spec_dir, subdir)
        if _os.path.isdir(d):
            for f in _os.listdir(d):
                if f.endswith('.py') and f != '__init__.py':
                    mods.append(f"{pkg}.{f[:-3]}")
    return sorted(mods)

_screen_mods = _collect_screens()

a = Analysis(
    ['puck_dynasty_native.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('*.png', '.'),
        ('icons', 'icons'),
        ('assets', 'assets'),
        ('puck_dynasty_icon.ico', '.'),
    ],
    hiddenimports=[
        'PIL', 'PIL.Image', 'PIL.ImageDraw',
        'PIL.ImageFont', 'PIL.ImageOps',
        'PySide6', 'PySide6.QtWidgets', 'PySide6.QtCore', 'PySide6.QtGui',
        'native_ui', 'native_ui.main_window', 'native_ui.theme',
        'native_ui.screens', 'native_ui.screens.base',
        'native_ui.widgets', 'native_ui.widgets.player_table',
        'native_ui.widgets.attribute_bar',
    ] + _screen_mods \
      + _first_party,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'flask', 'werkzeug', 'jinja2',
        'tkinter', 'customtkinter',
        'web_ui',
    ],
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='puck_dynasty_icon.ico',
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
