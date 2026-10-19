"""Copy and paste keystrokes: layout-independent keys, terminals, remote
sessions and modifiers still held after a hotkey."""

import logging
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pynput.keyboard import Key
from PySide6.QtWidgets import QApplication

from src.utils import context_menu as context_menu_module
from src.utils.clipboard_config import (
    CLIPBOARD_REMOTE_RESTORE_DELAY,
    CLIPBOARD_RESTORE_DELAY,
)
from src.utils.context_menu import ContextMenuManager
from src.utils.logger import logger as supermenu_logger
from src.utils.text_inserter import VK_C, VK_V, TextInserter
from src.utils.window_target import PasteTarget


SECRET = "Mot de passe très confidentiel 4242"


def _app():
    return QApplication.instance() or QApplication([])


class FakeSettings:
    def get_ai_provider(self):
        return "openai"

    def get_api_key(self):
        return "key"

    def get_use_custom_endpoint(self):
        return False

    def get_custom_endpoint(self):
        return ""

    def get_custom_endpoint_type(self):
        return "ollama"

    def get_custom_model(self):
        return ""

    def get_model(self):
        return "gpt-5.6-sol"

    def get_reasoning_effort(self):
        return "none"

    def get_prompts(self):
        return {}

    def get_voice_prompts(self):
        return {}

    def sync(self):
        pass


class RecordingKeyboard:
    def __init__(self, on_press=None):
        self.pressed = []
        self.released = []
        self.on_press = on_press

    def press(self, key):
        self.pressed.append(key)
        if self.on_press:
            self.on_press(key)

    def release(self, key):
        self.released.append(key)


def _selection_environment(monkeypatch, manager, *, window_class, copied, pid=4242, unreadable=False):
    """Fake the foreground window, the clipboard and the keyboard."""
    clipboard = {"text": "contenu de l'utilisateur"}
    env = SimpleNamespace(writes=[], restores=[], snapshots=0)

    def capture_snapshot():
        env.snapshots += 1
        return "snapshot"

    def set_text(text, transient=False):
        env.writes.append((text, transient))
        clipboard["text"] = text
        return True

    def on_press(key):
        if copied is not None and key in (VK_C, Key.insert):
            clipboard["text"] = copied

    monkeypatch.setattr("src.utils.context_menu.ClipboardManager.capture_snapshot", capture_snapshot)
    monkeypatch.setattr("src.utils.context_menu.ClipboardManager.set_clipboard_text_safe", set_text)
    monkeypatch.setattr(
        "src.utils.context_menu.ClipboardManager.get_clipboard_text_safe",
        lambda: None if unreadable else clipboard["text"],
    )
    monkeypatch.setattr(
        "src.utils.context_menu.ClipboardManager.restore_if_unchanged",
        lambda snapshot, expected: env.restores.append((snapshot, expected)),
    )
    monkeypatch.setattr("src.utils.context_menu.win32gui.GetForegroundWindow", lambda: 100)
    monkeypatch.setattr("src.utils.context_menu.win32gui.GetClassName", lambda _hwnd: window_class)
    monkeypatch.setattr(
        "src.utils.context_menu.win32process.GetWindowThreadProcessId",
        lambda _hwnd: (1, pid),
    )
    monkeypatch.setattr(context_menu_module.time, "sleep", lambda _seconds: None)
    manager.keyboard = RecordingKeyboard(on_press)
    env.keyboard = manager.keyboard
    return env


def test_copy_uses_layout_independent_virtual_key(monkeypatch):
    _app()
    manager = ContextMenuManager(FakeSettings())
    env = _selection_environment(monkeypatch, manager, window_class="Chrome_WidgetWin_1", copied="sélection")

    assert manager._try_get_selected_text() == "sélection"

    assert env.keyboard.pressed == [Key.ctrl, VK_C]
    assert VK_C.vk == 0x43 and VK_C.char is None
    # The sentinel is an internal write kept out of the clipboard history.
    assert env.writes and env.writes[0][1] is True
    assert env.restores == [("snapshot", "sélection")]
    manager.close()


