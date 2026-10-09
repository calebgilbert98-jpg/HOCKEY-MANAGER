# PyInstaller spec for Puck Dynasty NATIVE v2.
#
# LESSON FROM V1: never rely on filesystem scanning (_collect_screens)
# or on PyInstaller's AST analysis alone. Every v2 module is listed
# EXPLICITLY in hiddenimports below. Adding a screen means adding it
# here, in screens/__init__.py, and in NAV_ORDER -- three places,
# all static, all visible.
#
# To add a screen:
#   1. native_ui_v2/screens/<name>.py
#   2. import + registry entry in native_ui_v2/screens/__init__.py
#   3. hiddenimports entry below

import os as _os

block_cipher = None

_spec_dir = _os.path.dirname(_os.path.abspath(SPEC))

# --- EXPLICIT module list. No scanning. Every v2 module, named. ---
V2_MODULES = [
    # package inits
    "native_ui_v2",
    "native_ui_v2.main_window",
    "native_ui_v2.theme",
    "native_ui_v2.screens",
    "native_ui_v2.widgets",
    # screens (static registry -- keep in sync with screens/__init__.py)
    "native_ui_v2.screens.base",
    "native_ui_v2.screens.dashboard",
    "native_ui_v2.screens.roster",
    "native_ui_v2.screens.standings",
]

a = Analysis(
    ["puck_dynasty_v2.py"],
    pathex=[_spec_dir],
    binaries=[],
    datas=[
        ("*.png", "."),
        ("icons", "icons"),
        ("assets", "assets"),
        ("puck_dynasty_icon.ico", "."),
    ],
    hiddenimports=[
        "PIL", "PIL.Image", "PIL.ImageDraw",
        "PIL.ImageFont", "PIL.ImageOps",
        "PySide6", "PySide6.QtWidgets", "PySide6.QtCore", "PySide6.QtGui",
        # game engine (imported by the launcher at runtime)
        "game_manager",
        "game_classes",
    ] + V2_MODULES,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "scipy",
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
    name="PuckDynastyV2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="puck_dynasty_icon.ico" if _os.path.exists(
        _os.path.join(_spec_dir, "puck_dynasty_icon.ico")) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PuckDynastyV2",
)
