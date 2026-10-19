import json
import re
from pathlib import Path

import pytest

from src.utils import updater


MACOS_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = MACOS_ROOT.parent
DMG_SHA256 = "ab" * 32


def _manifest(**overrides):
    payload = {
        "schema_version": 1,
        "platform": "macos",
        "architecture": "arm64",
        "channel": "beta",
        "version": "1.2.9-beta.71",
        "prerelease": True,
        "tag": "beta",
        "asset": "SuperMenu_Beta-macOS-arm64.dmg",
    }
    payload.update(overrides)
    return payload


def _render_notes(script, notes_text, env):
    """Rebuild the release body exactly as the cat/printf lines produce it."""
    output = []
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("cat "):
            output.append(notes_text)
        elif stripped.startswith("printf "):
            match = re.fullmatch(
                r"printf (?:-- )?'([^']*)'((?:\s+\"\$\{\w+\}\")*)",
                stripped,
            )
            assert match, f"printf line not understood: {stripped}"
            fmt = match.group(1).replace("\\n", "\n")
            names = re.findall(r"\$\{(\w+)\}", match.group(2))
            output.append(fmt % tuple(env[name] for name in names))
    return "".join(output)


def _step_script(workflow, step_name):
    match = re.search(
        rf"^      - name: {re.escape(step_name)}\n(.*?)(?=^      - name: |\Z)",
        workflow,
        re.M | re.S,
    )
    assert match, f"{step_name} step not found"
    return match.group(1).split("run: |\n", 1)[1]


def test_manifest_fingerprint_is_returned_when_published():
    release = updater._release_from_manifest(
        _manifest(sha256=DMG_SHA256.upper()), "beta"
    )

    assert release["sha256"] == DMG_SHA256
    assert release["url"].endswith("/beta/SuperMenu_Beta-macOS-arm64.dmg")


def test_manifest_without_fingerprint_stays_compatible():
    assert updater._release_from_manifest(_manifest(), "beta")["sha256"] == ""


@pytest.mark.parametrize(
    ("overrides", "channel"),
    [
        ({"schema_version": 2}, "beta"),
        ({"platform": "windows"}, "beta"),
        ({"architecture": "x86_64"}, "beta"),
        ({"channel": "stable"}, "beta"),
        ({"channel": "BETA"}, "beta"),
        ({"version": "1.2"}, "beta"),
        ({"prerelease": False}, "beta"),
        ({"prerelease": 1}, "beta"),
        ({"tag": "v1.2.9"}, "beta"),
        ({"asset": "SuperMenu_Beta_Setup.exe"}, "beta"),
        ({"sha256": "abc"}, "beta"),
        ({"sha256": "z" * 64}, "beta"),
        (
            {"channel": "stable", "prerelease": False, "tag": "beta",
             "asset": "SuperMenu-macOS-arm64.dmg"},
            "stable",
        ),
        (
            {"channel": "stable", "prerelease": False, "tag": "v1.2.9-beta.1",
             "asset": "SuperMenu-macOS-arm64.dmg"},
            "stable",
        ),
    ],
)
def test_inconsistent_manifests_are_rejected(overrides, channel):
    with pytest.raises(ValueError):
        updater._release_from_manifest(_manifest(**overrides), channel)


def test_beta_notes_built_by_the_workflow_give_the_macos_version():
    beta = (REPOSITORY_ROOT / ".github" / "workflows" / "beta-release.yml").read_text(
        encoding="utf-8"
    )
    notes = (REPOSITORY_ROOT / ".github" / "BETA_NOTES.md").read_text(encoding="utf-8")
    body = _render_notes(
        _step_script(beta, "Prepare concise beta notes"),
        notes,
        {
            "WINDOWS_VERSION": "1.2.2-beta.71",
            "MACOS_VERSION": "1.2.9-beta.71",
            "BUILD_COMMIT": "0123abc",
        },
    )

    assert updater.extract_version(
        {"name": "SuperMenu Beta", "tag_name": "beta", "body": body}
    ) == "1.2.9-beta.71"


def test_beta_body_already_published_gives_the_macos_version_not_windows():
    body = (
        "## Nouveautés de cette bêta\n\n"
        "Windows : `1.2.2-beta.61` · macOS Apple Silicon : `1.2.9-beta.61`\n"
        "\n<details>\n<summary>Informations de build</summary>\n\n"
        "Commit : `abc`\n\n</details>\n"
    )

    assert updater.extract_version({"tag_name": "beta", "body": body}) == (
        "1.2.9-beta.61"
    )


def test_windows_version_is_never_reported_as_the_mac_version():
    release = {
        "tag_name": "v1.2.2",
        "name": "SuperMenu 1.2.2",
        "body": "Windows version: 1.2.2\nmacOS Apple Silicon : DMG signé",
    }

    assert updater.extract_version(release) == ""


def test_legacy_single_version_release_still_falls_back_to_the_tag():
    assert updater.extract_version(
        {"tag_name": "v1.1.0", "name": "SuperMenu", "body": ""}
    ) == "1.1.0"


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.content = json.dumps(payload).encode("utf-8")
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_api_fallback_without_a_macos_version_reports_an_error(monkeypatch):
    api_release = {
        "prerelease": True,
        "tag_name": "beta",
        "name": "SuperMenu Beta",
        "body": "Windows : `1.2.2-beta.5`",
        "html_url": "https://github.com/lfpoulain/SuperMenu/releases/tag/beta",
        "assets": [
            {
                "name": "SuperMenu_Beta-macOS-arm64.dmg",
                "browser_download_url": "https://example.invalid/beta.dmg",
            }
        ],
    }

    def fake_get(url, **_kwargs):
        if "api.github.com" in url:
            return _Response(200, api_release)
        return _Response(404, {})

    monkeypatch.setattr(updater.requests, "get", fake_get)

    with pytest.raises(ValueError) as caught:
        updater.check_latest_release("beta")
    assert "version macOS" in str(caught.value)
