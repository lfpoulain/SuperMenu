from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QApplication

from supermenu_core.audio import session as session_module
from supermenu_core.audio.backends import SpeechBackend
from supermenu_core.audio.dictation_flow import PlainDictationSession
from supermenu_core.audio.dictation_shortcut import DictationShortcut
from supermenu_core.audio.settings import SpeechSettingsMixin
from supermenu_core.config.model_memory import TextMemorySettingsMixin
from supermenu_core.ui.dictation_settings import (
    DictationBehaviorSettings,
    DictationShortcutSettings,
)


class Correction(QObject):
    request_finished_scoped = Signal(str, str, bool, object)
    request_error_scoped = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.requests = []
        self.closed = False

    def send_request(self, instruction, text, **options):
        self.requests.append((instruction, text, options))

    def close(self):
        self.closed = True

    def complete(self, text):
        self.request_finished_scoped.emit(
            self.requests[-1][2]["request_id"], text, False, None
        )


@pytest.fixture
def flow():
    QApplication.instance() or QApplication([])
    backend = SpeechBackend()
    backend.start = lambda: None
    backend.cancel = lambda: None
    pasted, correction = [], Correction()

    def insert(text, finished, active):
        if active():
            pasted.append(text)
            finished(True)

    session = PlainDictationSession(
        lambda _: backend,
        {"provider": "foundry"},
        insert_text=insert,
        correction_factory=lambda: correction,
    )
    session.start_voice_recognition()
    yield SimpleNamespace(
        session=session,
        backend=backend,
        pasted=pasted,
        correction=correction,
        dialog=session.recording_dialog,
    )
    session.cleanup()


@pytest.mark.parametrize("automatic", [False, True])
@pytest.mark.parametrize("correct", [False, True])
def test_final_transcription_is_the_only_text_delivered(flow, automatic, correct):
    flow.session.auto_insert = automatic
    flow.session.correct_before_insert = correct
    flow.backend.transcript.emit("Texte incomplet")
    flow.dialog.insert_button.click()
    assert not flow.pasted and not flow.correction.requests
    flow.backend.completed.emit("je sui la")
    assert flow.session.microphone is None
    if not automatic:
        assert flow.dialog.isVisible() and not flow.pasted
        flow.dialog.insert_button.click()
    if correct:
        assert not flow.pasted
        assert flow.correction.requests[0][1] == "je sui la"
        assert flow.correction.requests[0][2]["include_reasoning"] is False
        flow.correction.complete("<think>Analyse privée</think>Je suis là.")
        assert flow.pasted == ["Je suis là."]
    else:
        assert flow.pasted == ["je sui la"]
    assert flow.dialog.isVisible() is not automatic
    flow.dialog.insert_button.click()
    assert len(flow.pasted) == 1


def test_manual_insertion_uses_edits_made_to_final_transcription(flow):
    flow.backend.completed.emit("Bonjour")
    flow.dialog.transcript_edit.setPlainText("Bonjour, Camille.")
    flow.dialog.copy_button.click()
    assert QApplication.clipboard().text() == "Bonjour, Camille."
    flow.dialog.insert_button.click()
    assert flow.pasted == ["Bonjour, Camille."]


def test_cancellation_during_correction_prevents_late_paste(flow):
    flow.session.correct_before_insert = True
    flow.backend.completed.emit("texte")
    flow.dialog.insert_button.click()
    flow.dialog.reject()
    flow.correction.complete("Texte corrigé")
    assert flow.correction.closed and not flow.pasted


def test_correction_error_retains_original_text_without_pasting(flow):
    flow.session.auto_insert = flow.session.correct_before_insert = True
    flow.backend.completed.emit("texte original")
    request_id = flow.correction.requests[0][2]["request_id"]
    flow.correction.request_error_scoped.emit(request_id, "Moteur indisponible")
    assert not flow.pasted
    assert flow.dialog.isVisible() and flow.dialog.insert_button.isEnabled()
    assert flow.dialog.transcript_edit.toPlainText() == "texte original"
    assert "Rien n’a été collé" in flow.dialog.hint_label.text()


def test_failed_target_keeps_corrected_text_available(flow):
    flow.session.auto_insert = True
    flow.session._insert_text = lambda text, done, active: done(False, "target_changed")
    flow.backend.completed.emit("Texte final")
    assert flow.dialog.isVisible() and flow.dialog.copy_button.isEnabled()
    assert "cible" in flow.dialog.hint_label.text()


def test_release_during_preparation_blocks_every_late_microphone_start(
    flow, monkeypatch
):
    starts = []
    monkeypatch.setattr(flow.session, "_start_microphone", lambda: starts.append(True))
    flow.session.stop_listening()
    flow.backend.ready.emit()
    flow.backend.completed.emit("Trop tard")
    assert not starts and not flow.pasted and not flow.dialog.isVisible()


def test_release_during_listening_flushes_and_finalizes_once(flow, monkeypatch):
    class Microphone(QObject):
        chunk = Signal(bytes)
        level = Signal(int)
        failed = Signal(str)

        def __init__(self, *_args):
            super().__init__()

        def start(self):
            pass

        def stop(self, flush=False):
            if flush:
                self.chunk.emit(b"last samples")

    events = []
    monkeypatch.setattr(session_module, "Microphone", Microphone)
    flow.backend.append = lambda chunk: events.append(chunk)
    flow.backend.finish = lambda: events.append("finish")
    flow.session._start_microphone()
    flow.session.stop_listening()
    flow.session.stop_listening()
    assert events == [b"last samples", "finish"]


@pytest.mark.parametrize(
    "mode,expected", [("hold", ["start", "stop"]), ("press", ["start"])]
)
def test_shortcut_ignores_repeat_and_snapshots_mode_until_release(mode, expected):
    QApplication.instance() or QApplication([])
    settings = SimpleNamespace(get_dictation_hotkey_mode=lambda: mode)
    shortcut = DictationShortcut(settings)
    events = []
    shortcut.started.connect(lambda: events.append("start"))
    shortcut.released.connect(lambda: events.append("stop"))
    shortcut.press()
    shortcut.press()
    settings.get_dictation_hotkey_mode = lambda: "press" if mode == "hold" else "hold"
    shortcut.release()
    shortcut.release()
    assert events == expected


def test_shared_preferences_persist_without_changing_prompt_behavior(tmp_path):
    QApplication.instance() or QApplication([])

    class Settings(SpeechSettingsMixin, TextMemorySettingsMixin):
        def __init__(self):
            self.settings = QSettings(
                str(tmp_path / "settings.ini"), QSettings.IniFormat
            )

        def sync(self):
            self.settings.sync()

    settings = Settings()
    settings.settings.setValue("voice_prompts", "preserved")
    delivery = DictationBehaviorSettings(settings)
    delivery.auto_insert.setChecked(True)
    delivery.correct_before_insert.setChecked(True)
    shortcuts = DictationShortcutSettings(settings)
    shortcuts.set_shortcut("Ctrl+Alt+D")
    shortcuts.mode.setCurrentIndex(shortcuts.mode.findData("hold"))
    settings.set_text_idle_seconds(-1)
    settings.sync()
    loaded = Settings()
    assert loaded.get_dictation_hotkey() == "Ctrl+Alt+D"
    assert loaded.get_dictation_hotkey_mode() == "hold"
    assert (
        loaded.get_dictation_auto_insert()
        and loaded.get_dictation_correct_before_insert()
    )
    assert loaded.get_text_idle_seconds() == -1
    assert loaded.settings.value("voice_prompts") == "preserved"
