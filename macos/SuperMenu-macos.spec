# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path


project_dir = Path(SPECPATH)
shared_dir = project_dir.parent / "shared"
version = (project_dir / "VERSION").read_text(encoding="utf-8").strip()
codesign_identity = os.environ.get("MACOS_CODESIGN_IDENTITY") or None

a = Analysis(
    ["run.py"],
    pathex=[str(project_dir), str(shared_dir)],
    binaries=[("build/native/SuperMenuFoundationModels", "native")],
    datas=[
        ("resources", "resources"),
        ("VERSION", "."),
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
        "LSMinimumSystemVersion": "12.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
    },
)
