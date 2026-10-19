"""Update lookup for the signed Apple Silicon DMG distribution."""

from __future__ import annotations

import re

import requests

# Single source of truth, shared with src.config.settings and with Windows.
from supermenu_core.config.provider_settings import normalize_update_channel
# Version, manifest and release-notes rules are shared with Windows.
from supermenu_core.utils.updates import (
    MANIFEST_SCHEMA_VERSION as _MANIFEST_SCHEMA_VERSION,
    VERSION_PATTERN as _VERSION_PATTERN,
    WINDOWS_VERSION_LINE as _WINDOWS_VERSION_LINE,
    declared_sha256,
    decode_release_manifest,
    is_newer_version,
    parse_version,
    release_manifest_url,
    request_release_manifest,
)
# Formerly defined here; still exposed under its previous name.
from supermenu_core.utils.updates import (  # noqa: F401
    SHA256_PATTERN as _SHA256_PATTERN,
)


REPOSITORY_RELEASES_URL = "https://github.com/lfpoulain/SuperMenu/releases"
_REPOSITORY_DOWNLOADS_URL = f"{REPOSITORY_RELEASES_URL}/download"
# "macOS version: X" (metadata line) or "macOS Apple Silicon : `X`" (beta
# summary line). Windows lines are only detected, never used as a version.
_MACOS_VERSION_LINE = re.compile(
    rf"macOS(?:\s+version|\s+Apple\s+Silicon)?\s*:\s*`?{_VERSION_PATTERN.pattern}",
    re.IGNORECASE,
)

__all__ = [
    "REPOSITORY_RELEASES_URL",
    "check_latest_release",
    "dmg_asset_name",
    "extract_version",
    "find_dmg_download_url",
    "is_newer_version",
    "normalize_update_channel",
    "parse_version",
    "release_manifest_name",
]


def dmg_asset_name(channel: str) -> str:
    if normalize_update_channel(channel) == "beta":
        return "SuperMenu_Beta-macOS-arm64.dmg"
    return "SuperMenu-macOS-arm64.dmg"


def release_manifest_name(channel: str) -> str:
    if normalize_update_channel(channel) == "beta":
        return "update-macos-beta.json"
    return "update-macos-stable.json"


def find_dmg_download_url(release: dict, channel: str) -> str:
    expected_name = dmg_asset_name(channel).casefold()
    for asset in release.get("assets") or ():
        if str(asset.get("name") or "").casefold() == expected_name:
            return str(asset.get("browser_download_url") or "")
    return ""


def _release_from_manifest(payload: dict, expected_channel: str) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Le manifeste macOS n'est pas un objet JSON.")
    if payload.get("schema_version") != _MANIFEST_SCHEMA_VERSION:
        raise ValueError("Version de manifeste macOS incompatible.")
    if payload.get("platform") != "macos" or payload.get("architecture") != "arm64":
        raise ValueError("Le manifeste ne cible pas cette version de macOS.")

    channel = normalize_update_channel(payload.get("channel"))
    if channel != expected_channel or payload.get("channel") != expected_channel:
        raise ValueError("Le canal du manifeste macOS est incorrect.")

    version = str(payload.get("version") or "").strip()
    if not parse_version(version):
        raise ValueError("La version du manifeste macOS est invalide.")

    prerelease = payload.get("prerelease")
    if prerelease is not (expected_channel == "beta"):
        raise ValueError("Le type de release macOS est incorrect.")

    tag = str(payload.get("tag") or "").strip()
    if expected_channel == "beta":
        if tag != "beta":
            raise ValueError("Le tag de la release beta macOS est incorrect.")
    elif not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        # Windows and macOS deliberately keep separate app versions. The
        # shared stable release tag therefore only has to be a stable tag.
        raise ValueError("Le tag de la release stable macOS est incorrect.")

    asset_name = dmg_asset_name(expected_channel)
    if payload.get("asset") != asset_name:
        raise ValueError("Le DMG déclaré dans le manifeste est incorrect.")

    # Older manifests have no fingerprint; a declared one must be valid.
    sha256 = declared_sha256(
        payload, "L'empreinte SHA-256 du manifeste macOS est invalide."
    ) or ""

    return {
        "channel": expected_channel,
        "version": version,
        "url": f"{_REPOSITORY_DOWNLOADS_URL}/{tag}/{asset_name}",
        "release_url": f"{REPOSITORY_RELEASES_URL}/tag/{tag}",
        "sha256": sha256,
    }


def _manifest_url(channel: str) -> str:
    return release_manifest_url(
        REPOSITORY_RELEASES_URL, channel, release_manifest_name(channel)
    )


def _get_release_manifest(channel: str, timeout_s: int) -> dict | None:
    response = request_release_manifest(
        requests.get, _manifest_url(channel), timeout_s
    )
    if response is None:
        return None
    payload = decode_release_manifest(
        response, "Le manifeste de mise à jour macOS est illisible."
    )
    return _release_from_manifest(payload, channel)


def _get_release_from_api(channel: str, timeout_s: int) -> dict:
    if channel == "beta":
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
    if bool(release.get("prerelease")) != (channel == "beta"):
        raise ValueError("Le type de release GitHub ne correspond pas au canal.")

    download_url = find_dmg_download_url(release, channel)
    if not download_url:
        raise ValueError("Cette release ne contient aucun DMG macOS compatible.")
    version = extract_version(release)
    if not version:
        raise ValueError(
            "Impossible de déterminer la version macOS de cette release."
        )
    return {
        "channel": channel,
        "version": version,
        "url": download_url,
        "release_url": release.get("html_url") or REPOSITORY_RELEASES_URL,
    }


def check_latest_release(channel: str, timeout_s: int = 15) -> dict:
    normalized = normalize_update_channel(channel)
    try:
        manifest_release = _get_release_manifest(normalized, timeout_s)
    except (requests.RequestException, ValueError):
        manifest_release = None
    if manifest_release is not None:
        return manifest_release
    return _get_release_from_api(normalized, timeout_s)


def extract_version(release: dict) -> str:
    body = str(release.get("body") or "")
    # The metadata lines are appended after the human notes: the last wins.
    macos_versions = _MACOS_VERSION_LINE.findall(body)
    if macos_versions:
        return macos_versions[-1]
    if _WINDOWS_VERSION_LINE.search(body):
        # Both platforms keep separate versions; the tag, the name and the
        # rest of the body then describe Windows, never this Mac build.
        return ""

    for value in (release.get("tag_name"), release.get("name"), body):
        match = _VERSION_PATTERN.search(str(value or ""))
        if match:
            return match.group(1)
    return ""
