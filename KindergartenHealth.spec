# -*- mode: python ; coding: utf-8 -*-
"""Reproducible PyInstaller configuration for the KindergartenHealth desktop app.

Build with:

    python -m PyInstaller KindergartenHealth.spec

Packaging layout: ONE-DIR (``COLLECT``), windowed GUI (``console=False`` so no
console window appears). One-dir is chosen over one-file on purpose:

  * matplotlib / pandas / reportlab unpack a lot of data; one-dir starts far
    faster and avoids re-extracting to a temp dir on every launch;
  * a one-file bundle extracts itself to ``sys._MEIPASS`` which is DELETED on
    exit, so it cannot hold the runtime database (see paths._writable_root).

Runtime data location: the application NEVER writes into the bundle. In a
frozen build ``paths.py`` puts the database, photos and backups under
``%LOCALAPPDATA%\KindergartenHealth\.runtime`` (always writable for the current
user), while development uses the git-ignored ``<repo>\.runtime``.

Deliberately NOT bundled (verified absent from the analysis):
  kindergarten.db, 123.db, photos/, .runtime/, .serena/, tests/, and any
  previously generated exports or backups.
"""

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# tkcalendar ships locale/calendar data and uses babel for localization; both
# are pure-Python data that PyInstaller cannot discover by static import.
datas = []
datas += collect_data_files("tkcalendar")
datas += collect_data_files("babel", include_py_files=False)
# reportlab ships font metrics/encoding data; its hook covers most of it, the
# collection here is a safety net for the Cyrillic font path used by reports.py.
datas += collect_data_files("reportlab", include_py_files=False)

hiddenimports = [
    "tkcalendar",
    "babel",
    "babel.numbers",
    "babel.dates",
    "babel.localedata",
]

# Never packaged: the test suite and any runtime data.
excludedimports = ["tests"]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludedimports,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KindergartenHealth",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,   # windowed GUI: no console window
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
    upx=False,
    upx_exclude=[],
    name="KindergartenHealth",
)
