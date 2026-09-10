import json
from array import array

import pytest
from PySide6.QtCore import QSettings, Signal
from PySide6.QtMultimedia import QAudioFormat
from PySide6.QtWidgets import QApplication

from supermenu_core.audio import session as session_module
from supermenu_core.audio.backends import OpenAISpeechBackend, SpeechBackend
from supermenu_core.audio.microphone import PCMConverter
from supermenu_core.audio.settings import SpeechSettingsMixin, local_language
from supermenu_core.audio.session import DictationSession
from supermenu_core.ui.dictation_dialog import RecordingDialog
from supermenu_core.ui.speech_settings import SpeechSettingsWidget


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


class FakeBackend(SpeechBackend):
    def __init__(self):
        super().__init__()
        self.cancelled = False
        self.finished = False
        self.audio = []

    def start(self):
        pass

    def append(self, pcm):
        self.audio.append(pcm)

    def finish(self):
        self.finished = True

    def cancel(self):
        self.cancelled = True


class FakeMicrophone(SpeechBackend):
    chunk = Signal(bytes)
    level = Signal(int)
    stop_count = 0

    def __init__(self, *_args):
        super().__init__()

    def start(self):
        pass

    def stop(self, flush=False):
        self.stop_count += 1


def test_stream_conversion_preserves_split_frames_and_resampling():
    fmt = QAudioFormat()
    fmt.setSampleRate(48000)
    fmt.setChannelCount(2)
    fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
    pcm = array("f", [0.1, 0.3, -0.5, -0.3] * 500).tobytes()
    whole = PCMConverter(fmt, 16000).convert(pcm)
    fragmented = PCMConverter(fmt, 16000)
    pieces = b"".join(
        fragmented.convert(pcm[i : i + 113]) for i in range(0, len(pcm), 113)
    )
    assert pieces == whole
    assert len(whole) == 668
    assert array("h", whole)[0] == pytest.approx(6553, abs=2)


def test_openai_protocol_streams_then_replaces_final_text(app):
    backend = OpenAISpeechBackend(
        "test-key", {"languages": ["fr"], "keywords": ["SuperMenu"]}
    )
    sent, snapshots, completed = [], [], []
    backend._send = sent.append
    backend.transcript.connect(snapshots.append)
    backend.completed.connect(completed.append)
    backend._configure()
    config = sent[0]["session"]["audio"]["input"]
    assert config["format"] == {"type": "audio/pcm", "rate": 24000}
    assert config["transcription"]["model"] == "gpt-live-transcribe"
    assert config["transcription"]["languages"] == ["fr"]
    assert config["turn_detection"] is None
    for delta in ("Bonjour", " monde"):
        backend._receive(
            json.dumps(
                {
                    "type": "conversation.item.input_audio_transcription.delta",
                    "item_id": "a",
                    "delta": delta,
                }
            )
        )
    backend.audio_bytes = 10000
    backend.finish()
    assert sent[-1] == {"type": "input_audio_buffer.commit"}
    backend._receive(
        json.dumps(
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "item_id": "a",
                "transcript": "Bonjour, monde.",
            }
        )
    )
    assert snapshots == ["Bonjour", "Bonjour monde", "Bonjour, monde."]
    assert completed == ["Bonjour, monde."]
    backend._receive(json.dumps({"type": "error", "error": {"code": "bad"}}))
    assert backend.closed


def test_cancel_preparation_ignores_late_ready_and_transcript(app, monkeypatch):
    backend = FakeBackend()
    session = DictationSession(lambda _: backend, {"provider": "foundry"})
    activated = []
    monkeypatch.setattr(session, "_ready", lambda: activated.append(True))
    session.start_voice_recognition()
    session.recording_dialog.close()
    backend.ready.emit()
    backend.transcript.emit("Late result")
    assert backend.cancelled
    assert not activated
    assert not session.recording_dialog.transcript_edit.toPlainText()


def test_stop_finalizes_once_and_hands_final_snapshot_to_callback(app, monkeypatch):
    monkeypatch.setattr(session_module, "Microphone", FakeMicrophone)
    backend, completed = FakeBackend(), []
    session = DictationSession(
        lambda _: backend, {"provider": "foundry"}, completed.append
    )
    session.start_voice_recognition()
    session._start_microphone()
    mic = session.microphone
    backend.transcript.emit("provisoire")
    session.recording_dialog.stop_button.click()
    assert backend.finished and mic.stop_count == 1
    assert not session.is_recording
    backend.completed.emit("Texte final.")
    assert completed == ["Texte final."]
    assert not session.recording_dialog.isVisible()
    assert session.microphone is None and backend.cancelled


