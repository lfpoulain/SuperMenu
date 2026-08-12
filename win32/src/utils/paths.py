"""Centralized paths for source and PyInstaller executions."""

from __future__ import annotations

import os
import sys


def application_base_dir() -> str:
    """Return the read-only directory containing bundled application assets."""
    if getattr(sys, "frozen", False):
        extraction_dir = getattr(sys, "_MEIPASS", None)
        if extraction_dir:
            return os.path.abspath(extraction_dir)
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def resource_path(*parts: str) -> str:
    return os.path.join(application_base_dir(), *parts)


def packaged_resource_status() -> dict[str, object]:
    icon_path = resource_path("resources", "icons", "icon.png")
    ffmpeg_path = resource_path("bin", "ffmpeg.exe")
    return {
        "ok": os.path.isfile(icon_path) and os.path.isfile(ffmpeg_path),
        "base_dir": application_base_dir(),
        "icon": icon_path,
        "ffmpeg": ffmpeg_path,
    }
