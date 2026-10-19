"""Regression tests for the macOS shortcut recorder, validation and logging."""

import sys

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from src.utils import hotkey_manager
from src.utils.hotkey_manager import (
    HotkeyManager,
    HotkeyRecorderDialog,
    HotkeyService,
    PromptHotkeyManager,
    _MacOSGlobalHotKeys,
    _recorded_character_key,
    normalize_hotkey,
)


# Qt reports Command as ControlModifier on macOS and as MetaModifier elsewhere.
CMD = (
    Qt.KeyboardModifier.ControlModifier
    if sys.platform == "darwin"
    else Qt.KeyboardModifier.MetaModifier
)
OPTION = Qt.KeyboardModifier.AltModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier

# Fake AppKit modifier flags, matching FakeAppKitEventAPI below.
FLAG_CMD, FLAG_CTRL, FLAG_OPTION, FLAG_SHIFT = 1, 2, 4, 8


class FakeAppKitEventAPI:
    command_flag = FLAG_CMD
    control_flag = FLAG_CTRL
    option_flag = FLAG_OPTION
    shift_flag = FLAG_SHIFT
    independent_flags_mask = 15

    def __init__(self):
        self.global_handler = None
        self.local_handler = None

    def add_global_monitor(self, handler):
        self.global_handler = handler
        return "global"

    def add_local_monitor(self, handler):
        self.local_handler = handler
        return "local"

    def remove_monitor(self, monitor):
        pass


class FakeKeyDown:
    def __init__(self, flags, key_code, characters):
        self._flags = flags
        self._key_code = key_code
        self._characters = characters

    def type(self):
        return 10  # NSEventTypeKeyDown

    def modifierFlags(self):
        return self._flags

    def keyCode(self):
        return self._key_code

    def charactersIgnoringModifiers(self):
        return self._characters

    def isARepeat(self):
        return False


class FakePersistentListener:
    instances = []

    def __init__(self):
        self.bindings = {}
        self.alive = False
        self.__class__.instances.append(self)

    def replace_bindings(self, bindings):
        self.bindings = dict(bindings)

    def set_suspended(self, suspended):
        pass

    def start(self):
        self.alive = True

    def wait(self):
        return None

    def is_alive(self):
        return self.alive

    def stop(self):
        self.alive = False

    def join(self, timeout=None):
        pass


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _record(dialog, key, modifiers, text=""):
    dialog.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text))


# --- Finding 11: no unrelated keystroke reaches the log -----------------------


def test_unmatched_keystrokes_are_never_logged(monkeypatch):
    messages = []
    monkeypatch.setattr(
        hotkey_manager, "log", lambda message, *args: messages.append(message)
    )
    api = FakeAppKitEventAPI()
    listener = _MacOSGlobalHotKeys(event_api=api)
    triggered = []
    listener.replace_bindings(
        {
            "<cmd>+<shift>+<space>": lambda: triggered.append("menu"),
            "<cmd>+<shift>+m": lambda: triggered.append("custom"),
            # Bound directly to the listener: the same modifiers as typing.
            "<shift>+k": lambda: triggered.append("shift-k"),
        }
    )
    listener.start()

    for character in "PASS":
        api.global_handler(FakeKeyDown(FLAG_SHIFT, 0x23, character))
    api.global_handler(FakeKeyDown(FLAG_CMD | FLAG_SHIFT, 0x11, "T"))
    api.global_handler(FakeKeyDown(FLAG_CMD | FLAG_SHIFT, 0x06, "Z"))

    assert triggered == []
    assert messages == []

    api.global_handler(FakeKeyDown(FLAG_CMD | FLAG_SHIFT, 0x2E, "M"))

    assert triggered == ["custom"]
    assert messages == ["Raccourci global AppKit détecté : <cmd>+<shift>+m"]


# --- Finding 12: the recorder reads keys like the AppKit detector -------------