def test_copy_and_paste_virtual_keys_never_become_unicode_packets():
    for key, vk in ((VK_C, 0x43), (VK_V, 0x56)):
        parameters = key._parameters(True)
        assert parameters["wVk"] == vk
        # KEYEVENTF_UNICODE (0x4) is what non-Latin layouts used to produce.
        assert not parameters["dwFlags"] & 0x4


def test_supermenu_in_front_never_touches_the_clipboard(monkeypatch):
    _app()
    manager = ContextMenuManager(FakeSettings())
    env = _selection_environment(
        monkeypatch, manager, window_class="Qt", copied="ignored", pid=os.getpid()
    )

    assert manager._try_get_selected_text() == ""

    assert env.snapshots == 0
    assert env.writes == [] and env.restores == []
    assert env.keyboard.pressed == []
    manager.close()


def test_standalone_terminals_receive_ctrl_insert_but_never_ctrl_c(monkeypatch):
    _app()
    manager = ContextMenuManager(FakeSettings())
    for window_class in sorted(context_menu_module.TERMINAL_WINDOW_CLASSES):
        env = _selection_environment(
            monkeypatch, manager, window_class=window_class, copied=None, unreadable=True
        )
        assert manager._try_get_selected_text() == ""
        assert env.keyboard.pressed == [Key.ctrl, Key.insert], window_class
        assert VK_C not in env.keyboard.pressed
    manager.close()


def test_console_hosts_keep_their_copy_shortcuts(monkeypatch):
    _app()
    manager = ContextMenuManager(FakeSettings())
    env = _selection_environment(
        monkeypatch, manager, window_class="ConsoleWindowClass", copied="dir", unreadable=False
    )
    assert manager._try_get_selected_text() == "dir"
    assert env.keyboard.pressed == [Key.ctrl, Key.insert]

    env = _selection_environment(
        monkeypatch, manager, window_class="CASCADIA_HOSTING_WINDOW_CLASS", copied=None, unreadable=True
    )
    assert manager._try_get_selected_text() == ""
    # Fallback only when the clipboard could not be read, now with VK_C.
    assert env.keyboard.pressed == [Key.ctrl, Key.insert, Key.ctrl, Key.shift, VK_C]
    manager.close()


class SafeTarget:
    def __init__(self, remote=False):
        self.remote = remote

    def activate_and_verify(self):
        return True

    def is_remote_session(self):
        return self.remote


def _inserter_environment(monkeypatch):
    env = SimpleNamespace(writes=[], sleeps=[], restores=[])

    def set_text(text, transient=False):
        env.writes.append((text, transient))
        return True

    monkeypatch.setattr("src.utils.text_inserter.ClipboardManager.capture_snapshot", lambda: "snapshot")
    monkeypatch.setattr("src.utils.text_inserter.ClipboardManager.set_clipboard_text_safe", set_text)
    monkeypatch.setattr(
        "src.utils.text_inserter.ClipboardManager.restore_if_unchanged",
        lambda snapshot, expected: env.restores.append((snapshot, expected)),
    )
    monkeypatch.setattr("src.utils.text_inserter.time.sleep", env.sleeps.append)
    inserter = TextInserter()
    inserter.keyboard = RecordingKeyboard()
    return inserter, env


def test_paste_uses_layout_independent_virtual_key(monkeypatch):
    inserter, env = _inserter_environment(monkeypatch)

    assert inserter.insert_text("réponse", target=SafeTarget()) is True

    assert inserter.keyboard.pressed == [Key.ctrl, VK_V]
    assert VK_V.vk == 0x56 and VK_V.char is None
    assert env.writes == [("réponse", True)]
    assert env.sleeps[-1] == CLIPBOARD_RESTORE_DELAY
    assert env.restores == [("snapshot", "réponse")]


def test_remote_desktop_targets_wait_longer_before_restoring(monkeypatch):
    inserter, env = _inserter_environment(monkeypatch)

    assert inserter.insert_text("réponse", target=SafeTarget(remote=True)) is True

    assert env.sleeps[-1] == CLIPBOARD_REMOTE_RESTORE_DELAY
    assert env.restores == [("snapshot", "réponse")]


