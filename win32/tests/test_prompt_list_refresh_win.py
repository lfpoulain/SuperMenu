"""Prompt library refreshes in the Windows main window."""

import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication

from src.config import settings as settings_module
from src.config.settings import Settings
from src.ui import main_window
from src.ui import response_window as response_window_module
from src.ui.main_window import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def _prompt(name, position, text="Corrige ce texte."):
    return {
        "name": name,
        "prompt": text,
        "status": "En cours",
        "insert_directly": False,
        "position": position,
        "hotkey": "",
    }


@pytest.fixture
def window(monkeypatch, tmp_path):
    _app()
    monkeypatch.setattr(settings_module.os.path, "expanduser", lambda _path: str(tmp_path))
    monkeypatch.setattr(Settings, "get_api_key", lambda _self: "")
    monkeypatch.setattr(Settings, "get_custom_endpoint_api_key", lambda _self: "")
    monkeypatch.setattr("supermenu_core.ui.speech_settings.microphones", lambda: [])
    for name in ("information", "warning"):
        monkeypatch.setattr(main_window.QMessageBox, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        main_window.QMessageBox, "question", lambda *_args, **_kwargs: main_window.QMessageBox.Yes
    )
    created = MainWindow(Settings())
    yield created
    created.hide()
    created.deleteLater()


def _sidebar(window):
    return [
        window.prompt_order_list.item(row).data(Qt.UserRole)
        for row in range(window.prompt_order_list.count())
    ]


def _combo(window):
    return [window.prompt_combo.itemData(row) for row in range(window.prompt_combo.count())]


def test_import_rebuilds_the_visible_prompt_list(monkeypatch, window):
    assert len(_sidebar(window)) > 1

    def fake_import(_path):
        window.settings.set_prompts({"alpha": _prompt("Alpha", 10)})
        return True, "ok"

    monkeypatch.setattr(window.settings, "import_prompts", fake_import)
    monkeypatch.setattr(
        main_window.QFileDialog, "getOpenFileName", lambda *_args, **_kwargs: ("prompts.json", "")
    )

    window.import_all_prompts()

    # The hidden combo was refreshed but the sidebar kept the old prompts.
    assert _combo(window) == ["alpha"]
    assert _sidebar(window) == ["alpha"]
    assert window.prompt_order_list.currentRow() == 0
    assert window.prompt_name_input.text() == "Alpha"


def test_reset_rebuilds_the_visible_prompt_list(window):
    window.settings.add_prompt("perso", "Perso", "Texte", "En cours", False, 999, hotkey="")
    window.populate_prompt_combo()
    window.populate_prompt_order_list()
    assert "perso" in _sidebar(window)

    window.reset_all_settings()

    assert "perso" not in _sidebar(window)
    assert _sidebar(window) == _combo(window)


def test_prompt_text_is_loaded_as_plain_text(window):
    text = "<b>Ne pas interpréter</b>\nDeuxième ligne"
    window.settings.set_prompts({"alpha": _prompt("Alpha", 10, text)})
    window.populate_prompt_combo()

    window.load_prompt(0)

    assert window.prompt_text_input.toPlainText() == text


def test_previous_library_can_be_restored_from_the_text_prompts(monkeypatch, window):
    calls = []
    monkeypatch.setattr(
        main_window,
        "restore_previous_library",
        lambda parent, settings, refreshed: calls.append((parent, settings, refreshed)),
    )

    window.restore_previous_prompt_library()

    assert calls == [(window, window.settings, window._prompts_restored)]


def test_restore_previous_action_is_wired_when_the_shared_actions_offer_it(monkeypatch, tmp_path):
    from supermenu_core.ui import page_actions

    class PromptActionsWithPrevious(page_actions.PromptActions):
        restore_previous_requested = Signal()

    _app()
    monkeypatch.setattr(page_actions, "PromptActions", PromptActionsWithPrevious)
    monkeypatch.setattr(settings_module.os.path, "expanduser", lambda _path: str(tmp_path))
    monkeypatch.setattr(Settings, "get_api_key", lambda _self: "")
    monkeypatch.setattr(Settings, "get_custom_endpoint_api_key", lambda _self: "")
    monkeypatch.setattr("supermenu_core.ui.speech_settings.microphones", lambda: [])
    calls = []
    monkeypatch.setattr(
        main_window,
        "restore_previous_library",
        lambda parent, settings, refreshed: calls.append(parent),
    )
    created = MainWindow(Settings())
    try:
        created.prompt_actions.restore_previous_requested.emit()
        assert calls == [created]
    finally:
        created.hide()
        created.deleteLater()


def test_response_window_foreground_failure_reaches_the_log_file(monkeypatch):
    _app()
    window = response_window_module.ResponseWindow()
    logged = []

    def broken_is_window(_hwnd):
        raise OSError("fenêtre introuvable")

    monkeypatch.setattr(response_window_module.win32gui, "IsWindow", broken_is_window)
    monkeypatch.setattr(
        response_window_module, "log", lambda message, level=logging.INFO: logged.append((message, level))
    )

    window._reinforce_foreground_win32()

    assert len(logged) == 1
    assert "fenêtre introuvable" in logged[0][0]
    assert logged[0][1] == logging.WARNING
