"""Paths used by the standalone macOS application."""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "SuperMenu"


def application_base_dir() -> str:
    """Return the read-only directory containing bundled application assets."""
    if getattr(sys, "frozen", False):
        extraction_dir = getattr(sys, "_MEIPASS", None)
        if extraction_dir:
            return os.path.abspath(extraction_dir)
        return os.path.dirname(os.path.abspath(sys.executable))
    return str(Path(__file__).resolve().parents[2])


def resource_path(*parts: str) -> str:
    return os.path.join(application_base_dir(), *parts)


def user_config_dir() -> Path:
    override = os.getenv("SUPERMENU_CONFIG_DIR")
    path = (
        Path(override).expanduser()
        if override
        else Path.home() / "Library" / "Application Support" / APP_NAME
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> str:
    return str(user_config_dir() / "SuperMenu.ini")


def user_log_dir() -> Path:
    override = os.getenv("SUPERMENU_LOG_DIR")
    path = (
        Path(override).expanduser()
        if override
        else Path.home() / "Library" / "Logs" / APP_NAME
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def packaged_resource_status() -> dict[str, object]:
    icon_path = resource_path("resources", "icons", "icon.png")
    return {
        "ok": os.path.isfile(icon_path),
        "base_dir": application_base_dir(),
        "icon": icon_path,
    }