def test_failure_during_microphone_flush_never_finalizes_cancelled_backend(
    app, monkeypatch
):
    monkeypatch.setattr(session_module, "Microphone", FakeMicrophone)
    backend = FakeBackend()
    session = DictationSession(lambda _: backend, {"provider": "openai"})
    session.start_voice_recognition()
    session._start_microphone()
    mic = session.microphone
    mic.stop = lambda flush=False: (
        backend.failed.emit("Connexion perdue") if flush else None
    )
    session.finish()
    assert not backend.finished
    assert session.recording_dialog._state == "error"
    session.cleanup()


def test_error_keeps_partial_transcript_copyable_and_retryable(app):
    dialog = RecordingDialog()
    dialog.set_transcript("Texte conservé")
    dialog.set_error("Microphone débranché")
    assert dialog.copy_button.isEnabled()
    assert dialog.stop_button.text() == "Réessayer"
    assert dialog.transcript_edit.toPlainText() == "Texte conservé"
    dialog.dismiss()


def test_cancel_during_finalization_stops_engine_once(app):
    dialog = RecordingDialog()
    calls = []
    dialog.recording_cancelled.connect(lambda: calls.append(True))
    dialog.set_processing("Finalisation")
    dialog.close()
    dialog.close()
    assert calls == [True]


class Settings(SpeechSettingsMixin):
    def __init__(self, path):
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)
        self.key = ""

    def get_api_key(self):
        return self.key

    def set_api_key(self, key):
        self.key = key

    def sync(self):
        self.settings.sync()


def test_voice_settings_local_choice_and_probe_do_not_change_text_provider(
    app, tmp_path
):
    settings = Settings(tmp_path / "settings.ini")
    settings.settings.setValue("ai_provider", "custom")
    backend = FakeBackend()
    widget = SpeechSettingsWidget(settings, lambda options: backend, platform="win32")
    widget.provider_combo.setCurrentIndex(widget.provider_combo.findData("foundry"))
    widget.prepare("probe")
    backend.result.emit({"cached": False, "device": "CUDA"})
    assert widget.download_button.isEnabled()
    assert "télécharger" in widget.status.title.text()
    assert widget.save()
    assert settings.get_speech_provider() == "foundry"
    assert settings.settings.value("ai_provider") == "custom"
    assert "api_key" not in widget.options()
    widget.cancel(silent=True)


def test_apple_requires_exactly_one_language_and_foundry_allows_auto():
    assert local_language("fr-CA", "apple") == "fr-ca"
    assert local_language("", "foundry") == "auto"
    for provider, value in (("apple", ""), ("apple", "fr,en"), ("foundry", "fr,en")):
        with pytest.raises(ValueError):
            local_language(value, provider)


def test_custom_language_editor_stays_open_when_typing_a_preset(app, tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    widget = SpeechSettingsWidget(
        settings, lambda options: FakeBackend(), platform="win32"
    )
    widget.language_combo.setCurrentIndex(widget.language_combo.findData(None))
    widget.languages_input.setText("")
    widget.languages_input.setText("fr")
    assert widget.language_combo.currentData() is None
    assert not widget.languages_input.isHidden()
    widget.languages_input.setText("fr, en")
    assert widget.options()["languages"] == ["fr", "en"]
    widget.language_combo.setCurrentIndex(widget.language_combo.findData("de"))
    assert widget.languages_input.isHidden()
    assert widget.options()["languages"] == ["de"]


def test_microphone_refresh_keeps_unsaved_default_choice(app, tmp_path, monkeypatch):
    from supermenu_core.ui import speech_settings

    settings = Settings(tmp_path / "settings.ini")
    settings.set_speech_microphone("saved-mic")
    monkeypatch.setattr(
        speech_settings, "microphones", lambda: [("saved-mic", "Input")]
    )
    widget = SpeechSettingsWidget(
        settings, lambda options: FakeBackend(), platform="win32"
    )
    assert widget.microphone_combo.currentData() == "saved-mic"
    widget.microphone_combo.setCurrentIndex(0)
    widget.refresh_microphones()
    assert widget.microphone_combo.currentData() == ""
