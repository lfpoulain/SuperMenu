import hashlib
import json
import os
import tempfile

import pytest
import requests

from src.utils import updater


INSTALLER = b"MZ fake installer payload" * 1000
INSTALLER_SHA256 = hashlib.sha256(INSTALLER).hexdigest()


def _manifest(**overrides):
    payload = {
        "schema_version": 1,
        "channel": "beta",
        "version": "1.2.2-beta.70",
        "prerelease": True,
        "tag": "beta",
    }
    payload.update(overrides)
    return payload


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.content = payload
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        for start in range(0, len(self.payload), chunk_size):
            yield self.payload[start:start + chunk_size]


class _FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.routes = {}
        self.urls = []

    def get(self, url, **_kwargs):
        self.urls.append(url)
        if url in self.routes:
            return _FakeResponse(*self.routes[url])
        return _FakeResponse(self.payload)


class _RecordingLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message, *args):
        self.warnings.append(message % args)


@pytest.fixture
def temp_dir(monkeypatch, tmp_path):
    """Stand-in for %TEMP%: the real one may hold the user's own downloads."""
    folder = tmp_path / "temp"
    folder.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(folder))
    return folder


@pytest.fixture
def fake_download(monkeypatch, temp_dir):
    session = _FakeSession(INSTALLER)
    monkeypatch.setattr(updater, "_SESSION", session)
    logger = _RecordingLogger()
    monkeypatch.setattr(updater, "_LOGGER", logger)
    return session, logger


def test_manifest_fingerprint_is_exposed_like_the_github_api_digest():
    release = updater._release_from_manifest(
        _manifest(asset="SuperMenu_Beta_Setup.exe", sha256=INSTALLER_SHA256.upper()),
        "lfpoulain",
        "SuperMenu",
        "beta",
    )

    assert updater.find_asset_sha256(
        release, "SuperMenu_Beta_Setup.exe"
    ) == INSTALLER_SHA256
    assert release["assets"][0]["digest"] == f"sha256:{INSTALLER_SHA256}"


def test_manifest_without_fingerprint_stays_compatible():
    release = updater._release_from_manifest(
        _manifest(), "lfpoulain", "SuperMenu", "beta"
    )

    assert updater.find_asset_sha256(release, "SuperMenu_Beta_Setup.exe") is None
    assert "digest" not in release["assets"][0]


def test_api_release_digest_is_used_when_the_manifest_is_unreachable():
    release = {
        "assets": [
            {
                "name": "SuperMenu_Beta_Setup.exe",
                "browser_download_url": "https://example.invalid/setup.exe",
                "digest": f"sha256:{INSTALLER_SHA256}",
            },
            {"name": "SuperMenu_Beta.exe", "digest": None},
        ]
    }

    assert updater.find_asset_sha256(
        release, "SuperMenu_Beta_Setup.exe"
    ) == INSTALLER_SHA256
    assert updater.find_asset_sha256(release, "SuperMenu_Beta.exe") is None
    assert updater.find_asset_sha256(release, "missing.exe") is None


@pytest.mark.parametrize(
    ("overrides", "channel"),
    [
        ({"schema_version": 2}, "beta"),
        ({"channel": "stable"}, "beta"),
        ({"version": "1.2"}, "beta"),
        ({"version": "latest"}, "beta"),
        ({"prerelease": False}, "beta"),
        ({"prerelease": "true"}, "beta"),
        ({"tag": "v1.2.2"}, "beta"),
        ({"asset": "SuperMenu_Setup.exe"}, "beta"),
        ({"asset": "../evil.exe"}, "beta"),
        ({"sha256": "abc"}, "beta"),
        ({"sha256": "g" * 64}, "beta"),
        ({"sha256": 12}, "beta"),
        (
            {"channel": "stable", "prerelease": False, "tag": "v9.9.9",
             "version": "1.2.2"},
            "stable",
        ),
        (
            {"channel": "stable", "prerelease": False, "tag": "beta",
             "version": "1.2.2"},
            "stable",
        ),
    ],
)
def test_inconsistent_manifests_are_rejected(overrides, channel):
    with pytest.raises(ValueError):
        updater._release_from_manifest(
            _manifest(**overrides), "lfpoulain", "SuperMenu", channel
        )


def test_manifest_payload_must_be_an_object():
    with pytest.raises(ValueError):
        updater._release_from_manifest([], "lfpoulain", "SuperMenu", "beta")


