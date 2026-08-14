import pytest
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest

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


def test_first_permission_click_shows_only_native_consent(
    window,
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        main_window_module,
        "request_accessibility_permission",
        lambda: calls.append("request") or True,
    )
    monkeypatch.setattr(
        main_window_module,
        "open_accessibility_settings",
        lambda: calls.append(("open_accessibility", True)) or True,
    )
    window.request_accessibility_permission()

    assert calls == ["request"]
    assert window.accessibility_button.text() == "Ouvrir les réglages…"
    assert not hasattr(window, "input_monitoring_button")


def test_second_permission_click_opens_accessibility_settings(
    window,
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        main_window_module,
        "request_accessibility_permission",
        lambda: calls.append("request") or True,
    )
    monkeypatch.setattr(
        main_window_module,
        "open_accessibility_settings",
        lambda: calls.append("settings") or True,
    )

    window.request_accessibility_permission()
    window.request_accessibility_permission()

    assert calls == ["request", "settings"]


def test_permission_click_opens_settings_when_native_prompt_is_unavailable(
    window,
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        main_window_module,
        "request_accessibility_permission",
        lambda: calls.append("request") or False,
    )
    monkeypatch.setattr(
        main_window_module,
        "open_accessibility_settings",
        lambda: calls.append("settings") or True,
    )

    window.request_accessibility_permission()

    assert calls == ["request", "settings"]


def test_granted_permissions_reload_hotkeys(window, monkeypatch):
    class ServiceStub:
        running = True

        def __init__(self):
            self.restart_calls = 0

        def restart(self):
            self.restart_calls += 1
            return True

    class HotkeyManagerStub:
        registered = False
        last_register_error = ""

        def register_hotkey(self):
            self.registered = True
            return True

    class PromptManagerStub:
        def refresh_hotkeys(self):
            return True, {}

    service = ServiceStub()
    window.hotkey_manager = HotkeyManagerStub()
    window.custom_hotkey_manager = HotkeyManagerStub()
    window.prompt_hotkey_manager = PromptManagerStub()
    window.hotkey_manager.service = service
    window.custom_hotkey_manager.service = service
    window.prompt_hotkey_manager.service = service
    window._last_permission_state = False
    monkeypatch.setattr(
        main_window_module,
        "current_permission_status",
        lambda: PermissionStatus(accessibility=True),
    )

    window.refresh_permission_status()

    assert window.hotkey_manager.registered is True
    assert window.custom_hotkey_manager.registered is True
    assert service.restart_calls == 1
    assert "actifs" in window.hotkey_service_status.text()


def test_custom_endpoint_switch_uses_windows_style_on_off_display(window):
    window.use_custom_endpoint.setChecked(False)
    assert window.openai_group.isHidden() is False
    assert window.custom_group.isHidden() is True

    window.use_custom_endpoint.setChecked(True)
    assert window.openai_group.isHidden() is True
    assert window.custom_group.isHidden() is False


def test_lmstudio_catalog_updates_native_reasoning_options(window, monkeypatch):
    endpoint_index = window.endpoint_type.findData("lmstudio")
    window.endpoint_type.setCurrentIndex(endpoint_index)
    window.custom_model.setCurrentText("reasoning-model")

    class WorkerStub:
        endpoint = window.custom_endpoint.text().strip()
        endpoint_type = "lmstudio"

    window._custom_models_worker = WorkerStub()
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)

    window._on_custom_models_loaded(
        [
            {
                "id": "reasoning-model",
                "identifiers": ["reasoning-model"],
                "reasoning_supported": True,
                "reasoning_options": ["off", "on", "future_tier"],
                "reasoning_default": "on",
            }
        ]
    )

    assert [
        window.custom_reasoning.itemData(index)
        for index in range(window.custom_reasoning.count())
    ] == ["off", "on", "future_tier"]


def test_recheck_attempts_hotkeys_even_when_permission_api_reports_false(
    window,
    monkeypatch,
):
    class HotkeyManagerStub:
        registered = False
        last_register_error = ""

        def register_hotkey(self):
            self.registered = True
            return True

    window.hotkey_manager = HotkeyManagerStub()
    window.custom_hotkey_manager = HotkeyManagerStub()
    monkeypatch.setattr(
        main_window_module,
        "current_permission_status",
        lambda: PermissionStatus(accessibility=False),
    )

    window.refresh_permission_status(force_reload=True)

    assert window.hotkey_manager.registered is True
    assert window.custom_hotkey_manager.registered is True
    assert "actifs" in window.hotkey_service_status.text()


def test_hotkey_recorder_is_async_and_keeps_main_window_open(window, qt_app):
    class ServiceStub:
        def __init__(self):
            self.suspended = False

        def suspend(self):
            self.suspended = True

        def resume(self):
            self.suspended = False

    class ManagerStub:
        last_register_error = ""

        def __init__(self):
            self.service = ServiceStub()
            self.saved = None

        def set_hotkey(self, hotkey):
            self.saved = hotkey
            return True

    manager = ManagerStub()
    window.hotkey_manager = manager
    window.show()
    qt_app.processEvents()

    window.record_main_hotkey()
    dialog = window._hotkey_dialog

    assert dialog is not None
    assert manager.service.suspended is True
    dialog.recorded_hotkey = "Cmd+Option+K"
    dialog.accept()
    qt_app.processEvents()

    assert manager.saved == "Cmd+Option+K"
    assert window.isVisible() is True
    assert window._hotkey_dialog is None
    for _attempt in range(40):
        if not manager.service.suspended:
            break
        QTest.qWait(50)
    assert manager.service.suspended is False


def test_prompt_menu_can_be_opened_without_global_hotkey(window):
    class ContextMenuStub:
        def __init__(self):
            self.calls = 0

        def show_menu(self, *, from_ui=False):
            self.calls += 1
            self.from_ui = from_ui

    manager = ContextMenuStub()
    window.context_menu_manager = manager

    window.show_prompt_menu()

    # SuperMenu is the frontmost application here, so the menu has to reuse the
    # target remembered before the configuration window took focus.
    assert manager.from_ui is True

    assert manager.calls == 1