def test_paste_target_recognises_remote_session_windows(monkeypatch):
    target = PasteTarget(foreground_hwnd=10, process_id=20)
    for window_class, expected in (
        ("TscShellContainerClass", True),
        ("Transparent Windows Client", True),
        ("Notepad", False),
    ):
        monkeypatch.setattr("src.utils.window_target.win32gui.GetClassName", lambda _hwnd, value=window_class: value)
        assert target.is_remote_session() is expected

    def broken(_hwnd):
        raise OSError("invalid window")

    monkeypatch.setattr("src.utils.window_target.win32gui.GetClassName", broken)
    assert target.is_remote_session() is False


def _hotkey_environment(monkeypatch, manager, target):
    state = {"held": True, "target": target}
    env = SimpleNamespace(queued=[], calls=[], indicators=[], state=state)
    monkeypatch.setattr("src.utils.context_menu.PasteTarget.capture", lambda: state["target"])
    monkeypatch.setattr(
        "src.utils.context_menu.win32api.GetAsyncKeyState",
        lambda _key: 0x8000 if state["held"] else 0,
    )
    monkeypatch.setattr(
        "src.utils.context_menu.QTimer.singleShot",
        lambda _delay, callback: env.queued.append(callback),
    )
    monkeypatch.setattr(
        "src.utils.context_menu.SimpleLoadingIndicator.show_near_cursor",
        lambda message, duration_ms=None: env.indicators.append(message),
    )
    monkeypatch.setattr(
        manager, "_try_get_selected_text", lambda: env.calls.append("copy") or "texte"
    )
    return env


def test_custom_mode_waits_for_modifier_release_before_copying(monkeypatch):
    _app()
    manager = ContextMenuManager(FakeSettings())
    target = SimpleNamespace(process_id=4242)
    env = _hotkey_environment(monkeypatch, manager, target)
    monkeypatch.setattr(
        manager,
        "_handle_godmode_action",
        lambda text, target=None: env.calls.append(("custom", text, target)),
    )

    manager.show_custom_mode()
    # Ctrl+Alt+M is still held: copying now would send Ctrl+Alt+C.
    assert env.calls == [] and len(env.queued) == 1

    env.state["held"] = False
    env.queued.pop()()
    assert env.calls == ["copy", ("custom", "texte", target)]
    manager.close()


def test_menu_waits_for_modifier_release_and_aborts_if_focus_changes(monkeypatch):
    _app()
    manager = ContextMenuManager(FakeSettings())
    target = SimpleNamespace(process_id=4242)
    env = _hotkey_environment(monkeypatch, manager, target)

    def fake_exec(menu):
        env.calls.append("menu")
        manager._finish_menu_session(menu)
        return None

    monkeypatch.setattr(manager, "_exec_menu", fake_exec)

    manager.show_menu()
    assert env.calls == [] and len(env.queued) == 1
    env.state["held"] = False
    env.queued.pop()()
    assert env.calls == ["copy", "menu"]
    assert manager._is_menu_open is False

    env.calls.clear()
    env.state["held"] = True
    manager.show_menu()
    env.state.update(held=False, target=SimpleNamespace(process_id=7))
    env.queued.pop()()
    assert env.calls == []
    manager.close()


def test_hotkey_without_held_modifiers_still_runs_immediately(monkeypatch):
    _app()
    manager = ContextMenuManager(FakeSettings())
    target = SimpleNamespace(process_id=4242)
    env = _hotkey_environment(monkeypatch, manager, target)
    env.state["held"] = False
    monkeypatch.setattr(
        manager,
        "_handle_godmode_action",
        lambda text, target=None: env.calls.append("custom"),
    )

    manager.show_custom_mode()

    assert env.queued == []
    assert env.calls == ["copy", "custom"]
    manager.close()


