# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the status_tools desktop app (Windows & Linux).

Builds an onedir bundle (a folder), which is more reliable than onefile for
PySide6 and is what the Linux AppImage step consumes. Unused heavyweight Qt
modules are excluded to keep the bundle smaller.
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'tkinter',
        'matplotlib',
        'pandas',
        'scipy',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='status_tools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app: no console window
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='status_tools',
)
