# -*- mode: python ; coding: utf-8 -*-

import importlib.util
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata


project_dir = Path(SPECPATH)
shared_dir = project_dir.parent / "shared"
repository_dir = project_dir.parent

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
        # SuperMenu's own terms and the third-party notices ship with the app.
        (str(repository_dir / 'LICENSE'), '.'),
        (str(repository_dir / 'THIRD_PARTY_NOTICES.md'), '.'),
        (str(repository_dir / 'licenses'), 'licenses'),
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
# Libraries collected by the Qt hooks that SuperMenu never loads. They are
# left out so their licenses do not apply to the build:
# - Qt Virtual Keyboard is only available under GPL-3.0 or a commercial
#   license, unlike the LGPL Qt libraries (every input context plugin is
#   collected by the QtGui hook);
# - the PDF image plugin and Qt Pdf embed PDFium;
# - opengl32sw.dll is Mesa's software OpenGL; SuperMenu draws with Qt's
#   raster engine and never uses OpenGL.
_UNUSED_QT_FILES = {"qpdf.dll", "qt6pdf.dll", "opengl32sw.dll"}


def _is_shipped(entry):
    name = entry[0].lower()
    return "virtualkeyboard" not in name and Path(name).name not in _UNUSED_QT_FILES


a.binaries = [entry for entry in a.binaries if _is_shipped(entry)]
a.datas = [entry for entry in a.datas if _is_shipped(entry)]

# License files of every third-party distribution actually bundled, copied
# from the build environment. A distribution without one only warns. The
# folder is also written next to the executable for the installer.
_collector_spec = importlib.util.spec_from_file_location(
    "collect_third_party_licenses",
    repository_dir / "tools" / "collect_third_party_licenses.py",
)
license_collector = importlib.util.module_from_spec(_collector_spec)
_collector_spec.loader.exec_module(license_collector)
a.datas += license_collector.pyinstaller_datas(
    Path(DISTPATH) / "third_party_licenses",
    requirement_files=[project_dir / "requirements.txt"],
    toc=a.pure + a.binaries + a.datas + a.scripts,
)
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
