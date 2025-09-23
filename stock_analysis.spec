﻿# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files

PROJECT_ROOT = os.path.abspath('.')

extra_datas = [
    (os.path.join(PROJECT_ROOT, "files"), "files"),
    (os.path.join(PROJECT_ROOT, "investar.db"), "."),
]

extra_datas += collect_data_files("plotly")
extra_datas += collect_data_files("FinanceDataReader")

a = Analysis(
    ['stock_analysis.py'],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=extra_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='stock_analysis',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='stock_analysis',
)
