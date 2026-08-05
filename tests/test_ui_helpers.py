import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from pynput.keyboard import Key
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from src.ui.response_window import ResponseWindow
from src.utils import hotkey_manager as hotkey_manager_module
from src.utils.context_menu import ContextMenuManager
from src.utils.hotkey_manager import (
    HotkeyRecorderDialog,
    PromptHotkeyManager,
    _Win32HotkeyRegistry,
    _parse_hotkey_to_win32,
)
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
        return "gpt-5.6-sol"

    def get_prompts(self):
        return {"broken": {"position": 0}}

    def get_voice_prompts(self):
        return {}

    def get_microphone_index(self):
        return None

    def get_transcription_languages(self):
        return "fr, en"

    def get_transcription_prompt(self):
        return "Contexte technique"

    def get_transcription_keywords(self):
        return "SuperMenu, PySide6"


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


def test_response_window_write_queues_final_answer_even_when_thinking_visible():
    _app()
    window = ResponseWindow()
    window.set_response("<think>raisonnement interne</think>\n\nreponse finale")
    window.toggle_thinking_visibility()
    window._paste_text = lambda: None

    window.write_response()

    assert window._pending_paste_text == "reponse finale"


def test_response_window_combines_qt_and_win32_presentation():
    _app()
    window = ResponseWindow()
    calls = []
    window._raise_to_front_qt = lambda: calls.append("qt")
    window._reinforce_foreground_win32 = lambda: calls.append("win32")

    window._raise_to_front()

    assert calls == ["qt", "win32"]


def test_standalone_response_clears_retry_and_keeps_write_action():
    _app()
    window = ResponseWindow()
    window.store_request("ancien prompt", "ancien contenu")

    window.set_standalone_response(
        "Texte dicté",
        title="SuperMenu - Transcription",
    )

    assert window.response_text.toPlainText() == "Texte dicté"
    assert window.final_response == "Texte dicté"
    assert window.last_prompt is None
    assert window.last_content is None
    assert window.retry_button.isEnabled() is False
    assert window.copy_button.isEnabled() is True
    assert window.write_button.isEnabled() is True


def test_context_menu_always_presents_response_window():
    _app()
    settings = FakeMenuSettings()
    manager = ContextMenuManager(settings)
    calls = []
    manager.response_window.present = lambda: calls.append("present")

    manager._present_response_window()
    assert calls == ["present"]


def test_context_menu_passes_transcription_settings(monkeypatch):
    _app()
    settings = FakeMenuSettings()
    manager = ContextMenuManager(settings)
    captured = {}

    class FakeVoiceRecognition:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "src.utils.context_menu.VoiceRecognition",
        FakeVoiceRecognition,
    )

    callback = lambda _text: None
    target = object()
    manager._create_voice_recognition(
        callback=callback,
        target=target,
    )

    assert captured["transcription_languages"] == "fr, en"
    assert captured["transcription_prompt"] == "Contexte technique"
    assert captured["transcription_keywords"] == "SuperMenu, PySide6"
    assert captured["callback"] is callback
    assert captured["target"] is target


def test_write_by_voice_opens_response_window_instead_of_direct_paste(
    monkeypatch,
):
    _app()
    settings = FakeMenuSettings()
    manager = ContextMenuManager(settings)
    target = object()
    captured = {}
    presented = []

    class FakeVoiceRecognition:
        def start_voice_recognition(self, insert_text=True):
            captured["insert_text"] = insert_text

    def fake_create_voice_recognition(**kwargs):
        captured.update(kwargs)
        return FakeVoiceRecognition()

    monkeypatch.setattr(
        manager,
        "_create_voice_recognition",
        fake_create_voice_recognition,
    )
    monkeypatch.setattr(manager, "stop_voice_recognition", lambda: None)
    manager.response_window.present = lambda: presented.append("present")

    manager._handle_voice_action(target=target)
    captured["callback"]("Texte dicté")

    assert captured["insert_text"] is False
    assert "fenêtre de réponse" in captured["callback_success_message"]
    assert manager.response_window.response_text.toPlainText() == "Texte dicté"
    assert manager.response_window.paste_target is target
    assert presented == ["present"]


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


@pytest.mark.parametrize(
    ("hotkey", "expected_modifiers", "expected_vk"),
    [
        ("Ctrl+F1", 0x0002, 0x70),
        ("Alt+Shift+F12", 0x0001 | 0x0004, 0x7B),
        ("Ctrl+Alt+F24", 0x0002 | 0x0001, 0x87),
    ],
)
def test_function_hotkeys_are_parsed(hotkey, expected_modifiers, expected_vk):
    modifiers, vk, error = _parse_hotkey_to_win32(hotkey)

    assert error == ""
    assert modifiers == expected_modifiers
    assert vk == expected_vk


def test_function_hotkeys_reject_out_of_range_keys():
    modifiers, vk, error = _parse_hotkey_to_win32("Ctrl+F25")

    assert modifiers is None
    assert vk is None
    assert "non support" in error


def test_hotkey_recorder_captures_function_key():
    _app()
    dialog = HotkeyRecorderDialog()
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_F12,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier,
    )

    dialog.keyPressEvent(event)

    assert dialog.recorded_hotkey == "Ctrl+Alt+F12"
    assert dialog.ok_button.isEnabled()


def test_prompt_hotkey_manager_registers_and_emits_each_prompt(monkeypatch):
    _app()

    class Settings:
        def get_prompts(self):
            return {
                "corriger": {
                    "position": 10,
                    "hotkey": "Ctrl+Alt+1",
                },
                "traduire": {
                    "position": 20,
                    "hotkey": "Ctrl+Alt+2",
                },
            }

    callbacks = {}
    unregistered = []

    def fake_register(_modifiers, _vk, callback):
        hotkey_id = len(callbacks) + 1
        callbacks[hotkey_id] = callback
        return hotkey_id, ""

    monkeypatch.setattr(
        hotkey_manager_module._REGISTRY,
        "register",
        fake_register,
    )
    monkeypatch.setattr(
        hotkey_manager_module._REGISTRY,
        "unregister",
        unregistered.append,
    )
    manager = PromptHotkeyManager(Settings())
    triggered = []
    manager.prompt_hotkey_triggered.connect(triggered.append)

    callbacks[1]()
    callbacks[2]()

    assert triggered == ["corriger", "traduire"]
    manager.close()
    assert unregistered == [1, 2]


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