def test_verified_download_uses_a_private_unpredictable_folder(fake_download):
    session, logger = fake_download

    path = updater.download_verified_installer(
        "https://example.invalid/setup.exe",
        "SuperMenu_Beta_Setup_1.2.2-beta.70.exe",
        INSTALLER_SHA256,
    )
    try:
        folder = os.path.dirname(path)
        assert os.path.basename(path) == "SuperMenu_Beta_Setup_1.2.2-beta.70.exe"
        assert os.path.dirname(folder) == tempfile.gettempdir()
        assert os.path.basename(folder).startswith("SuperMenu_update_")
        with open(path, "rb") as installer:
            assert installer.read() == INSTALLER
        assert session.urls == ["https://example.invalid/setup.exe"]
        assert logger.warnings == []
        updater.verify_installer_sha256(path, INSTALLER_SHA256)
    finally:
        os.remove(path)
        os.rmdir(os.path.dirname(path))


def _download_folders(temp_dir):
    return sorted(
        entry.name
        for entry in temp_dir.iterdir()
        if entry.name.startswith("SuperMenu_update_")
    )


def test_a_new_download_replaces_the_previous_folder(fake_download, temp_dir):
    # Declined at "Lancer l'installation maintenant ?": the first installer
    # (about 100 MB) must not stay in %TEMP% once a new one is downloaded.
    first = updater.download_verified_installer(
        "https://example.invalid/setup.exe", "setup.exe", INSTALLER_SHA256
    )
    second = updater.download_verified_installer(
        "https://example.invalid/setup.exe", "setup.exe", INSTALLER_SHA256
    )

    assert first != second
    assert not os.path.exists(os.path.dirname(first))
    assert os.path.isfile(second)
    assert _download_folders(temp_dir) == [
        os.path.basename(os.path.dirname(second))
    ]


def test_cleanup_only_touches_previous_download_folders(fake_download, temp_dir):
    (temp_dir / "Other_folder").mkdir()
    (temp_dir / "Other_folder" / "keep.txt").write_text("x", encoding="utf-8")
    (temp_dir / "SuperMenu_update_notes.txt").write_text("x", encoding="utf-8")
    stale = temp_dir / "SuperMenu_update_old"
    stale.mkdir()
    (stale / "SuperMenu_Setup_1.0.0.exe").write_bytes(b"old")

    path = updater.download_verified_installer(
        "https://example.invalid/setup.exe", "setup.exe", INSTALLER_SHA256
    )

    assert not stale.exists()
    assert (temp_dir / "Other_folder" / "keep.txt").is_file()
    assert (temp_dir / "SuperMenu_update_notes.txt").is_file()
    assert os.path.isfile(path)


def test_cleanup_failure_never_blocks_the_download(fake_download, monkeypatch):
    def unreadable(_path):
        raise PermissionError("denied")

    monkeypatch.setattr(updater.os, "scandir", unreadable)

    path = updater.download_verified_installer(
        "https://example.invalid/setup.exe", "setup.exe", INSTALLER_SHA256
    )

    assert os.path.isfile(path)


def test_fingerprint_mismatch_is_refused_and_nothing_is_left(
    fake_download, monkeypatch
):
    created = []
    real_mkdtemp = tempfile.mkdtemp

    def recording_mkdtemp(*args, **kwargs):
        created.append(real_mkdtemp(*args, **kwargs))
        return created[-1]

    monkeypatch.setattr(updater.tempfile, "mkdtemp", recording_mkdtemp)

    with pytest.raises(updater.UpdateIntegrityError) as caught:
        updater.download_verified_installer(
            "https://example.invalid/setup.exe",
            "SuperMenu_Setup.exe",
            "0" * 64,
        )

    assert "empreinte" in str(caught.value)
    assert isinstance(caught.value, updater.UpdateCheckError)
    assert len(created) == 1
    assert not os.path.exists(created[0])


def test_invalid_expected_fingerprint_is_refused_before_download(fake_download):
    session, _logger = fake_download

    with pytest.raises(updater.UpdateIntegrityError):
        updater.download_verified_installer(
            "https://example.invalid/setup.exe", "setup.exe", "not-a-hash"
        )

    assert session.urls == []


def test_older_manifest_without_fingerprint_downloads_with_a_warning(
    fake_download,
):
    _session, logger = fake_download

    path = updater.download_verified_installer(
        "https://example.invalid/setup.exe", "setup.exe", None
    )
    try:
        assert os.path.isfile(path)
        assert len(logger.warnings) == 1
        assert "SHA-256" in logger.warnings[0]
        # Nothing to compare against: the launch-time check is a no-op.
        updater.verify_installer_sha256(path, None)
    finally:
        os.remove(path)
        os.rmdir(os.path.dirname(path))


