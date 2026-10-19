"""Release checks run by the beta and stable workflows before anything ships.

The installed updaters only offer a version strictly newer than their own,
read from the update manifests attached to the published releases. A release
whose version is not newer than the published one would therefore never reach
anybody, or would hide an older build behind the Latest badge. These checks
compare versions exactly as the updaters do and use the standard library only,
so they run on a bare runner before any dependency is installed.

Command line, from the repository root:

    python tools/release_guard.py require-newer 1.2.3-beta.80 <manifest URL>
    python tools/release_guard.py make-latest 1.2.3 <manifest URL>
    python tools/release_guard.py notes-heading 1.2.3 .github/STABLE_NOTES.md

A manifest URL answering 404 means nothing is published yet. Any other
failure stops the release after three attempts: a check that cannot run must
not pass.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional, Tuple

_VERSION = re.compile(r"v?(\d+)\.(\d+)\.(\d+)(?:-(beta|rc)\.(\d+))?")
_STAGE_RANK = {"beta": 0, "rc": 1, None: 2}
ATTEMPTS = 3


class ReleaseGuardError(Exception):
    """A check failed; the message is shown in the workflow log."""


def parse_version(value: str) -> Tuple[int, ...]:
    """Same ordering as the Windows and macOS updaters: beta < rc < final."""
    match = _VERSION.fullmatch(str(value or "").strip().lower())
    if not match:
        return ()
    return (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        _STAGE_RANK[match.group(4)],
        int(match.group(5) or 0),
    )


def _require_version(value: str) -> Tuple[int, ...]:
    parsed = parse_version(value)
    if not parsed:
        raise ReleaseGuardError(f"Version illisible : {value!r}")
    return parsed


def fetch_published_version(
    url: str,
    opener: Optional[Callable] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Optional[str]:
    """Return the version of a published manifest, or None when it is absent."""
    opener = opener or urllib.request.urlopen
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "SuperMenu-release-guard"},
    )
    last_error: Optional[Exception] = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with opener(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            last_error = error
        except (urllib.error.URLError, OSError, ValueError) as error:
            last_error = error
        if attempt < ATTEMPTS:
            sleep(5 * attempt)
    else:
        raise ReleaseGuardError(f"Manifeste publié illisible : {url} ({last_error})")

    version = payload.get("version") if isinstance(payload, dict) else None
    if not isinstance(version, str) or not parse_version(version):
        raise ReleaseGuardError(f"Version absente ou invalide dans {url}")
    return version


def require_newer(candidate: str, url: str, **fetch_options) -> str:
    candidate_key = _require_version(candidate)
    published = fetch_published_version(url, **fetch_options)
    if published is None:
        return f"Aucun manifeste publié à {url} : {candidate} accepté."
    if candidate_key <= parse_version(published):
        raise ReleaseGuardError(
            f"{candidate} n'est pas plus récente que la version publiée {published} "
            f"({url}). Les applications installées ne la proposeraient pas."
        )
    return f"{candidate} est plus récente que la version publiée {published}."


def make_latest(candidate: str, url: str, **fetch_options) -> bool:
    """True when the release may take the Latest badge from the current one."""
    candidate_key = _require_version(candidate)
    published = fetch_published_version(url, **fetch_options)
    return published is None or candidate_key > parse_version(published)


def notes_mention_version(notes: str, version: str) -> bool:
    """A Markdown heading names the version as a whole token.

    1.2.1 must not match a heading about 1.2.10 or 11.2.1, and a version quoted
    in the body (such as a licence note about older releases) does not count.
    """
    _require_version(version)
    token = re.compile(rf"(?<![\w.])v?{re.escape(version)}(?!\w|\.\d)")
    for line in notes.splitlines():
        if re.match(r"#{1,6}\s", line) and token.search(line):
            return True
    return False


def main(argv: list[str]) -> int:
    usage = (
        "Usage : release_guard.py require-newer VERSION URL | "
        "make-latest VERSION URL | notes-heading VERSION FICHIER"
    )
    # Workflow logs are UTF-8; a Windows runner would otherwise use its code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if len(argv) != 4:
        print(usage, file=sys.stderr)
        return 2
    command, version, target = argv[1:]
    try:
        if command == "require-newer":
            print(require_newer(version, target))
        elif command == "make-latest":
            print("true" if make_latest(version, target) else "false")
        elif command == "notes-heading":
            notes = Path(target).read_text(encoding="utf-8")
            if not notes_mention_version(notes, version):
                raise ReleaseGuardError(
                    f"{target} doit contenir un titre qui nomme la version {version}."
                )
            print(f"{target} décrit la version {version}.")
        else:
            print(usage, file=sys.stderr)
            return 2
    except ReleaseGuardError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
