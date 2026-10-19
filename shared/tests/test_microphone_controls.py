import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QLabel

from supermenu_core.ui import microphone_test as controls
from supermenu_core.ui.settings_panel import SettingsPanel


class Microphone(QObject):
    chunk = Signal(bytes)
    level = Signal(int)
    failed = Signal(str)

    def __init__(self, rate, device, parent):
        super().__init__(parent)
        self.rate, self.device = rate, device
        self.stopped = False

    def start(self):
        pass

    def stop(self):
        self.stopped = True


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def start_test(monkeypatch):
    monkeypatch.setattr(controls, "Microphone", Microphone)
    widget = controls.MicrophoneTest(lambda: "selected-input")
    widget.active = True
    widget._permission(Qt.PermissionStatus.Granted, widget.generation)
    assert widget.microphone.device == "selected-input"
    return widget


@pytest.mark.parametrize("peak, message", [(15, "opérationnel"), (0, "aucun son")])
def test_microphone_check_distinguishes_working_from_muted(
    app, monkeypatch, peak, message
):
    widget = start_test(monkeypatch)
    microphone = widget.microphone
    microphone.chunk.emit(b"\x00\x00")
    microphone.level.emit(peak)
    widget.finish()
    assert microphone.stopped
    assert widget.microphone is None and not widget.timer.isActive()
    assert message in widget.status.text()


def test_page_navigation_stops_capture_and_preserves_settings(app, monkeypatch):
    panel = SettingsPanel()
    voice = panel.add_page("voice", "Dictée", "Microphone")
    text = panel.add_page("text", "Texte", "Correction et traduction")
    selected = QLabel("Mes paramètres")
    text.addWidget(selected)
    widget = start_test(monkeypatch)
    voice.addWidget(widget)
    panel.show()
    app.processEvents()
    microphone = widget.microphone
    assert widget.isVisible()
    panel.select_page("text")
    app.processEvents()
    assert microphone.stopped and widget.microphone is None
    assert not widget.active and not widget.timer.isActive()
    assert selected.isVisible()
    panel.select_page("voice")
    assert widget.isVisible() and widget.microphone is None
    panel.close()


def test_cancelled_permission_prompt_cannot_reopen_microphone(app, monkeypatch):
    widget = controls.MicrophoneTest(lambda: "selected-input")
    widget.active = True
    generation = widget.generation
    widget.cancel()

    def unexpected_start(*_args):
        pytest.fail("A cancelled permission request reopened the microphone")

    monkeypatch.setattr(controls, "Microphone", unexpected_start)
    widget._permission(Qt.PermissionStatus.Granted, generation)
    assert widget.microphone is None


def test_failure_during_open_does_not_restart_test_timer(app, monkeypatch):
    monkeypatch.setattr(controls, "Microphone", Microphone)
    monkeypatch.setattr(Microphone, "start", lambda mic: mic.failed.emit("Déconnecté"))
    widget = controls.MicrophoneTest(lambda: "selected-input")
    widget.active = True
    widget._permission(Qt.PermissionStatus.Granted, widget.generation)
    assert widget.microphone is None and not widget.active
    assert not widget.timer.isActive()
    assert widget.status.text() == "Déconnecté"
