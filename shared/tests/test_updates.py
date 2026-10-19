import json

import pytest

from supermenu_core.config import provider_settings
from supermenu_core.utils import updates


SHA256 = "ab" * 32


def test_versions_order_prereleases_before_the_stable_release():
    assert updates.parse_version("v1.2.3") == (1, 2, 3, 2, 0)
    assert updates.parse_version(" 1.2.3-RC.4 ") == (1, 2, 3, 1, 4)
    assert updates.parse_version("1.2.3-beta.9") < updates.parse_version("1.2.3-rc.1")
    assert updates.parse_version("1.2.3-rc.1") < updates.parse_version("1.2.3")
    for invalid in (None, "", "1.2", "1.2.3-alpha.1", "1.2.3-beta"):
        assert updates.parse_version(invalid) == ()


def test_newer_version_tolerates_missing_or_invalid_values():
    assert updates.is_newer_version(None, "1.0.0") is True
    assert updates.is_newer_version("invalid", "1.0.0") is True
    assert updates.is_newer_version("1.0.0", None) is False
    assert updates.is_newer_version("1.0.0", "invalid") is False
    assert updates.is_newer_version("1.2.0-beta.42", "1.2.0") is True
    assert updates.is_newer_version("1.2.0", "1.2.0-beta.99") is False


def test_update_channels_have_a_single_definition():
    assert updates.normalize_update_channel is provider_settings.normalize_update_channel
    assert updates.UPDATE_CHANNELS == (
        updates.UPDATE_CHANNEL_STABLE,
        updates.UPDATE_CHANNEL_BETA,
    )


def test_windows_release_notes_line_gives_the_last_windows_version():
    body = (
        "Windows : `1.2.2-beta.61` · macOS Apple Silicon : `1.2.9-beta.61`\n"
        "Windows version: v1.2.2-RC.3\n"
    )

    assert updates.WINDOWS_VERSION_LINE.findall(body) == [
        "1.2.2-beta.61",
        "1.2.2-RC.3",
    ]
    assert not updates.WINDOWS_VERSION_LINE.search("macOS version: 1.2.9")


def test_manifests_live_beside_the_beta_tag_or_the_latest_stable_release():
    releases = "https://github.com/lfpoulain/SuperMenu/releases"

    assert updates.release_manifest_url(releases, "beta", "update-beta.json") == (
        "https://github.com/lfpoulain/SuperMenu/releases/download/beta/"
        "update-beta.json"
    )
    assert updates.release_manifest_url(
        releases, "stable", "update-macos-stable.json"
    ) == (
        "https://github.com/lfpoulain/SuperMenu/releases/latest/download/"
        "update-macos-stable.json"
    )


class _Response:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_manifest_request_bypasses_caches_and_treats_404_as_absent():
    calls = []
    response = _Response()

    def http_get(*args, **kwargs):
        calls.append((args, kwargs))
        return response

    assert updates.request_release_manifest(http_get, "https://example.invalid/m", 7) is response
    assert calls == [
        (
            ("https://example.invalid/m",),
            {
                "timeout": (5, 7),
                "headers": {
                    "Accept": "application/json",
                    "Cache-Control": "no-cache",
                },
            },
        )
    ]

    assert updates.request_release_manifest(
        lambda *_a, **_kw: _Response(404), "u", 15
    ) is None
    with pytest.raises(RuntimeError, match="HTTP 500"):
        updates.request_release_manifest(lambda *_a, **_kw: _Response(500), "u", 15)


def test_manifest_body_accepts_a_bom_and_reports_unreadable_content():
    payload = {"schema_version": 1, "channel": "beta"}
    body = b"\xef\xbb\xbf" + json.dumps(payload).encode("utf-8")

    assert updates.decode_release_manifest(_Response(content=body), "illisible") == payload
    assert updates.decode_release_manifest(_Response(content=b"null"), "illisible") is None

    for content in (b"{", b"\xff\xfe", None):
        with pytest.raises(ValueError, match="^illisible$") as caught:
            updates.decode_release_manifest(_Response(content=content), "illisible")
        assert caught.value.__cause__ is not None


def test_manifest_fingerprint_is_optional_but_must_be_valid_when_declared():
    assert updates.declared_sha256({}, "invalide") is None
    assert updates.declared_sha256({"sha256": None}, "invalide") is None
    assert updates.declared_sha256({"sha256": f" {SHA256.upper()}\n"}, "invalide") == SHA256

    for invalid in ("", "abc", "g" * 64, f"sha256:{SHA256}", SHA256 + "0", 12, False):
        with pytest.raises(ValueError, match="^invalide$"):
            updates.declared_sha256({"sha256": invalid}, "invalide")
