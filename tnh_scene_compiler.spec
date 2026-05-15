# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for TNH Scene Compiler GUI.

import os
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "tnh_scene_compiler",
    os.path.join("tnh_scene_compiler", "__init__.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_version = _mod.__version__

block_cipher = None

a = Analysis(
    ["run_gui.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("allowlists_base", "allowlists_base"),
        ("templates", "templates"),
        ("thumbnails", "thumbnails"),
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
    name=f"TNHSceneCompiler-{_version}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
