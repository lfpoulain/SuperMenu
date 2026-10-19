import importlib.util
import io
import json
import urllib.error
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GUARD_PATH = REPOSITORY_ROOT / "tools" / "release_guard.py"
MANIFEST_URL = "https://example.invalid/update-beta.json"


def _load_guard():
    # The workflows run the file directly: tools/ is no package.
    spec = importlib.util.spec_from_file_location("release_guard_under_test", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _serving(*answers):
    """An opener answering each call with the next manifest or exception."""
    calls = []
    pending = list(answers)

    def opener(request, timeout):
        calls.append((request.full_url, timeout))
        answer = pending.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return _Response(json.dumps(answer).encode("utf-8"))

    opener.calls = calls
    return opener


def _http_error(code):
    return urllib.error.HTTPError(MANIFEST_URL, code, "error", {}, None)


def _no_sleep(_seconds):
    return None


@pytest.mark.parametrize(
    ("older", "newer"),
    [
        ("1.2.2-beta.37", "1.2.2-beta.38"),
        ("1.2.2-beta.99", "1.2.2-rc.1"),
        ("1.2.2-rc.4", "1.2.2"),
        ("1.2.2", "1.2.3-beta.1"),
        ("1.2.9", "1.2.10-beta.1"),
        ("1.9.9", "1.10.0"),
        ("v1.2.1", "1.2.2"),
    ],
)
def test_versions_are_ordered_like_the_updaters(older, newer):
    assert guard.parse_version(older) < guard.parse_version(newer)


def test_the_updaters_use_the_same_ordering():
    """A release accepted here must be offered by the installed apps."""
    # Both updaters take their version rules from supermenu_core; the guard
    # cannot import it, since it runs before any dependency is installed.
    from supermenu_core.utils import updates

    for platform in ("win32", "macos"):
        source = (REPOSITORY_ROOT / platform / "src" / "utils" / "updater.py").read_text(
            encoding="utf-8"
        )
        assert "from supermenu_core.utils.updates import (" in source
        assert "parse_version" in source and "is_newer_version" in source

    samples = (
        "1.2.1", "v1.2.2", " 1.3.0 ", "1.3.0-beta.38", "1.3.0-RC.2", "1.10.0",
        "1.2", "1.2.3-alpha.1", "1.2.3-beta", "latest", "",
    )
    for value in samples:
        assert guard.parse_version(value) == updates.parse_version(value), value
    assert guard._VERSION.pattern == r"v?(\d+)\.(\d+)\.(\d+)(?:-(beta|rc)\.(\d+))?"


def test_require_newer_accepts_a_newer_version():
    opener = _serving({"version": "1.2.2-beta.37"})

    message = guard.require_newer("1.2.2-beta.38", MANIFEST_URL, opener=opener)

    assert "1.2.2-beta.37" in message
    assert opener.calls == [(MANIFEST_URL, 20)]


@pytest.mark.parametrize("published", ["1.2.2-beta.38", "1.2.2-beta.40", "1.2.2"])
def test_require_newer_refuses_an_equal_or_older_version(published):
    opener = _serving({"version": published})

    with pytest.raises(guard.ReleaseGuardError, match="pas plus récente"):
        guard.require_newer("1.2.2-beta.38", MANIFEST_URL, opener=opener)


def test_nothing_published_yet_is_accepted():
    opener = _serving(_http_error(404))

    assert "Aucun manifeste" in guard.require_newer("1.0.0", MANIFEST_URL, opener=opener)
    assert guard.make_latest("1.0.0", MANIFEST_URL, opener=_serving(_http_error(404)))


def test_transient_failures_are_retried_then_fail_closed():
    sleeps = []
    opener = _serving(_http_error(502), urllib.error.URLError("reset"), {"version": "1.2.1"})

    assert guard.require_newer("1.2.2", MANIFEST_URL, opener=opener, sleep=sleeps.append)
    assert sleeps == [5, 10]

    failing = _serving(_http_error(500), OSError("timeout"), _http_error(503))
    with pytest.raises(guard.ReleaseGuardError, match="illisible"):
        guard.require_newer("1.2.2", MANIFEST_URL, opener=failing, sleep=_no_sleep)
    assert len(failing.calls) == guard.ATTEMPTS


@pytest.mark.parametrize("manifest", [{}, {"version": "latest"}, ["1.2.2"], {"version": 3}])
def test_a_published_manifest_without_a_valid_version_fails(manifest):
    with pytest.raises(guard.ReleaseGuardError, match="invalide"):
        guard.require_newer("1.2.2", MANIFEST_URL, opener=_serving(manifest))


def test_an_unreadable_candidate_fails_before_any_request():
    opener = _serving()

    with pytest.raises(guard.ReleaseGuardError, match="illisible"):
        guard.require_newer("1.2", MANIFEST_URL, opener=opener)
    assert opener.calls == []


@pytest.mark.parametrize(
    ("published", "expected"),
    [("1.2.1", True), ("1.2.2", False), ("1.3.0", False)],
)
def test_make_latest_only_for_a_newer_line(published, expected):
    opener = _serving({"version": published})

    assert guard.make_latest("1.2.2", MANIFEST_URL, opener=opener) is expected


@pytest.mark.parametrize(
    ("notes", "expected"),
    [
        ("## Nouveautés de SuperMenu 1.2.1\n", True),
        ("# SuperMenu v1.2.1\n", True),
        ("### 1.2.1 - correctif\n", True),
        ("## Nouveautés de SuperMenu 1.2.10\n", False),
        ("## Nouveautés de SuperMenu 11.2.1\n", False),
        ("## Nouveautés de SuperMenu 1.2.1.4\n", False),
        ("## Nouveautés de SuperMenu 1.2.2\n\nReleases jusqu’à v1.2.1.\n", False),
        ("#1.2.1 sans espace\n", False),
    ],
)
def test_notes_need_a_heading_naming_the_exact_version(notes, expected):
    assert guard.notes_mention_version(notes, "1.2.1") is expected


def test_command_line(tmp_path, monkeypatch, capsys):
    notes = tmp_path / "STABLE_NOTES.md"
    notes.write_text("## Nouveautés de SuperMenu 1.2.2\n", encoding="utf-8")

    assert guard.main(["release_guard.py", "notes-heading", "1.2.2", str(notes)]) == 0
    assert guard.main(["release_guard.py", "notes-heading", "1.2.1", str(notes)]) == 1
    assert "::error::" in capsys.readouterr().err

    monkeypatch.setattr(
        guard.urllib.request, "urlopen", _serving({"version": "1.2.1"}, {"version": "1.2.3"})
    )
    assert guard.main(["release_guard.py", "make-latest", "1.2.2", MANIFEST_URL]) == 0
    assert capsys.readouterr().out.strip() == "true"
    assert guard.main(["release_guard.py", "require-newer", "1.2.2", MANIFEST_URL]) == 1

    assert guard.main(["release_guard.py", "unknown", "1.2.2", "x"]) == 2
    assert guard.main(["release_guard.py"]) == 2
