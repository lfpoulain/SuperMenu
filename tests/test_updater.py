from src.utils import updater


def test_extract_version_from_release_body_metadata():
    release = {"name": "Nightly", "body": "Channel: nightly\nVersion: 1.0.42\nCommit: abc"}

    assert updater.extract_version_from_release(release) == "1.0.42"


def test_extract_version_from_release_name_fallback():
    release = {"name": "Nightly 1.0.43", "body": ""}

    assert updater.extract_version_from_release(release) == "1.0.43"


def test_is_newer_version_handles_missing_installed_version():
    assert updater.is_newer_version(None, "1.0.44") is True
    assert updater.is_newer_version("1.0.44", "1.0.44") is False
    assert updater.is_newer_version("1.0.44", "1.0.45") is True
