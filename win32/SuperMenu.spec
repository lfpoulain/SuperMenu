# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata


project_dir = Path(SPECPATH)
shared_dir = project_dir.parent / "shared"

foundry_datas, foundry_binaries, foundry_imports = [], [], []
for package in ("foundry_local_sdk", "foundry_local_core_winml", "onnxruntime_core", "onnxruntime_genai_core"):
    data, binaries, imports = collect_all(package)
    foundry_datas += data
    foundry_binaries += binaries
    foundry_imports += imports
foundry_datas += copy_metadata("foundry-local-sdk-winml")

a = Analysis(
    ['run.py'],
    pathex=[str(project_dir), str(shared_dir)],
    binaries=foundry_binaries,
    datas=[
        ('resources', 'resources'),
    ] + foundry_datas,
    hiddenimports=foundry_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Qt 6.11 uses Windows' ICU API. A different ICU on the build machine's PATH
# (e.g. Poppler/Conda) exports versioned symbols and breaks QtCore at startup.
# These unversioned Windows ICU DLLs must be resolved from the target OS.
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower()
              not in {"icuuc.dll", "icuin.dll", "icudt.dll"}]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SuperMenu',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources\\icons\\app_icon.ico'],
)