def test_held_modifiers_time_out_without_copying(monkeypatch):
    _app()
    manager = ContextMenuManager(FakeSettings())
    env = _hotkey_environment(monkeypatch, manager, SimpleNamespace(process_id=4242))
    monkeypatch.setattr(context_menu_module, "MODIFIER_RELEASE_TIMEOUT", 0)

    manager.show_custom_mode()

    assert env.calls == [] and env.queued == []
    assert env.indicators == ["Relâchez les touches puis réessayez"]
    manager.close()


VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12


def _hold_only(monkeypatch, *keys):
    monkeypatch.setattr(
        "src.utils.context_menu.win32api.GetAsyncKeyState",
        lambda key: 0x8000 if key in keys else 0,
    )


def test_menu_opens_on_key_press_while_ctrl_is_still_held(monkeypatch):
    # Default hotkey Ctrl+²: a held Ctrl leaves the synthesized Ctrl+C intact.
    _app()
    manager = ContextMenuManager(FakeSettings())
    env = _hotkey_environment(monkeypatch, manager, SimpleNamespace(process_id=4242))
    _hold_only(monkeypatch, VK_CONTROL)

    def fake_exec(menu):
        env.calls.append("menu")
        manager._finish_menu_session(menu)
        return None

    monkeypatch.setattr(manager, "_exec_menu", fake_exec)

    manager.show_menu()

    assert env.queued == []
    assert env.calls == ["copy", "menu"]
    assert env.indicators == []
    manager.close()


def test_custom_mode_waits_for_alt_but_not_for_ctrl(monkeypatch):
    _app()
    manager = ContextMenuManager(FakeSettings())
    target = SimpleNamespace(process_id=4242)
    env = _hotkey_environment(monkeypatch, manager, target)
    monkeypatch.setattr(
        manager,
        "_handle_godmode_action",
        lambda text, target=None: env.calls.append(("custom", text, target)),
    )
    _hold_only(monkeypatch, VK_CONTROL, VK_MENU)

    manager.show_custom_mode()
    assert env.calls == [] and len(env.queued) == 1

    # Alt released, Ctrl still held: Ctrl+C can be sent.
    _hold_only(monkeypatch, VK_CONTROL)
    env.queued.pop()()
    assert env.calls == ["copy", ("custom", "texte", target)]
    manager.close()


def test_prompt_hotkey_still_waits_for_every_modifier(monkeypatch):
    _app()
    manager = ContextMenuManager(FakeSettings())
    env = _hotkey_environment(monkeypatch, manager, SimpleNamespace(process_id=4242))
    monkeypatch.setattr(manager, "_handle_menu_action", lambda *a, **kw: env.calls.append("run"))
    _hold_only(monkeypatch, VK_CONTROL)

    manager.run_prompt_hotkey("corriger")

    assert env.calls == [] and len(env.queued) == 1
    manager.close()


def test_immediate_hotkey_does_not_compare_two_captures(monkeypatch):
    # Without a wait the menu opens as before, even if two captures differ.
    _app()
    manager = ContextMenuManager(FakeSettings())
    env = _hotkey_environment(monkeypatch, manager, None)
    env.state["held"] = False
    monkeypatch.setattr("src.utils.context_menu.PasteTarget.capture", lambda: object())
    monkeypatch.setattr(
        manager,
        "_handle_godmode_action",
        lambda text, target=None: env.calls.append("custom"),
    )

    manager.show_custom_mode()

    assert env.calls == ["copy", "custom"]
    manager.close()


def test_hotkey_dropped_after_a_focus_change_is_announced(monkeypatch):
    _app()
    manager = ContextMenuManager(FakeSettings())
    env = _hotkey_environment(monkeypatch, manager, SimpleNamespace(process_id=4242))
    _hold_only(monkeypatch, VK_SHIFT)

    manager.show_menu()
    env.state["target"] = SimpleNamespace(process_id=7)
    _hold_only(monkeypatch)
    env.queued.pop()()

    assert env.calls == []
    assert env.indicators == ["Raccourci ignoré : la fenêtre active a changé"]
    manager.close()


