import os
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QSettings

from src.config import settings as settings_module
from src.config.settings import Settings


def test_retiring_portaudio_index_preserves_current_voice_preferences(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings_module.os.path, "expanduser", lambda _: str(tmp_path))
    saved = QSettings(str(tmp_path / "SuperMenu.ini"), QSettings.Format.IniFormat)
    saved.setValue("microphone_index", 7)
    preferences = {
        "speech_microphone": "qt-usb-device-id",
        "speech_provider": "foundry",
        "speech_device": "cpu",
        "speech_idle_seconds": 900,
        "transcription_languages": "fr",
        "transcription_prompt": "Réunion produit",
        "transcription_keywords": "SuperMenu, Nemotron",
    }
    for key, value in preferences.items():
        saved.setValue(key, value)
    saved.sync()

    for _ in range(2):
        settings = Settings()
        assert not settings.settings.contains("microphone_index")
        for key, expected in preferences.items():
            assert getattr(settings, "get_" + key)() == expected
        settings.sync()


def test_windows_capture_and_clipboard_import_without_portaudio():
    # A fresh interpreter catches transitive imports even if PyAudio happens to
    # be installed in the developer environment or loaded by another test.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
sys.modules['pyaudio'] = None
sys.modules['_portaudio'] = None
from src.utils.context_menu import ContextMenuManager
from src.utils.text_inserter import TextInserter
from supermenu_core.audio.microphone import Microphone
from supermenu_core.audio.session import DictationSession
assert sys.modules['pyaudio'] is None
assert sys.modules['_portaudio'] is None
""",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
