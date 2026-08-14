import pytest

from src.utils.hotkey_manager import (
    HotkeyManager,
    HotkeyService,
    _MacOSGlobalHotKeys,
    _modifier_labels,
    _native_binding_signature,
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


class FakeAppKitEventAPI:
    command_flag = 1
    control_flag = 2
    option_flag = 4
    shift_flag = 8
    independent_flags_mask = 15

    def __init__(self):
        self.global_handler = None
        self.local_handler = None
        self.removed = []

    def add_global_monitor(self, handler):
        self.global_handler = handler
        return "global"

    def add_local_monitor(self, handler):
        self.local_handler = handler
        return "local"

    def remove_monitor(self, monitor):
        self.removed.append(monitor)


class FakeAppKitKeyEvent:
    def __init__(self, *, flags, key_code, characters="", repeat=False):
        self._flags = flags
        self._key_code = key_code
        self._characters = characters
        self._repeat = repeat

    def modifierFlags(self):
        return self._flags

    def keyCode(self):
        return self._key_code

    def charactersIgnoringModifiers(self):
        return self._characters

    def isARepeat(self):
        return self._repeat


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


def test_native_binding_signature_supports_literal_less_than_key():
    assert _native_binding_signature("<cmd>+<shift>+<") == (
        frozenset({"cmd", "shift"}),
        "<",
    )


def test_appkit_monitor_matches_global_space_shortcut_and_ignores_repeats():
    api = FakeAppKitEventAPI()
    listener = _MacOSGlobalHotKeys(event_api=api)
    triggered = []
    listener.replace_bindings(
        {"<cmd>+<shift>+<space>": lambda: triggered.append(True)}
    )

    listener.start()
    event = FakeAppKitKeyEvent(flags=9, key_code=0x31, repeat=True)
    api.global_handler(event)
    event._repeat = False
    api.global_handler(event)

    assert triggered == [True]
    assert listener.is_alive() is True


def test_appkit_monitor_covers_local_events_and_removes_each_monitor_once():
    api = FakeAppKitEventAPI()
    listener = _MacOSGlobalHotKeys(event_api=api)
    triggered = []
    listener.replace_bindings({"<cmd>+m": lambda: triggered.append(True)})
    listener.start()
    event = FakeAppKitKeyEvent(flags=1, key_code=0, characters="M")

    assert api.local_handler(event) is event
    listener.stop()
    listener.stop()

    assert triggered == [True]
    assert api.removed == ["global", "local"]
    assert listener.is_alive() is False


def test_appkit_monitor_suspension_keeps_monitors_installed():
    api = FakeAppKitEventAPI()
    listener = _MacOSGlobalHotKeys(event_api=api)
    triggered = []
    listener.replace_bindings({"<cmd>+a": lambda: triggered.append(True)})
    listener.start()
    listener.set_suspended(True)

    api.global_handler(
        FakeAppKitKeyEvent(flags=1, key_code=0, characters="a")
    )

    assert triggered == []
    assert listener.is_alive() is True


def test_appkit_monitor_cleans_up_after_partial_start_failure():
    api = FakeAppKitEventAPI()
    api.add_local_monitor = lambda handler: None
    listener = _MacOSGlobalHotKeys(event_api=api)

    with pytest.raises(RuntimeError, match="moniteurs clavier AppKit"):
        listener.start()

    assert api.removed == ["global"]
    assert listener.is_alive() is False


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


def test_service_restart_recreates_listener_with_existing_bindings():
    FakePersistentListener.instances = []
    service = HotkeyService(listener_factory=FakePersistentListener)
    callback = lambda: None
    service.replace_owner_bindings("principal", {"<cmd>+a": callback})
    first_listener = FakePersistentListener.instances[0]

    assert service.restart() is True

    second_listener = FakePersistentListener.instances[1]
    assert first_listener.stop_calls == 1
    assert first_listener.join_calls == 1
    assert second_listener.start_calls == 1
    assert second_listener.bindings == {"<cmd>+a": callback}
    assert service.running is True


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
