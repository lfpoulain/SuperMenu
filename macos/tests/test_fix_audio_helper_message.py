"""A missing Apple Speech helper names the right remedy for each build."""

import pytest

from src.audio import speech_backend
from src.config.settings import Settings


@pytest.mark.parametrize(
    "frozen, expected",
    [
        (True, "Réinstallez SuperMenu."),
        (False, "bash scripts/build_speech_helper.sh"),
    ],
)
def test_missing_helper_message_matches_build(monkeypatch, tmp_path, frozen, expected):
    settings = Settings(str(tmp_path / "settings.ini"))
    monkeypatch.setattr(speech_backend.sys, "platform", "darwin")
    monkeypatch.setattr(speech_backend.sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(speech_backend.platform, "mac_ver", lambda: ("26.0", (), ""))
    monkeypatch.setattr(
        speech_backend, "resource_path", lambda *_: str(tmp_path / "absent")
    )
    with pytest.raises(ValueError) as error:
        speech_backend.create_speech_backend(
            settings, {"provider": "apple", "language": "fr"}
        )
    assert expected in str(error.value)
    assert "bêta" not in str(error.value)
