import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from pynput.keyboard import Key
from PySide6.QtWidgets import QApplication

from src.ui.response_window import ResponseWindow
from src.utils.context_menu import ContextMenuManager
from src.utils.hotkey_manager import _Win32HotkeyRegistry
from src.utils.safe_dialogs import SafeDialogs
from src.utils.text_inserter import TextInserter


def _app():
    return QApplication.instance() or QApplication([])


class FakeMenuSettings:
    def get_api_key(self):
        return ""

    def get_use_custom_endpoint(self):
        return False

    def get_model(self):
        return "gpt-5.2"

    def get_prompts(self):
        return {"broken": {"position": 0}}

    def get_voice_prompts(self):
        return {}


def test_safe_dialog_methods_are_qt_slots():
    _app()
    instance = SafeDialogs.get_instance()
    meta = instance.metaObject()

    assert meta.indexOfMethod("_show_information_impl(QString,QString)") != -1
    assert meta.indexOfMethod("_show_warning_impl(QString,QString)") != -1
    assert meta.indexOfMethod("_show_critical_impl(QString,QString)") != -1


def test_response_window_masks_thinking_when_no_final_answer():
    _app()
    window = ResponseWindow()

    window.set_response("<think>raisonnement seulement</think>")

    assert "Aucune reponse finale" in window.response_text.toPlainText()
    window.toggle_thinking_visibility()
    assert "raisonnement seulement" in window.response_text.toPlainText()


def test_context_menu_releases_lock_when_build_fails():
    _app()
    manager = ContextMenuManager(FakeMenuSettings())
    manager._try_get_selected_text = lambda: "texte"

    manager.show_menu()

    assert manager._is_menu_open is False
    assert manager._active_menu is None
    assert manager._menu_watchdog.isActive() is False


def test_hotkey_dispatch_is_queued_to_qt_event_loop():
    app = _app()
    calls = []
    registry = _Win32HotkeyRegistry()
    registry._callbacks[7] = lambda: calls.append("called")

    registry.dispatch(7)

    assert calls == []
    for _ in range(5):
        app.processEvents()
        if calls:
            break
    assert calls == ["called"]


def test_keyboard_shortcut_releases_pressed_keys_on_failure():
    class FailingKeyboard:
        def __init__(self):
            self.released = []

        def press(self, key):
            if key == "v":
                raise RuntimeError("press failed")

        def release(self, key):
            self.released.append(key)

    inserter = TextInserter()
    inserter.keyboard = FailingKeyboard()

    with pytest.raises(RuntimeError):
        inserter._press_keyboard_shortcut(Key.ctrl, "v")

    assert inserter.keyboard.released == [Key.ctrl]
