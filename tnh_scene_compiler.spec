# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for TNH Scene Compiler GUI.

import os

block_cipher = None

a = Analysis(
    [os.path.join("tnh_scene_compiler", "gui.py")],
    pathex=[],
    binaries=[],
    datas=[
        ("allowlists_base", "allowlists_base"),
        ("templates", "templates"),
    ],
    hiddenimports=["yaml"],
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
    a.binaries,
    a.datas,
    [],
    name="TNHSceneCompiler",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
