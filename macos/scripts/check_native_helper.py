"""Validate the JSON reply of a native helper smoke test.

Usage: <helper> | python check_native_helper.py foundation|speech

Hosted runners older than macOS 26 can only exercise the os_unsupported
branch of the Swift helpers. That answer is accepted there, but on macOS 26 or
later it means the availability check itself regressed, so the build fails
instead of publishing helpers that were never really executed.
"""

from __future__ import annotations

import json
import subprocess
import sys

FIRST_SUPPORTED_MACOS = 26
FOUNDATION_UNAVAILABLE_CODES = {
    "device_not_eligible",
    "intelligence_disabled",
    "model_not_ready",
    "unavailable",
}


def macos_major_version() -> int:
    """Return the running macOS major version, or 0 when it is unknown.

    sw_vers is asked rather than platform.mac_ver(): a Python built against an
    older SDK can be shown a compatibility version instead of 26.
    """
    try:
        output = subprocess.run(
            ["sw_vers", "-productVersion"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout
        return int(output.strip().split(".")[0])
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def check_reply(kind: str, reply: object, os_major: int) -> None:
    """Raise AssertionError when the helper reply is not acceptable."""
    if kind not in ("foundation", "speech"):
        raise AssertionError(f"Type de helper inconnu : {kind!r}")
    if not isinstance(reply, dict):
        raise AssertionError(f"Réponse JSON inattendue : {reply!r}")
    if kind == "foundation":
        if type(reply.get("ok")) is not bool:
            raise AssertionError(f"Champ ok absent ou invalide : {reply!r}")
        if reply["ok"]:
            return
    elif reply.get("event") == "result":
        return

    code = reply.get("code")
    if code == "os_unsupported":
        if os_major >= FIRST_SUPPORTED_MACOS:
            raise AssertionError(
                f"Le helper répond os_unsupported sur macOS {os_major} : {reply!r}"
            )
        return
    if kind == "foundation" and code in FOUNDATION_UNAVAILABLE_CODES:
        return
    raise AssertionError(f"Réponse inattendue du helper {kind} : {reply!r}")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("foundation", "speech"):
        print("Usage : check_native_helper.py foundation|speech", file=sys.stderr)
        return 2
    try:
        reply = json.load(sys.stdin)
        check_reply(argv[1], reply, macos_major_version())
    except (AssertionError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
