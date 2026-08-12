from src.utils.updater import is_newer_version, normalize_update_channel, parse_version


def test_version_ordering_handles_prereleases():
    assert parse_version("v1.2.3") > parse_version("1.2.3-rc.1")
    assert parse_version("1.2.3-rc.1") > parse_version("1.2.3-beta.9")
    assert is_newer_version("1.2.2", "1.2.3")
    assert not is_newer_version("1.2.3", "1.2.3-beta.1")


def test_update_channel_is_restricted():
    assert normalize_update_channel("beta") == "beta"
    assert normalize_update_channel("anything") == "stable"

