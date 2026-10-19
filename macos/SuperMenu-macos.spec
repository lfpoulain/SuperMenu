# -*- mode: python ; coding: utf-8 -*-

import importlib.util
import os
from pathlib import Path


project_dir = Path(SPECPATH)
shared_dir = project_dir.parent / "shared"
repository_dir = project_dir.parent
version = (project_dir / "VERSION").read_text(encoding="utf-8").strip()
codesign_identity = os.environ.get("MACOS_CODESIGN_IDENTITY") or None

a = Analysis(
    ["run.py"],
    pathex=[str(project_dir), str(shared_dir)],
    binaries=[("build/native/SuperMenuFoundationModels", "native"),
              ("build/native/SuperMenuSpeech", "native")],
    datas=[
        ("resources", "resources"),
        ("VERSION", "."),
        # SuperMenu's own terms and the third-party notices ship with the app.
        (str(repository_dir / "LICENSE"), "."),
        (str(repository_dir / "THIRD_PARTY_NOTICES.md"), "."),
        (str(repository_dir / "licenses"), "licenses"),
    ],
    hiddenimports=[
        "pynput.keyboard._darwin",
        "pynput.mouse._darwin",
        # Imported lazily by src.utils.permissions for the Accessibility prompt.
        "HIServices",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Libraries collected by the Qt hooks that SuperMenu never loads. They are
# left out so their licenses do not apply to the build:
# - Qt Virtual Keyboard is only available under GPL-3.0 or a commercial
#   license, unlike the LGPL Qt libraries (every input context plugin is
#   collected by the QtGui hook);
# - the PDF image plugin and QtPdf.framework embed PDFium.
# PyInstaller also links each framework binary it collects into the top-level
# directory: a SYMLINK entry ("QtPdf", ".../QtPdf.framework/Versions/A/QtPdf").
# Such a link leaves with its target, otherwise it dangles in
# Contents/Frameworks and Contents/Resources and codesign rejects the whole
# bundle ("SuperMenu.app: No such file or directory"). The "QtPdf" name is
# also excluded on its own, whatever form the SYMLINK target takes.
def _is_shipped_path(path):
    path = path.lower()
    return (
        "virtualkeyboard" not in path
        and "qtpdf.framework" not in path
        and Path(path).name not in {"libqpdf.dylib", "qtpdf"}
    )


def _is_shipped(entry):
    name, source, typecode = entry
    if typecode == "SYMLINK" and not _is_shipped_path(source):
        return False
    return _is_shipped_path(name)


a.binaries = [entry for entry in a.binaries if _is_shipped(entry)]
a.datas = [entry for entry in a.datas if _is_shipped(entry)]

# License files of every third-party distribution actually bundled, copied
# from the build environment. A distribution without one only warns.
_collector_spec = importlib.util.spec_from_file_location(
    "collect_third_party_licenses",
    repository_dir / "tools" / "collect_third_party_licenses.py",
)
license_collector = importlib.util.module_from_spec(_collector_spec)
_collector_spec.loader.exec_module(license_collector)
a.datas += license_collector.pyinstaller_datas(
    Path(workpath) / "third_party_licenses",
    requirement_files=[project_dir / "requirements.txt"],
    toc=a.pure + a.binaries + a.datas + a.scripts,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SuperMenu",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    # SuperMenu is distributed for Apple Silicon only. Pinning the slice keeps
    # the build honest instead of silently inheriting the runner architecture.
    target_arch="arm64",
    # PyInstaller signs every collected Mach-O binary and enables the
    # hardened runtime when a real Developer ID identity is provided. The
    # entitlements are required by that runtime, see entitlements.plist.
    codesign_identity=codesign_identity,
    entitlements_file=str(project_dir / "entitlements.plist"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SuperMenu",
)

app = BUNDLE(
    coll,
    name="SuperMenu.app",
    icon="resources/icons/app_icon.icns",
    bundle_identifier="com.supermenu.macos",
    version=version,
    info_plist={
        "CFBundleDisplayName": "SuperMenu",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        # Minimum of the PySide6 6.11 wheels (macosx_13_0): Qt does not start
        # on an older macOS.
        "LSMinimumSystemVersion": "13.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": "SuperMenu utilise le microphone uniquement pendant votre dictée pour transcrire votre voix en texte.",
    },
)
