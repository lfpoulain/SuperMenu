import json

from src.utils import updater
from src.utils.updater import is_newer_version, normalize_update_channel, parse_version


def test_version_ordering_handles_prereleases():
    assert parse_version("v1.2.3") > parse_version("1.2.3-rc.1")
    assert parse_version("1.2.3-rc.1") > parse_version("1.2.3-beta.9")
    assert is_newer_version("1.2.2", "1.2.3")
    assert not is_newer_version("1.2.3", "1.2.3-beta.1")


def test_update_channel_is_restricted():
    assert normalize_update_channel("beta") == "beta"
    assert normalize_update_channel("anything") == "stable"


def test_each_channel_has_a_deterministic_apple_silicon_dmg():
    assert updater.dmg_asset_name("stable") == "SuperMenu-macOS-arm64.dmg"
    assert updater.dmg_asset_name("beta") == "SuperMenu_Beta-macOS-arm64.dmg"
    assert updater.release_manifest_name("stable") == "update-macos-stable.json"
    assert updater.release_manifest_name("beta") == "update-macos-beta.json"


def test_asset_selection_never_returns_a_windows_binary():
    release = {
        "assets": [
            {
                "name": "SuperMenu_Beta_Setup.exe",
                "browser_download_url": "https://example.invalid/windows.exe",
            },
            {
                "name": "SuperMenu_Beta-macOS-arm64.dmg",
                "browser_download_url": "https://example.invalid/macos.dmg",
            },
        ]
    }

    assert updater.find_dmg_download_url(release, "beta") == (
        "https://example.invalid/macos.dmg"
    )


class _ManifestResponse:
    status_code = 200

    def __init__(self, payload):
        self.content = json.dumps(payload).encode("utf-8")

    def raise_for_status(self):
        return None


def test_update_check_uses_the_macos_manifest_and_direct_dmg(monkeypatch):
    payload = {
        "schema_version": 1,
        "platform": "macos",
        "architecture": "arm64",
        "channel": "stable",
        "version": "1.2.8",
        "prerelease": False,
        "tag": "v1.2.1",
        "asset": "SuperMenu-macOS-arm64.dmg",
    }
    monkeypatch.setattr(
        updater.requests,
        "get",
        lambda *args, **kwargs: _ManifestResponse(payload),
    )

    release = updater.check_latest_release("stable")

    assert release["version"] == "1.2.8"
    assert release["url"].endswith("/v1.2.1/SuperMenu-macOS-arm64.dmg")


def test_api_fallback_reads_the_explicit_macos_version():
    release = {
        "tag_name": "v1.2.1",
        "name": "SuperMenu 1.2.1",
        "body": "Windows version: 1.2.1\nmacOS version: 1.2.8",
    }

    assert updater.extract_version(release) == "1.2.8"