def test_recorded_option_shortcut_matches_the_native_detector(qt_app):
    dialog = HotkeyRecorderDialog()
    # Qt gives the composed character as text, AppKit compares "k".
    _record(dialog, Qt.Key.Key_K, CMD | OPTION, "˚")

    assert dialog.recorded_hotkey == "Cmd+Option+K"
    assert dialog.ok_button.isEnabled() is True

    normalized, error = normalize_hotkey(dialog.recorded_hotkey)
    assert error == ""
    api = FakeAppKitEventAPI()
    listener = _MacOSGlobalHotKeys(event_api=api)
    triggered = []
    listener.replace_bindings({normalized: lambda: triggered.append(True)})
    listener.start()
    api.global_handler(FakeKeyDown(FLAG_CMD | FLAG_OPTION, 0x28, "k"))

    assert triggered == [True]
    dialog.deleteLater()


def test_recorder_accepts_command_letters_without_qt_text(qt_app):
    dialog = HotkeyRecorderDialog()
    # Qt leaves text() empty while Command or Control is held.
    _record(dialog, Qt.Key.Key_M, CMD | SHIFT, "")

    assert dialog.recorded_hotkey == "Cmd+Shift+M"
    assert dialog.ok_button.isEnabled() is True
    dialog.deleteLater()


def test_recorder_names_shift_tab_like_the_detector(qt_app):
    dialog = HotkeyRecorderDialog()
    _record(dialog, Qt.Key.Key_Backtab, CMD | SHIFT, "")

    assert dialog.recorded_hotkey == "Cmd+Shift+Tab"
    assert normalize_hotkey(dialog.recorded_hotkey) == ("<cmd>+<shift>+<tab>", "")
    dialog.deleteLater()


def test_recorder_refuses_option_only_letters(qt_app):
    dialog = HotkeyRecorderDialog()
    _record(dialog, Qt.Key.Key_K, OPTION, "˚")

    assert dialog.recorded_hotkey == ""
    assert dialog.ok_button.isEnabled() is False
    assert "Cmd ou Ctrl" in dialog.current_hotkey_label.text()
    dialog.deleteLater()


def test_character_key_ignores_composed_text_when_qt_key_is_unknown():
    unknown = int(Qt.Key.Key_unknown)

    assert _recorded_character_key(unknown, "˚", option_held=True) is None
    assert _recorded_character_key(unknown, "é") == "É"
    assert _recorded_character_key(int(Qt.Key.Key_Less), "") == "<"
    assert _recorded_character_key(int(Qt.Key.Key_Plus), "+") is None
    # U+FFFD is what Qt reports for a key Cocoa left without a character,
    # such as a dead key; it would never match charactersIgnoringModifiers.
    assert _recorded_character_key(0xFFFD, "") is None
    assert _recorded_character_key(unknown, "\ufffd") is None
    # Apple's function-key characters are not names either.
    assert _recorded_character_key(0xF704, "") is None


def test_recorder_refuses_a_dead_key_reported_as_replacement_character(qt_app):
    dialog = HotkeyRecorderDialog()
    # Cmd+^ on a French keyboard: no character, Qt falls back to U+FFFD.
    dialog.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, 0xFFFD, CMD | SHIFT, ""))

    assert dialog.recorded_hotkey == ""
    assert dialog.ok_button.isEnabled() is False
    assert dialog.current_hotkey_label.text() == "Touche non supportée"
    dialog.deleteLater()


# --- Finding 55: shortcuts that would fire while typing are refused -----------


@pytest.mark.parametrize(
    "hotkey",
    [
        "Shift+K",
        "Option+K",
        "Shift+Option+K",
        "Option+Space",
        "Shift+Enter",
        "Option+Left",
        "Shift+1",
    ],
)
def test_shift_or_option_alone_is_refused_for_typing_keys(hotkey):
    normalized, error = normalize_hotkey(hotkey)

    assert normalized is None
    assert "Cmd ou Ctrl" in error
    # A shortcut saved by an earlier version keeps being accepted.
    legacy, legacy_error = normalize_hotkey(hotkey, legacy=True)
    assert legacy is not None
    assert legacy_error == ""


@pytest.mark.parametrize("key", ["A", "C", "V", "X", "Z"])
def test_text_editing_command_shortcuts_are_reserved(key):
    normalized, error = normalize_hotkey(f"Cmd+{key}")

    assert normalized is None
    assert "réservé" in error
    # SuperMenu posts Cmd+C and Cmd+V itself: never bound, even when saved.
    assert normalize_hotkey(f"Cmd+{key}", legacy=True)[0] is None


