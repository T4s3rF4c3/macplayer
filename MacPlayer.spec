# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for MacPlayer.
Works on both macOS (produces .app) and Windows (produces .exe folder).

Build:
    pyinstaller MacPlayer.spec
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

icon = "assets/icon.icns" if IS_MAC else "assets/icon.ico"

# Collect all PySide6 components (DLLs, plugins, Qt platform files)
pyside6_datas, pyside6_binaries, pyside6_hiddenimports = collect_all("PySide6")

# ---------------------------------------------------------------------------
a = Analysis(
    ["main.py"],
    pathex=[str(Path(".").resolve())],
    binaries=pyside6_binaries,
    datas=[
        ("ui", "ui"),
        *pyside6_datas,
    ],
    hiddenimports=[
        *pyside6_hiddenimports,
        "vlc",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "IPython",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MacPlayer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # no terminal window
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MacPlayer",
)

# macOS-only: wrap into a proper .app bundle
if IS_MAC:
    app = BUNDLE(
        coll,
        name="MacPlayer.app",
        icon=icon,
        bundle_identifier="com.ah-tech.macplayer",
        info_plist={
            "CFBundleName":             "MacPlayer",
            "CFBundleDisplayName":      "MacPlayer",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion":          "1.0.0",
            "NSHighResolutionCapable":  True,
            "NSRequiresAquaSystemAppearance": False,   # supports dark mode
            "LSMinimumSystemVersion":   "11.0",
            "NSMicrophoneUsageDescription": "",
        },
    )
