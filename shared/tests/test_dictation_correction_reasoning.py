"""Dictation correction follows the « Corriger » prompt's reasoning mode."""

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from supermenu_core.audio.backends import SpeechBackend
from supermenu_core.audio.dictation_flow import PlainDictationSession


class Correction(QObject):
    request_finished_scoped = Signal(str, str, bool, object)
    request_error_scoped = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.requests = []

    def send_request(self, instruction, text, **options):
        self.requests.append(options)

    def close(self):
        pass


def corrected_request(before_insert=None, **session_options):
    QApplication.instance() or QApplication([])
    backend = SpeechBackend()
    backend.start = lambda: None
    backend.cancel = lambda: None
    correction = Correction()
    session = PlainDictationSession(
        lambda _: backend,
        {"provider": "foundry"},
        insert_text=lambda text, finished, active: finished(True),
        correction_factory=lambda: correction,
        correct_before_insert=True,
        **session_options,
    )
    session.start_voice_recognition()
    try:
        backend.completed.emit("je sui la")
        if before_insert:
            before_insert()
        session.recording_dialog.insert_button.click()
        assert len(correction.requests) == 1
        return correction.requests[0]
    finally:
        session.cleanup()


def test_default_keeps_previous_request_unchanged():
    options = corrected_request()
    assert options["include_reasoning"] is False
    assert "reasoning_mode" not in options


@pytest.mark.parametrize("mode", ["off", "on"])
def test_prompt_reasoning_mode_is_forwarded(mode):
    assert corrected_request(correction_reasoning_mode=mode)["reasoning_mode"] == mode


def test_reasoning_mode_is_read_when_inserting():
    current = {"mode": "on"}
    options = corrected_request(
        before_insert=lambda: current.update(mode="off"),
        correction_reasoning_mode=lambda: current["mode"],
    )
    assert options["reasoning_mode"] == "off"
    assert options["include_reasoning"] is False


def test_unavailable_reasoning_setting_keeps_text_without_pasting():
    QApplication.instance() or QApplication([])
    backend = SpeechBackend()
    backend.start = lambda: None
    backend.cancel = lambda: None
    pasted = []

    def broken():
        raise ValueError("Réglage illisible")

    session = PlainDictationSession(
        lambda _: backend,
        {"provider": "foundry"},
        insert_text=lambda text, finished, active: pasted.append(text),
        correction_factory=Correction,
        correct_before_insert=True,
        correction_reasoning_mode=broken,
    )
    session.start_voice_recognition()
    try:
        backend.completed.emit("texte original")
        session.recording_dialog.insert_button.click()
        assert not pasted
        assert "Réglage illisible" in session.recording_dialog.hint_label.text()
        assert session.recording_dialog.insert_button.isEnabled()
    finally:
        session.cleanup()
