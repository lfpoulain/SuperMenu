"""Build metadata read from the macOS subproject's VERSION file."""

from __future__ import annotations

import sys
from pathlib import Path


def _application_root() -> Path:
    if getattr(sys, "frozen", False):
        extraction_dir = getattr(sys, "_MEIPASS", None)
        if extraction_dir:
            return Path(extraction_dir)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _read_version() -> str:
    try:
        return (_application_root() / "VERSION").read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        return "dev"


APP_VERSION = _read_version()
BUILD_CHANNEL = "stable"
