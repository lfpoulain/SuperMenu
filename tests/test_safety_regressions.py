import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication, QComboBox, QVBoxLayout, QWidget

from src.audio import audio_recorder as audio_recorder_module
from src.audio.audio_recorder import AudioRecorder
from src.audio.voice_recognition import RecordingDialog
from src.config import settings as settings_module
from src.config.settings import Settings
from src.ui.main_window import MainWindow
from src.utils.clipboard_manager import ClipboardManager
from src.utils.text_inserter import TextInserter


def _app():
    return QApplication.instance() or QApplication([])


def test_recording_dialog_close_cancels_once():
    _app()
    dialog = RecordingDialog()
    calls = []
    dialog.recording_cancelled.connect(lambda: calls.append("cancel"))

    dialog.close()
    dialog.close()

    assert calls == ["cancel"]


def test_recording_dialog_stop_switches_to_processing():
    _app()
    dialog = RecordingDialog()
    calls = []
    dialog.recording_stopped.connect(lambda: calls.append("stop"))

    dialog.stop_button.click()

    assert calls == ["stop"]
    assert dialog._state == "processing"
    assert dialog.stop_button.isHidden() is True


def test_audio_callback_never_exceeds_the_recording_limit(monkeypatch):
    monkeypatch.setattr(audio_recorder_module, "MAX_RECORDING_CHUNKS", 2)
    recorder = AudioRecorder.__new__(AudioRecorder)
    recorder.frames = []
    recorder.stop_event = audio_recorder_module.threading.Event()

    recorder._callback(b"first", 1, None, 0)
    recorder._callback(b"second", 1, None, 0)
    _data, status = recorder._callback(b"third", 1, None, 0)

    assert recorder.frames == [b"first", b"second"]
    assert recorder.stop_event.is_set()
    assert status == audio_recorder_module.pyaudio.paComplete


def test_audio_cancel_discards_the_temporary_recording(tmp_path):
    class FakeStream:
        def __init__(self):
            self.closed = False

        def is_active(self):
            return True

        def stop_stream(self):
            pass

        def close(self):
            self.closed = True

    recording_path = tmp_path / "cancelled.wav"
    recording_path.write_bytes(b"temporary audio")
    recorder = AudioRecorder.__new__(AudioRecorder)
    recorder.stop_event = audio_recorder_module.threading.Event()
    recorder.frames = [b"audio"]
    recorder.stream = FakeStream()
    recorder.is_recording = True
    recorder.temp_files = [str(recording_path)]

    recorder.cancel_recording()

    assert recorder.stream is None
    assert recorder.frames == []
    assert recorder.temp_files == []
    assert not recording_path.exists()


def test_clipboard_snapshot_restores_text_and_rich_formats():
    app = _app()
    mime = QMimeData()
    mime.setText("original")
    mime.setHtml("<b>original</b>")
    app.clipboard().setMimeData(mime)
    snapshot = ClipboardManager.capture_snapshot()

    app.clipboard().setText("temporary")
    assert snapshot.restore() is True

    restored = app.clipboard().mimeData()
    assert restored.text() == "original"
    assert restored.html() == "<b>original</b>"
    # The offscreen Qt clipboard keeps native MIME ownership until process
    # teardown on Windows; release it explicitly to avoid a plugin shutdown
    # crash that does not occur in the real Windows platform plugin.
    app.clipboard().clear()
    app.processEvents()


def test_text_inserter_refuses_to_paste_when_target_is_not_safe(monkeypatch):
    class UnsafeTarget:
        def activate_and_verify(self):
            return False

    inserter = TextInserter()
    paste_calls = []
    monkeypatch.setattr(
        inserter,
        "_press_keyboard_shortcut",
        lambda *_keys: paste_calls.append("paste"),
    )

    assert inserter.insert_text("sensitive", target=UnsafeTarget()) is False
    assert paste_calls == []


def test_bottom_buttons_are_added_and_close_is_connected():
    _app()

    class FakeWindow:
        def __init__(self):
            self.container = QWidget()
            self.main_layout = QVBoxLayout(self.container)
            self.reset_calls = 0
            self.close_calls = 0

        def reset_all_settings(self):
            self.reset_calls += 1

        def close(self):
            self.close_calls += 1

    fake = FakeWindow()
    MainWindow.create_bottom_buttons(fake)

    assert fake.main_layout.count() == 1
    buttons_layout = fake.main_layout.itemAt(0).layout()
    assert buttons_layout.count() == 3
    buttons_layout.itemAt(2).widget().click()
    assert fake.close_calls == 1


