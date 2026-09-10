import pytest
from PySide6.QtWidgets import QApplication

from src.audio import speech_backend
from src.config.settings import Settings
from supermenu_core.audio.backends import OpenAISpeechBackend, ProcessSpeechBackend


def test_voice_provider_round_trip_is_independent_of_text(tmp_path):
    path = str(tmp_path / "settings.ini")
    settings = Settings(path)
    settings.set_ai_provider("custom")
    settings.set_speech_provider("apple")
    settings.set_transcription_languages("fr-ca")
    settings.sync()
    reloaded = Settings(path)
    assert reloaded.get_ai_provider() == "custom"
    assert reloaded.get_speech_provider() == "apple"
    assert reloaded.get_transcription_languages() == "fr-ca"


def test_apple_speech_backend_checks_os_without_cloud_fallback(monkeypatch, tmp_path):
    settings = Settings(str(tmp_path / "settings.ini"))
    monkeypatch.setattr(speech_backend.sys, "platform", "darwin")
    monkeypatch.setattr(speech_backend.platform, "mac_ver", lambda: ("15.0", (), ""))
    with pytest.raises(ValueError, match="macOS 26"):
        speech_backend.create_speech_backend(settings, {"provider": "apple"})


def test_apple_backend_launches_bundled_helper_without_key(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    settings = Settings(str(tmp_path / "settings.ini"))
    helper = tmp_path / "SuperMenuSpeech"
    helper.write_text("")
    monkeypatch.setattr(speech_backend.sys, "platform", "darwin")
    monkeypatch.setattr(speech_backend.platform, "mac_ver", lambda: ("26.0", (), ""))
    monkeypatch.setattr(speech_backend, "resource_path", lambda *_: str(helper))
    backend = speech_backend.create_speech_backend(
        settings, {"provider": "apple", "language": "fr"}
    )
    assert isinstance(backend, ProcessSpeechBackend)
    assert backend.command == (str(helper), [])
    assert "api_key" not in backend.options
    backend.cancel()
    assert app is not None


def test_openai_voice_remains_available_on_older_macos(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    settings = Settings(str(tmp_path / "settings.ini"))
    monkeypatch.setattr(speech_backend.platform, "mac_ver", lambda: ("15.0", (), ""))
    backend = speech_backend.create_speech_backend(settings, {"provider": "openai"})
    assert isinstance(backend, OpenAISpeechBackend)
    backend.cancel()
    assert app is not None
