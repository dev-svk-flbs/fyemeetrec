# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for FyeLabs Recording System
Bundles Python + All Dependencies + FFmpeg into ONE executable folder
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all data files from packages
datas = []
datas += collect_data_files('faster_whisper')
datas += collect_data_files('flask')
datas += collect_data_files('flask_login')

# Add your application templates and static files
datas += [('templates', 'templates')]
datas += [('static', 'static')]

# Add FFmpeg binaries
datas += [('ffmpeg/bin/ffmpeg.exe', 'ffmpeg/bin')]
datas += [('ffmpeg/bin/ffprobe.exe', 'ffmpeg/bin')]

# Collect all hidden imports
hiddenimports = []
hiddenimports += collect_submodules('flask')
hiddenimports += collect_submodules('flask_login')
hiddenimports += collect_submodules('flask_sqlalchemy')
hiddenimports += collect_submodules('faster_whisper')
hiddenimports += collect_submodules('websockets')
hiddenimports += collect_submodules('keyboard')
hiddenimports += collect_submodules('plyer')
hiddenimports += collect_submodules('boto3')
hiddenimports += collect_submodules('av')
hiddenimports += [
    'sqlalchemy.ext.baked',
    'engineio.async_drivers.threading',
    'pywintypes',
    'win32api',
    'win32con',
]

a = Analysis(
    ['launcher_frozen.py'],  # Use the frozen-compatible launcher
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'jupyter',
        'notebook',
        'jupyterlab',
        'matplotlib',
        'tkinter',
        'test',
        'tests',
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
    name='FyeLabs Recording System',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Set to False to hide console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static/image.png' if os.path.exists('static/image.png') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FyeLabs Recording System',
)