def test_import_refresh_uses_existing_prompt_loaders(monkeypatch):
    _app()

    class FakeSettings:
        def import_prompts(self, _path):
            return True, "ok"

    class FakeWindow:
        def __init__(self):
            self.settings = FakeSettings()
            self.prompt_combo = QComboBox()
            self.prompt_combo.addItem("Text", "text")
            self.voice_prompt_combo = QComboBox()
            self.voice_prompt_combo.addItem("Voice", "voice")
            self.loaded = []

        def populate_prompt_combo(self):
            pass

        def populate_voice_prompt_combo(self):
            pass

        def load_prompt(self, index):
            self.loaded.append(("text", index))

        def load_voice_prompt(self, index):
            self.loaded.append(("voice", index))

        def clear_prompt_editor(self):
            self.loaded.append(("clear-text", None))

        def clear_voice_prompt_editor(self):
            self.loaded.append(("clear-voice", None))

    fake = FakeWindow()
    monkeypatch.setattr(
        "src.ui.main_window.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: ("prompts.json", ""),
    )
    monkeypatch.setattr(
        "src.ui.main_window.QMessageBox.question",
        lambda *_args, **_kwargs: MainWindow.__dict__["QMessageBox"].Yes
        if False
        else 16384,
    )
    monkeypatch.setattr(
        "src.ui.main_window.QMessageBox.information",
        lambda *_args, **_kwargs: None,
    )

    MainWindow.import_all_prompts(fake)

    assert fake.loaded == [("text", 0), ("voice", 0)]


def test_hotkey_reset_rolls_back_every_shortcut_on_one_conflict():
    class FakeSettings:
        def __init__(self):
            self.values = {}
            self.synced = False

        def set_hotkey(self, value):
            self.values["hotkey"] = value

        def set_voice_hotkey(self, value):
            self.values["voice_hotkey"] = value

        def set_screenshot_hotkey(self, value):
            self.values["screenshot_hotkey"] = value

        def set_custom_hotkey(self, value):
            self.values["custom_hotkey"] = value

        def sync(self):
            self.synced = True

    class FakeManager:
        def __init__(self, succeeds=True):
            self.succeeds = succeeds
            self.unregister_calls = 0
            self.register_calls = 0
            self._last_register_error = "conflict"

        def unregister_hotkey(self):
            self.unregister_calls += 1

        def register_hotkey(self):
            self.register_calls += 1
            return self.succeeds

    class FakeWindow:
        def __init__(self):
            self.settings = FakeSettings()
            self.hotkey_manager = FakeManager()
            self.voice_hotkey_manager = FakeManager(succeeds=False)
            self.screenshot_hotkey_manager = FakeManager()
            self.custom_hotkey_manager = FakeManager()

    fake = FakeWindow()
    previous = {
        "hotkey": "old-main",
        "voice_hotkey": "old-voice",
        "screenshot_hotkey": "old-screen",
        "custom_hotkey": "old-custom",
    }

    result = MainWindow._reregister_all_hotkeys(fake, previous)

    assert result is False
    assert fake.settings.values == previous
    assert fake.settings.synced is True
    assert all(
        manager.unregister_calls >= 2
        for manager in (
            fake.hotkey_manager,
            fake.voice_hotkey_manager,
            fake.screenshot_hotkey_manager,
            fake.custom_hotkey_manager,
        )
    )


def test_main_window_constructs_without_duplicate_prompts(
    monkeypatch, tmp_path
):
    _app()
    monkeypatch.setattr(
        settings_module.os.path, "expanduser", lambda _path: str(tmp_path)
    )
    monkeypatch.setattr(Settings, "get_api_key", lambda _self: "")
    monkeypatch.setattr(
        "src.audio.voice_recognition.VoiceRecognition.list_microphones",
        lambda: [],
    )
    settings = Settings()

    window = MainWindow(settings)

    assert window.prompt_combo.count() == len(settings.get_prompts())
    assert window.main_layout.count() == 2
    assert hasattr(window, "transcription_languages_input")
    assert hasattr(window, "transcription_keywords_input")
    assert hasattr(window, "transcription_prompt_input")
    assert not hasattr(window, "response_window_open_mode_combo")
    assert window.update_channel_combo.currentData() == "stable"

    beta_index = window.update_channel_combo.findData("beta")
    window.update_channel_combo.setCurrentIndex(beta_index)
    assert settings.get_update_channel() == "beta"
    assert "régressions" in window.update_channel_description.text()
    window.close()
