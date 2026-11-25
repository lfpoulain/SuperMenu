"""Regressions for the Windows fixes: recorder, capture, Foundry queue, tray."""

import os
import sys
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from src.api.foundry_client import FoundryService  # noqa: E402
from src.config import settings as settings_module  # noqa: E402
from src.config.settings import Settings  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402
from src.utils.context_menu import ContextMenuManager  # noqa: E402
from src.utils.hotkey_manager import (  # noqa: E402
    HotkeyRecorderDialog,
    _parse_hotkey_to_win32,
)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(app, tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings_module.os.path, "expanduser", lambda _path: str(tmp_path)
    )
    monkeypatch.setattr("supermenu_core.ui.speech_settings.microphones", lambda: [])
    instance = Settings()
    yield instance
    instance.settings.clear()
    instance.settings.sync()


# Shortcut recorder -------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "modifiers", "text", "expected"),
    [
        # What Windows really delivers with Ctrl held: a control character.
        (Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier, "\x0b", "Ctrl+K"),
        (Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier, "\x01", "Ctrl+A"),
        (
            Qt.Key.Key_K,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
            "\x0b",
            "Ctrl+Shift+K",
        ),
        (Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier, "\t", "Ctrl+I"),
    ],
)
def test_recorder_accepts_ctrl_letter_combinations(app, key, modifiers, text, expected):
    dialog = HotkeyRecorderDialog()
    try:
        dialog.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text))

        assert dialog.recorded_hotkey == expected
        assert dialog.ok_button.isEnabled()
        # And the recorded text is one RegisterHotKey can bind.
        assert _parse_hotkey_to_win32(expected) is not None
    finally:
        dialog.deleteLater()


def test_recorder_still_uses_the_typed_character_when_there_is_one(app):
    dialog = HotkeyRecorderDialog()
    try:
        dialog.keyPressEvent(
            QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_M,
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier,
                "m",
            )
        )
        assert dialog.recorded_hotkey == "Ctrl+Alt+m"
    finally:
        dialog.deleteLater()


# Screen capture ----------------------------------------------------------


def test_capture_is_ignored_while_a_supermenu_dialog_is_open(
    settings, monkeypatch, app
):
    manager = ContextMenuManager(settings)
    captures = []
    monkeypatch.setattr(
        "src.utils.context_menu.capture_screen", lambda mode: captures.append(mode)
    )
    dialog = QDialog()
    dialog.setModal(True)
    dialog.show()
    try:
        assert QApplication.activeModalWidget() is dialog

        manager._handle_screenshot_action()

        # The dialog (a prompt being typed) is neither hidden nor cancelled.
        assert captures == []
        assert dialog.isVisible()
    finally:
        dialog.close()
        dialog.deleteLater()
        manager.close()


def test_a_second_capture_cannot_start_inside_the_first(settings, monkeypatch, app):
    manager = ContextMenuManager(settings)
    captures = []

    def nested_capture(mode):
        captures.append(mode)
        # The shortcut pressed again while the first capture is running.
        manager._handle_screenshot_action()
        return None

    monkeypatch.setattr("src.utils.context_menu.capture_screen", nested_capture)
    monkeypatch.setattr("src.utils.context_menu.PasteTarget.capture", lambda: None)
    try:
        manager._handle_screenshot_action()

        assert len(captures) == 1
        # The guard is released for the next capture, even after a failure.
        assert manager._screen_capture_running is False
        manager._handle_screenshot_action()
        assert len(captures) == 2
    finally:
        manager.close()


# Foundry queue -----------------------------------------------------------

WORKER = """
import json, sys
for line in sys.stdin:
    r = json.loads(line)
    print(json.dumps({'id': r['id'], 'result': {'text': r.get('content', 'ok')}}), flush=True)
"""


def _wait_until(app, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert predicate()


def test_unencodable_request_fails_at_once_and_frees_the_queue(app, tmp_path):
    worker = tmp_path / "worker.py"
    worker.write_text(WORKER, encoding="utf-8")
    service = FoundryService(command=(sys.executable, [str(worker)]))
    events = SimpleNamespace(errors=[], results=[])
    service.failed.connect(lambda *args: events.errors.append(args))
    service.completed.connect(lambda *args: events.results.append(args))
    try:
        # Half an emoji, as a truncated copy leaves it on the clipboard.
        service.submit("generate", request_id="broken", content="abc \ud83d def")
        service.submit("generate", request_id="next", content="texte valide")

        _wait_until(app, lambda: events.errors and events.results)

        assert [error[0] for error in events.errors] == ["broken"]
        assert "caractère invalide" in events.errors[0][1]
        # The following request is served instead of waiting ten minutes.
        assert [result[0] for result in events.results] == ["next"]
    finally:
        service.close()


# Main window -------------------------------------------------------------


def test_tray_entry_restores_a_minimized_window(settings, app):
    window = MainWindow(settings)
    try:
        if window.tray_icon is None or window.tray_icon.contextMenu() is None:
            pytest.skip("Zone de notification indisponible sur cet hôte")
        action = next(
            action
            for action in window.tray_icon.contextMenu().actions()
            if action.text() == "Ouvrir SuperMenu"
        )
        window.showMinimized()
        assert window.isMinimized()

        action.trigger()

        assert not window.isMinimized()
        assert window.isVisible()
    finally:
        window.close()
        window.deleteLater()


def test_manual_update_check_during_a_silent_one_is_acknowledged(
    settings, monkeypatch, app
):
    window = MainWindow(settings)
    try:
        window._update_check_worker = SimpleNamespace(isRunning=lambda: True)
        window._update_check_silent = True
        window._update_loading = None

        window.check_for_updates(silent=False)

        # The running check now reports its result, with a visible indicator.
        assert window._update_check_silent is False
        assert window._update_loading is not None
        window._update_loading.close()
        window._update_loading = None
    finally:
        window._update_check_worker = None
        window.close()
        window.deleteLater()


def test_refused_credentials_are_reported_and_nothing_is_saved(
    settings, monkeypatch, app
):
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _parent, title, text: warnings.append(title)
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda *_args: pytest.fail("confirmation")
    )

    def refused(*_args):
        raise OSError("Credential Manager indisponible")

    window = MainWindow(settings)
    try:
        window.ai_provider_combo.setCurrentIndex(
            window.ai_provider_combo.findData("anthropic")
        )
        monkeypatch.setattr(settings, "set_anthropic_api_key", refused)

        window.save_api_key()

        assert warnings == ["Clés non enregistrées"]
        # The provider was not switched to an engine whose key is missing.
        assert settings.get_ai_provider() == "openai"
    finally:
        window.close()
        window.deleteLater()
