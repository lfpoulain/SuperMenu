import src.utils.hotkey_manager as hotkey_module
from src.utils.hotkey_manager import (
    HotkeyManager,
    HotkeyService,
    _PersistentGlobalHotKeys,
    _modifier_labels,
    normalize_hotkey,
)
from PySide6.QtCore import Qt


class FakePersistentListener:
    instances = []

    def __init__(self):
        self.bindings = {}
        self.alive = False
        self.suspended = False
        self.start_calls = 0
        self.stop_calls = 0
        self.join_calls = 0
        self.__class__.instances.append(self)

    def replace_bindings(self, bindings):
        self.bindings = dict(bindings)

    def set_suspended(self, suspended):
        self.suspended = bool(suspended)

    def start(self):
        self.start_calls += 1
        self.alive = True

    def wait(self):
        return None

    def is_alive(self):
        return self.alive

    def stop(self):
        self.stop_calls += 1
        self.alive = False

    def join(self, timeout=None):
        self.join_calls += 1


class HotkeySettingsStub:
    def __init__(self):
        self.main = "Cmd+Shift+Space"
        self.custom = "Cmd+Shift+M"

    def get_hotkey(self):
        return self.main

    def set_hotkey(self, value):
        self.main = value

    def get_custom_hotkey(self):
        return self.custom

    def set_custom_hotkey(self, value):
        self.custom = value


def test_command_hotkey_is_normalized_for_pynput():
    normalized, error = normalize_hotkey("Cmd+Shift+Space")
    assert error == ""
    assert normalized == "<cmd>+<shift>+<space>"


def test_option_alias_and_function_key_are_supported():
    normalized, error = normalize_hotkey("Option+F12")
    assert error == ""
    assert normalized == "<alt>+<f12>"


def test_less_than_shortcut_is_parsed_without_being_truncated():
    normalized, error = normalize_hotkey("Cmd+Shift+<")

    assert error == ""
    assert normalized == "<cmd>+<shift>+<"


def test_qt_macos_modifier_swap_is_mapped_to_physical_keys():
    command = _modifier_labels(
        Qt.KeyboardModifier.ControlModifier
        | Qt.KeyboardModifier.ShiftModifier,
        macos=True,
    )
    control = _modifier_labels(
        Qt.KeyboardModifier.MetaModifier,
        macos=True,
    )

    assert command == ["Cmd", "Shift"]
    assert control == ["Ctrl"]


def test_hotkey_requires_a_modifier():
    normalized, error = normalize_hotkey("K")
    assert normalized is None
    assert "modificateur" in error


def test_macos_quit_shortcut_is_rejected():
    normalized, error = normalize_hotkey("Cmd+Q")

    assert normalized is None
    assert "réservé" in error


def test_reconfiguring_hotkeys_keeps_one_listener_alive():
    FakePersistentListener.instances = []
    service = HotkeyService(listener_factory=FakePersistentListener)

    assert service.replace_owner_bindings("principal", {"<cmd>+a": lambda: None})[0]
    listener = FakePersistentListener.instances[0]
    assert service.replace_owner_bindings("personnalisé", {"<cmd>+b": lambda: None})[0]
    assert service.replace_owner_bindings("principal", {"<cmd>+c": lambda: None})[0]

    assert len(FakePersistentListener.instances) == 1
    assert listener.start_calls == 1
    assert listener.stop_calls == 0
    assert set(listener.bindings) == {"<cmd>+b", "<cmd>+c"}

    service.close()
    assert listener.stop_calls == 1
    assert listener.join_calls == 1


def test_recheck_does_not_restart_or_stop_the_native_listener():
    FakePersistentListener.instances = []
    service = HotkeyService(listener_factory=FakePersistentListener)
    manager = HotkeyManager(HotkeySettingsStub(), service=service)
    listener = FakePersistentListener.instances[0]

    assert manager.register_hotkey() is True
    assert manager.register_hotkey() is True

    assert listener.start_calls == 1
    assert listener.stop_calls == 0


def test_conflicting_hotkey_update_is_atomic():
    FakePersistentListener.instances = []
    settings = HotkeySettingsStub()
    service = HotkeyService(listener_factory=FakePersistentListener)
    main = HotkeyManager(settings, service=service)
    custom = HotkeyManager(settings, custom_hotkey=True, service=service)
    old_custom = settings.custom

    assert custom.set_hotkey(settings.main) is False

    assert settings.custom == old_custom
    assert main.registered is True
    assert custom.registered is True
    assert "déjà utilisé" in custom.last_register_error


def test_identical_less_than_shortcuts_are_reported_as_a_conflict():
    FakePersistentListener.instances = []
    settings = HotkeySettingsStub()
    settings.main = "Cmd+Shift+<"
    settings.custom = "Cmd+Shift+<"
    service = HotkeyService(listener_factory=FakePersistentListener)
    main = HotkeyManager(settings, service=service)
    custom = HotkeyManager(settings, custom_hotkey=True, service=service)

    assert main.registered is True
    assert custom.registered is False
    assert "déjà utilisé" in custom.last_register_error


def test_listener_is_suspended_without_being_destroyed():
    FakePersistentListener.instances = []
    service = HotkeyService(listener_factory=FakePersistentListener)
    service.replace_owner_bindings("principal", {"<cmd>+a": lambda: None})
    listener = FakePersistentListener.instances[0]

    service.suspend()
    service.resume()

    assert listener.suspended is False
    assert listener.stop_calls == 0


def test_disabled_macos_event_tap_is_reenabled_in_place(monkeypatch):
    enabled = []
    listener = _PersistentGlobalHotKeys()
    listener._event_tap = object()
    event = object()

    monkeypatch.setattr(hotkey_module.sys, "platform", "darwin")
    monkeypatch.setattr(hotkey_module, "_DISABLED_EVENT_TAP_TYPES", {99})
    monkeypatch.setattr(
        hotkey_module,
        "CGEventTapEnable",
        lambda tap, state: enabled.append((tap, state)),
    )

    returned = listener._handler(None, 99, event, None)

    assert returned is event
    assert enabled == [(listener._event_tap, True)]
    assert listener.tap_reenable_count == 1