def test_conemu_keeps_ctrl_c_because_ctrl_insert_is_not_its_copy_key(monkeypatch):
    _app()
    manager = ContextMenuManager(FakeSettings())
    assert "VirtualConsoleClass" not in context_menu_module.TERMINAL_WINDOW_CLASSES
    env = _selection_environment(
        monkeypatch, manager, window_class="VirtualConsoleClass", copied="sélection"
    )

    assert manager._try_get_selected_text() == "sélection"

    assert env.keyboard.pressed == [Key.ctrl, VK_C]
    manager.close()


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def test_debug_logs_never_contain_selection_prompt_or_transcription(monkeypatch, tmp_path):
    _app()
    handler = _ListHandler()
    monkeypatch.setattr(supermenu_logger, "handlers", [handler])
    previous_level = supermenu_logger.level
    # setLevel clears the logger cache, unlike a plain attribute assignment.
    supermenu_logger.setLevel(logging.DEBUG)
    try:
        _run_flows_with_secret_content(monkeypatch, tmp_path)
    finally:
        supermenu_logger.setLevel(previous_level)

    assert any("caractères" in message for message in handler.messages)
    for expected in (
        "Texte copié avec succès",
        "Texte sélectionné:",
        "Texte sélectionné inclus",
        "Transcription vocale reçue (",
        "Transcription vocale reçue pour prompt personnalisé",
        "Prompt saisi",
    ):
        assert any(message.startswith(expected) for message in handler.messages), expected
    leaked = [message for message in handler.messages if "confidentiel" in message]
    assert leaked == []


def _run_flows_with_secret_content(monkeypatch, tmp_path):
    settings = FakeSettings()
    settings.get_prompt = lambda _prompt_id: {
        "prompt": "Corrige :",
        "status": "Correction",
        "insert_directly": True,
    }
    settings.get_voice_prompt = lambda _prompt_id: {
        "name": "Vocal",
        "prompt": "Réponds :",
        "status": "Réponse",
        "insert_directly": True,
        "include_selected_text": True,
        "prompt_order": "prompt_transcription_selected",
    }
    settings.get_screenshot_capture_mode = lambda: "fullscreen"
    manager = ContextMenuManager(settings)
    manager.response_window.present = lambda: None
    monkeypatch.setattr(manager, "_send_request", lambda *args, **kwargs: None)

    # Selection read from the clipboard.
    _selection_environment(monkeypatch, manager, window_class="Edit", copied=SECRET + " sélection")
    assert manager._try_get_selected_text() == SECRET + " sélection"

    # Prompt run on that selection.
    manager._handle_menu_action("corriger", selected_text=SECRET + " menu", target=object())

    # Voice prompt including the selection, then its transcription.
    callbacks = []
    monkeypatch.setattr(
        manager,
        "_create_voice_recognition",
        lambda callback=None: callbacks.append(callback) or SimpleNamespace(
            start_voice_recognition=lambda: None, cleanup=lambda: None
        ),
    )
    monkeypatch.setattr(manager, "_try_get_selected_text", lambda: SECRET + " vocal")
    manager._handle_voice_prompt_action("vocal", target=object())
    callbacks[-1](SECRET + " transcription")

    # Custom voice prompt.
    monkeypatch.setattr(
        "src.ui.prompt_dialog.PromptDialog.show_prompt_dialog",
        lambda _text: "Prompt personnalisé",
    )
    manager._handle_voice_godmode_action(target=object())
    callbacks[-1](SECRET + " personnalisé")

    # Prompt typed for a screenshot.
    screenshot = tmp_path / "capture.png"
    screenshot.write_bytes(b"\x89PNG\r\n")

    class FakePromptDialog:
        def __init__(self, *_args):
            pass

        def set_image_path(self, _path):
            pass

        def exec(self):
            return True

        def get_prompt(self):
            return SECRET + " capture"

    monkeypatch.setattr("src.utils.context_menu.capture_screen", lambda _mode: str(screenshot))
    monkeypatch.setattr("src.ui.prompt_dialog.PromptDialog", FakePromptDialog)
    monkeypatch.setattr("src.utils.context_menu.PasteTarget.capture", lambda: None)
    manager._handle_screenshot_action()
    manager.close()
