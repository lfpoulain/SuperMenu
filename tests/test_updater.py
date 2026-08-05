from src.utils import updater


def test_extract_version_from_release_body_metadata():
    release = {"name": "Nightly", "body": "Channel: nightly\nVersion: 1.0.42\nCommit: abc"}

    assert updater.extract_version_from_release(release) == "1.0.42"


def test_extract_version_from_release_name_fallback():
    release = {"name": "Nightly 1.0.43", "body": ""}

    assert updater.extract_version_from_release(release) == "1.0.43"


def test_extract_beta_version_from_release_metadata():
    release = {
        "name": "SuperMenu Beta",
        "body": "Channel: beta\nVersion: 1.2.0-beta.47",
        "tag_name": "beta",
    }

    assert updater.extract_version_from_release(release) == "1.2.0-beta.47"


def test_extract_stable_version_from_tag_fallback():
    release = {"name": "SuperMenu", "body": "", "tag_name": "v1.2.3"}

    assert updater.extract_version_from_release(release) == "1.2.3"


def test_is_newer_version_handles_missing_installed_version():
    assert updater.is_newer_version(None, "1.0.44") is True
    assert updater.is_newer_version("1.0.44", "1.0.44") is False
    assert updater.is_newer_version("1.0.44", "1.0.45") is True


def test_version_order_handles_beta_and_stable_channels():
    assert updater.is_newer_version(
        "1.2.0-beta.41",
        "1.2.0-beta.42",
    ) is True
    assert updater.is_newer_version("1.2.0-beta.42", "1.2.0") is True
    assert updater.is_newer_version("1.2.0", "1.2.0-beta.99") is False
    assert updater.is_newer_version("1.2.0", "invalid") is False


def test_update_channels_use_distinct_installer_assets():
    assert updater.normalize_update_channel("unknown") == "stable"
    assert updater.installer_asset_name("stable") == "SuperMenu_Setup.exe"
    assert updater.installer_asset_name("beta") == "SuperMenu_Beta_Setup.exe"


def test_stable_channel_uses_latest_release_endpoint(monkeypatch):
    calls = []
    monkeypatch.setattr(
        updater,
        "get_latest_stable_release",
        lambda owner, repo, timeout_s=15: calls.append(
            (owner, repo, timeout_s)
        )
        or {"prerelease": False},
    )

    release = updater.get_release_for_update_channel(
        "lfpoulain",
        "SuperMenu",
        "stable",
    )

    assert release == {"prerelease": False}
    assert calls == [("lfpoulain", "SuperMenu", 15)]


def test_beta_channel_rejects_release_not_marked_as_prerelease(monkeypatch):
    monkeypatch.setattr(
        updater,
        "get_github_release_by_tag",
        lambda *_args, **_kwargs: {"prerelease": False},
    )

    try:
        updater.get_release_for_update_channel(
            "lfpoulain",
            "SuperMenu",
            "beta",
        )
    except ValueError as exc:
        assert "préversion" in str(exc)
    else:
        raise AssertionError("Une beta non marquée prerelease doit être refusée")