@pytest.mark.parametrize(
    "hotkey,expected",
    [
        ("Option+F12", "<alt>+<f12>"),
        ("Shift+F5", "<shift>+<f5>"),
        ("Cmd+Shift+C", "<cmd>+<shift>+c"),
        ("Cmd+Option+K", "<cmd>+<alt>+k"),
        ("Ctrl+Alt+I", "<ctrl>+<alt>+i"),
        ("Ctrl+K", "<ctrl>+k"),
        ("Ctrl+Shift+Left", "<ctrl>+<shift>+<left>"),
        ("Cmd+Shift+Space", "<cmd>+<shift>+<space>"),
        ("Cmd+Shift+<", "<cmd>+<shift>+<"),
    ],
)
def test_usual_global_shortcuts_stay_valid(hotkey, expected):
    assert normalize_hotkey(hotkey) == (expected, "")


class _Settings:
    def __init__(self, main="Cmd+Shift+Space", prompts=None):
        self.main = main
        self.custom = "Cmd+Shift+M"
        self.prompts = prompts or {}

    def get_hotkey(self):
        return self.main

    def set_hotkey(self, value):
        self.main = value

    def get_custom_hotkey(self):
        return self.custom

    def set_custom_hotkey(self, value):
        self.custom = value

    def get_prompts(self):
        return dict(self.prompts)


def test_stored_shift_only_shortcut_keeps_working_after_the_update(monkeypatch):
    messages = []
    monkeypatch.setattr(
        hotkey_manager, "log", lambda message, *args: messages.append(message)
    )
    FakePersistentListener.instances = []
    service = HotkeyService(listener_factory=FakePersistentListener)

    manager = HotkeyManager(_Settings(main="Shift+K"), service=service)

    # Accepted by the previous recorder: dropping it silently would break the
    # user's shortcut, so it stays bound and the log asks to replace it.
    assert manager.registered is True
    assert manager.last_register_error == ""
    assert manager.refused_hotkey_error == ""
    assert "<shift>+k" in FakePersistentListener.instances[-1].bindings
    assert any("à remplacer" in message for message in messages)
    service.close()


def test_new_shift_only_choice_is_refused_but_the_saved_one_is_kept():
    FakePersistentListener.instances = []
    service = HotkeyService(listener_factory=FakePersistentListener)
    settings = _Settings(main="Option+Space")
    manager = HotkeyManager(settings, service=service)

    assert manager.set_hotkey("Shift+K") is False
    assert "Cmd ou Ctrl" in manager.last_register_error
    assert settings.main == "Option+Space"
    assert "<alt>+<space>" in FakePersistentListener.instances[-1].bindings

    assert manager.set_hotkey("Cmd+Shift+K") is True
    assert settings.main == "Cmd+Shift+K"
    service.close()


def test_stored_shortcut_refused_by_validation_is_reported():
    FakePersistentListener.instances = []
    service = HotkeyService(listener_factory=FakePersistentListener)

    manager = HotkeyManager(_Settings(main="Cmd+C"), service=service)

    assert manager.registered is False
    assert "réservé" in manager.refused_hotkey_error
    assert manager.last_register_error == manager.refused_hotkey_error
    assert all(
        "<cmd>+c" not in listener.bindings
        for listener in FakePersistentListener.instances
    )
    service.close()


def test_one_refused_prompt_shortcut_keeps_the_other_prompts_bound():
    FakePersistentListener.instances = []
    service = HotkeyService(listener_factory=FakePersistentListener)
    settings = _Settings(
        prompts={
            "typing": {"name": "Ancien", "hotkey": "Option+K", "position": 10},
            "refused": {"name": "Copie", "hotkey": "Cmd+C", "position": 15},
            "valid": {"name": "Valide", "hotkey": "Cmd+Option+K", "position": 20},
        }
    )

    manager = PromptHotkeyManager(settings, service=service)

    assert set(manager.errors) == {"refused"}
    assert "réservé" in manager.errors["refused"]
    assert set(FakePersistentListener.instances[-1].bindings) == {
        "<alt>+k",
        "<cmd>+<alt>+k",
    }
    service.close()
