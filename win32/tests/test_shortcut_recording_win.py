"""Shortcut recording, inactive shortcuts and reset order in the main window."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QDialog

from src.config import settings as settings_module
from src.config.settings import Settings
from src.ui import main_window
from src.ui.main_window import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


class FakeHotkeyManager(QObject):
    registration_failed = Signal(str)

    def __init__(self, name, events, getter, setter, feature):
        super().__init__()
        self.name = name
        self.events = events
        self.getter = getter
        self.setter = setter
        self.feature_name = feature
        self.hotkey = getter()
        self.registered = True
        self._last_register_error = ""
        self.set_hotkey_result = True
        self.others_registered_on_set = None
        self.peers = []

    @property
    def last_error(self):
        return self._last_register_error

    def unregister_hotkey(self):
        self.events.append(f"{self.name}:unregister")
        self.registered = False

    def register_hotkey(self):
        self.events.append(f"{self.name}:register")
        self.hotkey = self.getter()
        self.registered = True
        self._last_register_error = ""
        return True

    def set_hotkey(self, hotkey):
        self.events.append(f"{self.name}:set:{hotkey}")
        self.others_registered_on_set = all(peer.registered for peer in self.peers)
        if not self.set_hotkey_result:
            self._last_register_error = "Raccourci déjà utilisé"
            return False
        self.setter(hotkey)
        self.hotkey = hotkey
        self.registered = True
        return True


class FakePromptHotkeyManager:
    def __init__(self, events):
        self.events = events
        self.errors = {}
        self.registered = True

    def unregister_hotkeys(self):
        self.events.append("prompts:unregister")
        self.registered = False

    def refresh_hotkeys(self):
        self.events.append("prompts:refresh")
        self.registered = True
        return True, {}


@pytest.fixture
def window_with_managers(monkeypatch, tmp_path):
    _app()
    monkeypatch.setattr(settings_module.os.path, "expanduser", lambda _path: str(tmp_path))
    monkeypatch.setattr(Settings, "get_api_key", lambda _self: "")
    monkeypatch.setattr(Settings, "get_custom_endpoint_api_key", lambda _self: "")
    monkeypatch.setattr("supermenu_core.ui.speech_settings.microphones", lambda: [])
    settings = Settings()
    events = []
    managers = {
        "main": FakeHotkeyManager("main", events, settings.get_hotkey, settings.set_hotkey, "Menu principal"),
        "voice": FakeHotkeyManager("voice", events, settings.get_voice_hotkey, settings.set_voice_hotkey, "Menu vocal"),
        "custom": FakeHotkeyManager("custom", events, settings.get_custom_hotkey, settings.set_custom_hotkey, "Mode personnalisé"),
        "screenshot": FakeHotkeyManager(
            "screenshot", events, settings.get_screenshot_hotkey, settings.set_screenshot_hotkey, "Capture d’écran"
        ),
        "dictation": FakeHotkeyManager(
            "dictation", events, settings.get_dictation_hotkey, settings.set_dictation_hotkey, "Dictée"
        ),
    }
    for manager in managers.values():
        manager.peers = [peer for peer in managers.values() if peer is not manager]
    prompts = FakePromptHotkeyManager(events)
    window = MainWindow(
        settings,
        hotkey_manager=managers["main"],
        voice_hotkey_manager=managers["voice"],
        screenshot_hotkey_manager=managers["screenshot"],
        custom_hotkey_manager=managers["custom"],
        prompt_hotkey_manager=prompts,
        dictation_hotkey_manager=managers["dictation"],
    )
    messages = {"information": [], "warning": []}
    monkeypatch.setattr(
        main_window.QMessageBox, "information", lambda *args, **_kw: messages["information"].append(args)
    )
    monkeypatch.setattr(
        main_window.QMessageBox, "warning", lambda *args, **_kw: messages["warning"].append(args)
    )
    yield window, managers, prompts, events, messages
    window.hide()
    window.deleteLater()


def _fake_recorder(monkeypatch, managers, prompts, recorded, accepted=True):
    seen = {}

    class FakeRecorder:
        def __init__(self, parent=None):
            self.recorded_hotkey = recorded

        def exec(self):
            seen["registered"] = {name: manager.registered for name, manager in managers.items()}
            seen["prompts_registered"] = prompts.registered
            if accepted:
                return QDialog.DialogCode.Accepted
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(main_window, "HotkeyRecorderDialog", FakeRecorder)
    return seen


@pytest.mark.parametrize(
    ("method", "manager_name"),
    [
        ("change_hotkey", "main"),
        ("change_voice_hotkey", "voice"),
        ("change_custom_hotkey", "custom"),
        ("change_screenshot_hotkey", "screenshot"),
    ],
)
def test_every_shortcut_is_released_while_a_main_shortcut_is_recorded(
    monkeypatch, window_with_managers, method, manager_name
):
    window, managers, prompts, events, messages = window_with_managers
    seen = _fake_recorder(monkeypatch, managers, prompts, "Ctrl+Alt+K")

    getattr(window, method)()

    # Pressing Ctrl+Alt+M (custom mode) in the main dialog used to run the
    # custom mode instead of being recorded.
    assert not any(seen["registered"].values())
    assert seen["prompts_registered"] is False
    # The new shortcut is applied once the others are back, so a combination
    # SuperMenu already uses is still refused by Windows.
    assert managers[manager_name].others_registered_on_set is True
    assert all(manager.registered for manager in managers.values())
    assert events[-1] == f"{manager_name}:set:Ctrl+Alt+K"
    assert len(messages["information"]) == 1
    assert messages["warning"] == []


def test_new_main_shortcut_is_shown_in_its_row(monkeypatch, window_with_managers):
    window, managers, prompts, _events, _messages = window_with_managers
    _fake_recorder(monkeypatch, managers, prompts, "Ctrl+Alt+K")

    window.change_hotkey()

    assert window.settings.get_hotkey() == "Ctrl+Alt+K"
    assert window.hotkey_label.text() == "Ctrl+Alt+K"


def test_refused_main_shortcut_keeps_the_previous_one(monkeypatch, window_with_managers):
    window, managers, prompts, _events, messages = window_with_managers
    previous = window.settings.get_custom_hotkey()
    managers["custom"].set_hotkey_result = False
    _fake_recorder(monkeypatch, managers, prompts, "Ctrl+Alt+K")

    window.change_custom_hotkey()

    assert window.settings.get_custom_hotkey() == previous
    assert messages["information"] == []
    assert "Raccourci déjà utilisé" in messages["warning"][0][2]


def test_cancelled_recording_restores_every_shortcut(monkeypatch, window_with_managers):
    window, managers, prompts, events, messages = window_with_managers
    _fake_recorder(monkeypatch, managers, prompts, "Ctrl+Alt+K", accepted=False)

    window.change_voice_hotkey()

    assert not any(":set:" in event for event in events)
    assert all(manager.registered for manager in managers.values())
    assert prompts.registered is True
    assert messages == {"information": [], "warning": []}


def test_prompt_and_dictation_recording_share_the_same_release(monkeypatch, window_with_managers):
    window, managers, prompts, _events, _messages = window_with_managers
    seen = _fake_recorder(monkeypatch, managers, prompts, "Ctrl+Alt+P")

    window.record_prompt_hotkey()

    assert not any(seen["registered"].values())
    assert window.prompt_hotkey_input.text() == "Ctrl+Alt+P"
    assert all(manager.registered for manager in managers.values())
    assert prompts.registered is True


def test_refused_shortcut_is_marked_inactive_in_its_row(window_with_managers):
    window, managers, _prompts, _events, _messages = window_with_managers
    voice = managers["voice"]
    voice.registered = False
    voice._last_register_error = "Raccourci déjà utilisé par une autre application"

    voice.registration_failed.emit(voice._last_register_error)

    expected = window.settings.get_voice_hotkey()
    assert window.voice_hotkey_label.text() == f"{expected} (inactif)"
    assert "déjà utilisé" in window.voice_hotkey_label.toolTip()
    assert window.hotkey_label.text() == window.settings.get_hotkey()

    voice.register_hotkey()
    window._refresh_hotkey_states()
    assert window.voice_hotkey_label.text() == expected
    assert window.voice_hotkey_label.toolTip() == ""


def test_main_window_reports_an_inactive_main_shortcut(window_with_managers):
    window, managers, _prompts, _events, _messages = window_with_managers
    main = managers["main"]
    main.registered = False
    main._last_register_error = "Raccourci déjà utilisé"

    window.show_main_window()

    message = window.statusBar().currentMessage()
    assert message.startswith("Raccourci inactif — Menu principal")
    assert "Raccourci déjà utilisé" in message
    assert "(inactif)" in window.hotkey_label.text()


def test_reset_releases_prompt_shortcuts_before_the_defaults(monkeypatch, window_with_managers):
    window, _managers, _prompts, events, messages = window_with_managers
    monkeypatch.setattr(main_window.QMessageBox, "question", lambda *_a, **_k: main_window.QMessageBox.Yes)
    events.clear()

    window.reset_all_settings()

    first_core_register = min(
        index for index, event in enumerate(events) if event.endswith(":register") and not event.startswith("prompts")
    )
    # A prompt holding a default combination used to make the reset fail
    # and roll every main shortcut back.
    assert events.index("prompts:unregister") < first_core_register
    assert "prompts:refresh" in events[first_core_register:]
    assert messages["information"] and not messages["warning"]
