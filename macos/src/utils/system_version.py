"""Running macOS version, read in a way a compatibility mode cannot lower."""

from __future__ import annotations

import os
import platform
import subprocess
import sys

_sw_vers_major: int | None = None


def _read_sw_vers_major() -> int:
    """Ask sw_vers, which reports the real version whatever SDK built Python."""
    if sys.platform != "darwin":
        return 0
    try:
        output = subprocess.run(
            ["/usr/bin/sw_vers", "-productVersion"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
            env={**os.environ, "SYSTEM_VERSION_COMPAT": "0"},
        ).stdout
        return int(output.strip().split(".")[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return 0


def _mac_ver_major() -> int:
    try:
        return int(platform.mac_ver()[0].split(".")[0])
    except (ValueError, IndexError):
        return 0


def macos_major_version() -> int:
    """Return the macOS major version, or 0 when it cannot be read.

    ``platform.mac_ver()`` alone is not enough: an executable linked against
    an older SDK is shown a compatibility version (16 instead of 26), which
    would hide Apple Intelligence and Apple Speech on a Mac that has them.
    A compatibility version is always the lower one, so the higher of the two
    readings is the real one. sw_vers is run once per session.
    """
    global _sw_vers_major
    if _sw_vers_major is None:
        _sw_vers_major = _read_sw_vers_major()
    return max(_sw_vers_major, _mac_ver_major())
