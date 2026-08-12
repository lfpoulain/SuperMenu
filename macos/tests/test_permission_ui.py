import pytest
from PySide6.QtWidgets import QApplication

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


def test_permission_buttons_open_the_matching_system_pane(
    window,
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        main_window_module,
        "accessibility_is_trusted",
        lambda prompt=False: calls.append(("accessibility", prompt)) or False,
    )
    monkeypatch.setattr(
        main_window_module,
        "open_accessibility_settings",
        lambda: calls.append(("open_accessibility", True)) or True,
    )
    monkeypatch.setattr(
        main_window_module,
        "input_monitoring_is_trusted",
        lambda prompt=False: calls.append(("input", prompt)) or False,
    )
    monkeypatch.setattr(
        main_window_module,
        "open_input_monitoring_settings",
        lambda: calls.append(("open_input", True)) or True,
    )

    window.request_accessibility_permission()
    window.request_input_monitoring_permission()

    assert ("accessibility", True) in calls
    assert ("open_accessibility", True) in calls
    assert ("input", True) in calls
    assert ("open_input", True) in calls


def test_granted_permissions_reload_hotkeys(window, monkeypatch):
    class HotkeyManagerStub:
        registered = False
        last_register_error = ""

        def register_hotkey(self):
            self.registered = True
            return True

    class PromptManagerStub:
        def refresh_hotkeys(self):
            return True, {}

    window.hotkey_manager = HotkeyManagerStub()
    window.custom_hotkey_manager = HotkeyManagerStub()
    window.prompt_hotkey_manager = PromptManagerStub()
    window._last_permission_state = (False, False)
    monkeypatch.setattr(
        main_window_module,
        "current_permission_status",
        lambda: PermissionStatus(True, True),
    )

    window.refresh_permission_status()

    assert window.hotkey_manager.registered is True
    assert window.custom_hotkey_manager.registered is True
    assert "actifs" in window.hotkey_service_status.text()

