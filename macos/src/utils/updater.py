"""Lightweight update lookup for the macOS DMG distribution."""

from __future__ import annotations

import re

import requests

# Single source of truth, shared with src.config.settings and with Windows.
from supermenu_core.config.provider_settings import normalize_update_channel


REPOSITORY_RELEASES_URL = "https://github.com/lfpoulain/SuperMenu/releases"
_VERSION_PATTERN = re.compile(
    r"v?(\d+\.\d+\.\d+(?:-(?:beta|rc)\.\d+)?)",
    re.IGNORECASE,
)

__all__ = [
    "REPOSITORY_RELEASES_URL",
    "check_latest_release",
    "extract_version",
    "is_newer_version",
    "normalize_update_channel",
    "parse_version",
]


def parse_version(value: str) -> tuple[int, ...]:
    match = re.fullmatch(
        r"v?(\d+)\.(\d+)\.(\d+)(?:-(beta|rc)\.(\d+))?",
        str(value or "").strip().lower(),
    )
    if not match:
        return ()
    stage = {"beta": 0, "rc": 1, None: 2}[match.group(4)]
    return (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        stage,
        int(match.group(5) or 0),
    )


def is_newer_version(current: str, candidate: str) -> bool:
    parsed_candidate = parse_version(candidate)
    if not parsed_candidate:
        return False
    parsed_current = parse_version(current)
    return not parsed_current or parsed_candidate > parsed_current


def check_latest_release(channel: str, timeout_s: int = 15) -> dict:
    normalized = normalize_update_channel(channel)
    if normalized == "beta":
        url = (
            "https://api.github.com/repos/lfpoulain/SuperMenu/"
            "releases/tags/beta"
        )
    else:
        url = (
            "https://api.github.com/repos/lfpoulain/SuperMenu/"
            "releases/latest"
        )
    response = requests.get(
        url,
        timeout=(5, timeout_s),
        headers={"Accept": "application/vnd.github+json"},
    )
    response.raise_for_status()
    release = response.json()
    version = extract_version(release)
    return {
        "channel": normalized,
        "version": version,
        "url": release.get("html_url") or REPOSITORY_RELEASES_URL,
    }


def extract_version(release: dict) -> str:
    for value in (
        release.get("tag_name"),
        release.get("name"),
        release.get("body"),
    ):
        match = _VERSION_PATTERN.search(str(value or ""))
        if match:
            return match.group(1)
    return ""