def test_file_name_cannot_escape_the_private_folder(fake_download):
    path = updater.download_verified_installer(
        "https://example.invalid/setup.exe",
        "..\\..\\Windows\\evil.exe",
        INSTALLER_SHA256,
    )
    try:
        assert os.path.basename(path) == "evil.exe"
        assert os.path.basename(os.path.dirname(path)).startswith(
            "SuperMenu_update_"
        )
    finally:
        os.remove(path)
        os.rmdir(os.path.dirname(path))


def test_installer_replaced_after_download_is_not_launched(fake_download):
    path = updater.download_verified_installer(
        "https://example.invalid/setup.exe", "setup.exe", INSTALLER_SHA256
    )
    with open(path, "wb") as installer:
        installer.write(b"swapped")

    with pytest.raises(updater.UpdateIntegrityError):
        updater.verify_installer_sha256(path, INSTALLER_SHA256)

    # The refused file does not stay in its private folder.
    assert not os.path.exists(os.path.dirname(path))


def test_refused_installer_outside_private_folders_is_kept(temp_dir, tmp_path):
    installer = tmp_path / "SuperMenu_Setup.exe"
    installer.write_bytes(b"swapped")

    with pytest.raises(updater.UpdateIntegrityError):
        updater.verify_installer_sha256(str(installer), INSTALLER_SHA256)

    assert installer.read_bytes() == b"swapped"


BETA_INSTALLER_URL = (
    "https://github.com/lfpoulain/supermenu/releases/download/beta/"
    "SuperMenu_Beta_Setup.exe"
)
BETA_MANIFEST_URL = (
    "https://github.com/lfpoulain/supermenu/releases/download/beta/"
    "update-beta.json"
)
PREVIOUS_BETA_SHA256 = hashlib.sha256(b"previous beta").hexdigest()


def _beta_manifest_response(sha256):
    payload = _manifest(asset="SuperMenu_Beta_Setup.exe", sha256=sha256)
    return (json.dumps(payload).encode("utf-8"), 200)


def _download_previous_beta():
    return updater.download_verified_installer(
        BETA_INSTALLER_URL,
        "SuperMenu_Beta_Setup_1.2.2-beta.70.exe",
        PREVIOUS_BETA_SHA256,
    )


def test_beta_published_during_the_update_gets_a_dedicated_message(
    fake_download, temp_dir
):
    session, _logger = fake_download
    # The question stayed open while a push to main replaced the beta.
    session.routes[BETA_MANIFEST_URL] = _beta_manifest_response(INSTALLER_SHA256)

    with pytest.raises(updater.UpdateSupersededError) as caught:
        _download_previous_beta()

    assert "nouvelle bêta" in str(caught.value)
    assert "Vérifier les mises à jour" in str(caught.value)
    # Still an integrity refusal for every existing handler.
    assert isinstance(caught.value, updater.UpdateIntegrityError)
    assert session.urls == [BETA_INSTALLER_URL, BETA_MANIFEST_URL]
    assert _download_folders(temp_dir) == []


@pytest.mark.parametrize(
    "manifest_response",
    [
        _beta_manifest_response(PREVIOUS_BETA_SHA256),
        (b"", 404),
        (b"{not json", 200),
        (json.dumps(_manifest()).encode("utf-8"), 200),
    ],
    ids=["unchanged", "missing", "unreadable", "without-sha256"],
)
def test_beta_mismatch_with_the_same_manifest_stays_a_strict_refusal(
    fake_download, temp_dir, manifest_response
):
    session, _logger = fake_download
    session.routes[BETA_MANIFEST_URL] = manifest_response

    with pytest.raises(updater.UpdateIntegrityError) as caught:
        _download_previous_beta()

    assert not isinstance(caught.value, updater.UpdateSupersededError)
    assert "empreinte" in str(caught.value)
    assert _download_folders(temp_dir) == []


def test_stable_mismatch_never_reads_a_manifest_again(fake_download):
    session, _logger = fake_download
    url = (
        "https://github.com/lfpoulain/supermenu/releases/download/v1.2.2/"
        "SuperMenu_Setup.exe"
    )

    with pytest.raises(updater.UpdateIntegrityError) as caught:
        updater.download_verified_installer(url, "setup.exe", PREVIOUS_BETA_SHA256)

    assert not isinstance(caught.value, updater.UpdateSupersededError)
    assert session.urls == [url]


def test_legacy_download_to_file_still_writes_the_payload(
    fake_download, tmp_path
):
    destination = tmp_path / "setup.exe"

    assert updater.download_to_file(
        "https://example.invalid/setup.exe", str(destination)
    ) is None
    assert destination.read_bytes() == INSTALLER
