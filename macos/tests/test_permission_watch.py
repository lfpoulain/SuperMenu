"""Permission watch of the configuration window and messages for refused
prompt shortcuts."""

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from src.config.settings import Settings
from src.ui import main_window as main_window_module
from src.ui.main_window import MainWindow
from src.utils.permissions import PermissionStatus


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt_app, tmp_path):
    instance = MainWindow(Settings(config_path=str(tmp_path / "settings.ini")))
    yield instance
    instance._quitting = True
    instance.close()
    instance.deleteLater()


class _ServiceStub:
    running = True

    def __init__(self):
        self.restart_calls = 0

    def restart(self):
        self.restart_calls += 1
        return True


class _HotkeyManagerStub:
    registered = True
    last_register_error = ""

    def __init__(self, service):
        self.service = service

    def register_hotkey(self):
        return True


def _set_permission(monkeypatch, **status):
    monkeypatch.setattr(
        main_window_module,
        "current_permission_status",
        lambda: PermissionStatus(**status),
    )


def test_permission_watch_survives_closing_the_window_until_granted(
    window,
    qt_app,
    monkeypatch,
):
    service = _ServiceStub()
    window.hotkey_manager = _HotkeyManagerStub(service)
    window.custom_hotkey_manager = _HotkeyManagerStub(service)
    _set_permission(monkeypatch, accessibility=False)
    window.refresh_permission_status()
    window.show()
    qt_app.processEvents()
    assert window._permission_timer.isActive() is True

    # The user closes the window, then grants Accessibility in System Settings.
    window.close()
    qt_app.processEvents()
    assert window.isVisible() is False
    assert window._permission_timer.isActive() is True

    window._permission_timer.timeout.emit()
    assert service.restart_calls == 0
    assert window._permission_timer.isActive() is True

    _set_permission(monkeypatch, accessibility=True)
    window._permission_timer.timeout.emit()

    assert service.restart_calls == 1
    assert window._permission_timer.isActive() is False


def test_hidden_window_stops_polling_once_accessibility_is_granted(
    window,
    qt_app,
    monkeypatch,
):
    _set_permission(monkeypatch, accessibility=True)
    window.show()
    qt_app.processEvents()

    window.hide()
    qt_app.processEvents()

    assert window._permission_timer.isActive() is False


def test_unreadable_permission_state_does_not_poll_while_hidden(
    window,
    qt_app,
    monkeypatch,
):
    _set_permission(
        monkeypatch,
        accessibility=False,
        accessibility_check_available=False,
    )
    window.show()
    qt_app.processEvents()

    window.hide()
    qt_app.processEvents()

    assert window._permission_timer.isActive() is False


def test_refused_prompt_shortcut_names_the_prompt_to_fix(window, monkeypatch):
    class PromptManagerStub:
        def validate_prompts(self, prompts):
            return False, {"legacy": "Ajoutez Cmd ou Ctrl"}

        def refresh_hotkeys(self):
            return True, {}

    prompts = window.settings.get_prompts()
    prompts["legacy"] = dict(
        next(iter(prompts.values())), name="Ancien prompt", hotkey="Shift+K"
    )
    window.settings.set_prompts(prompts)
    window._reload_prompts()
    window.prompt_hotkey_manager = PromptManagerStub()
    warnings = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )

    assert window.save_current_prompt(show_confirmation=False) is False

    assert warnings == [
        ("Raccourci invalide", "« Ancien prompt » : Ajoutez Cmd ou Ctrl")
    ]


def test_registration_error_is_shown_without_a_prompt_name():
    assert (
        MainWindow._prompt_hotkey_error({"registration": "Service fermé"}, {})
        == "Service fermé"
    )
    assert MainWindow._prompt_hotkey_error({}, {}) == "Conflit de raccourci"
