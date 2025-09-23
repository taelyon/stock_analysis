# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files

project_root = os.path.abspath('.')

extra_datas = [
    (os.path.join(project_root, 'files'), 'files'),
    (os.path.join(project_root, 'investar.db'), '.'),
]

a = Analysis(
    ['stock_analysis.py'],
    pathex=[project_root],
    binaries=[],
    datas=extra_datas + collect_data_files('plotly') + collect_data_files('FinanceDataReader'),
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
