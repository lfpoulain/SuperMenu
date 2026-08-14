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


def test_permission_button_opens_accessibility_system_pane(
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
    window.request_accessibility_permission()

    assert ("accessibility", True) in calls
    assert ("open_accessibility", True) in calls
    assert not hasattr(window, "input_monitoring_button")


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
    window._last_permission_state = False
    monkeypatch.setattr(
        main_window_module,
        "current_permission_status",
        lambda: PermissionStatus(accessibility=True),
    )

    window.refresh_permission_status()

    assert window.hotkey_manager.registered is True
    assert window.custom_hotkey_manager.registered is True
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

        def show_menu(self):
            self.calls += 1

    manager = ContextMenuStub()
    window.context_menu_manager = manager

    window.show_prompt_menu()

    assert manager.calls == 1
