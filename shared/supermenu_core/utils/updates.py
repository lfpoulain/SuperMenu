"""Release rules shared by the Windows and macOS update checks.

Both apps read the same GitHub releases, published by the same workflows:
the version format and its ordering, the update channels, where the release
manifests are published, how they are fetched and decoded, the optional
SHA-256 fingerprint they declare and the Windows line of the release notes
must stay identical on both platforms. Assets, the rest of the manifest
validation, version extraction, user-facing messages and the HTTP transport
remain platform-specific.
"""

import json
import re
from typing import Optional, Tuple

# Single source of truth, shared with both platforms' settings.
from supermenu_core.config.provider_settings import (
    UPDATE_CHANNELS,
    normalize_update_channel,
)


UPDATE_CHANNEL_STABLE = "stable"
UPDATE_CHANNEL_BETA = "beta"

MANIFEST_SCHEMA_VERSION = 1

VERSION_PATTERN = re.compile(
    r"v?(\d+\.\d+\.\d+(?:-(?:beta|rc)\.\d+)?)",
    re.IGNORECASE,
)
# "Windows version: X" (metadata line) or "Windows : `X`" (beta summary line).
# Windows reads its version there; macOS only detects it, never uses it.
WINDOWS_VERSION_LINE = re.compile(
    rf"Windows(?:\s+version)?\s*:\s*`?{VERSION_PATTERN.pattern}",
    re.IGNORECASE,
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")

__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "SHA256_PATTERN",
    "UPDATE_CHANNELS",
    "UPDATE_CHANNEL_BETA",
    "UPDATE_CHANNEL_STABLE",
    "VERSION_PATTERN",
    "WINDOWS_VERSION_LINE",
    "declared_sha256",
    "decode_release_manifest",
    "is_newer_version",
    "normalize_update_channel",
    "parse_version",
    "release_manifest_url",
    "request_release_manifest",
]


def parse_version(value: str) -> Tuple[int, ...]:
    normalized = str(value or "").strip().lower()
    match = re.fullmatch(
        r"v?(\d+)\.(\d+)\.(\d+)(?:-(beta|rc)\.(\d+))?",
        normalized,
    )
    if not match:
        return ()

    major, minor, patch = (int(match.group(i)) for i in range(1, 4))
    prerelease_kind = match.group(4)
    prerelease_number = int(match.group(5) or 0)
    stage_rank = {
        "beta": 0,
        "rc": 1,
        None: 2,
    }[prerelease_kind]
    return major, minor, patch, stage_rank, prerelease_number


def is_newer_version(current: Optional[str], candidate: Optional[str]) -> bool:
    if not candidate:
        return False
    parsed_candidate = parse_version(candidate)
    if not parsed_candidate:
        return False
    parsed_current = parse_version(current or "")
    if not parsed_current:
        return True
    return parsed_candidate > parsed_current


def release_manifest_url(releases_url: str, channel: str, manifest_name: str) -> str:
    """Locate a manifest: beside the moving beta tag, or the latest stable release.

    ``releases_url`` is the repository's ``.../releases`` page; ``channel``
    must already be normalized.
    """
    if channel == UPDATE_CHANNEL_BETA:
        return f"{releases_url}/download/beta/{manifest_name}"
    return f"{releases_url}/latest/download/{manifest_name}"


def request_release_manifest(http_get, url: str, timeout_s: int):
    """GET a manifest with ``http_get``; ``None`` when the release has none."""
    response = http_get(
        url,
        timeout=(5, timeout_s),
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        },
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response


def decode_release_manifest(response, unreadable_message: str):
    """Decode a manifest body, tolerating a UTF-8 BOM, or raise ``ValueError``."""
    try:
        return json.loads(response.content.decode("utf-8-sig"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(unreadable_message) from exc


def declared_sha256(payload: dict, invalid_message: str) -> Optional[str]:
    """Return the manifest's lowercase SHA-256, or ``None`` when it has none.

    Manifests published before the fingerprint was added have no sha256;
    a declared one must be valid, otherwise ``ValueError(invalid_message)``
    rejects the manifest.
    """
    if payload.get("sha256") is None:
        return None
    sha256 = str(payload.get("sha256")).strip().lower()
    if not SHA256_PATTERN.fullmatch(sha256):
        raise ValueError(invalid_message)
    return sha256
