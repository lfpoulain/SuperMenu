import sys
from types import ModuleType, SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from src.config.settings import Settings
from src.main import SuperMenu
from src.ui import main_window as main_window_module
from src.ui.main_window import MainWindow


class FakeMainWindow:
    def __init__(self, visible):
        self.visible = visible
        self.hide_calls = 0

    def isVisible(self):
        return self.visible

    def hide(self):
        self.visible = False
        self.hide_calls += 1


class FakeContextMenuManager:
    def __init__(self):
        self.show_calls = 0

    def show_menu(self):
        self.show_calls += 1


def _application_stub(main_window):
    return SimpleNamespace(
        main_window=main_window,
        context_menu_manager=FakeContextMenuManager(),
        hotkey_manager=SimpleNamespace(hotkey="Cmd+Shift+Space"),
    )


def test_global_menu_hides_visible_configuration_window_first():
    application = _application_stub(FakeMainWindow(visible=True))

    SuperMenu.show_context_menu(application)

    assert application.main_window.hide_calls == 1
    assert application.context_menu_manager.show_calls == 1


def test_global_menu_does_not_touch_already_hidden_configuration_window():
    application = _application_stub(FakeMainWindow(visible=False))

    SuperMenu.show_context_menu(application)

    assert application.main_window.hide_calls == 0
    assert application.context_menu_manager.show_calls == 1


@pytest.fixture
def configuration_window(tmp_path):
    QApplication.instance() or QApplication([])
    window = MainWindow(Settings(config_path=str(tmp_path / "settings.ini")))
    yield window
    window._quitting = True
    window.close()
    window.deleteLater()


def test_menu_bar_uses_only_the_native_status_item(
    configuration_window,
    monkeypatch,
):
    """The shipped path, not the abandoned QSystemTrayIcon one, is tested."""

    created = []

    class FakeNativeStatusItem:
        def __init__(self, icon_path, actions, parent=None):
            self.icon_path = icon_path
            self.actions = actions
            self.parent = parent
            self.hidden = False
            created.append(self)

        def hide(self):
            self.hidden = True

    fake_module = ModuleType("src.ui.status_item")
    fake_module.NativeStatusItem = FakeNativeStatusItem
    monkeypatch.setitem(sys.modules, "src.ui.status_item", fake_module)
    monkeypatch.setattr(
        main_window_module, "sys", SimpleNamespace(platform="darwin")
    )
    window = configuration_window
    calls = []
    window.show_main_window = lambda: calls.append("open")
    window.quit_application = lambda: calls.append("quit")

    assert window.setup_tray_icon() is True
    assert window.setup_tray_icon() is True

    assert len(created) == 1
    status_item = created[0]
    assert window.tray_icon is status_item
    assert status_item.parent is window
    labels = [entry and entry[0] for entry in status_item.actions]
    assert labels == [
        "Ouvrir SuperMenu",
        "Afficher le menu des prompts",
        "Dicter du texte…",
        "Afficher la dernière réponse",
        "Vérifier les mises à jour",
        "Autorisations macOS…",
        None,
        "Quitter",
    ]
    actions = dict(entry for entry in status_item.actions if entry)
    actions["Ouvrir SuperMenu"]()
    actions["Quitter"]()
    assert calls == ["open", "quit"]


def test_menu_bar_is_reported_unavailable_outside_macos(
    configuration_window,
    monkeypatch,
):
    monkeypatch.setattr(
        main_window_module, "sys", SimpleNamespace(platform="win32")
    )

    assert configuration_window.setup_tray_icon() is False
    assert configuration_window.tray_icon is None


def test_menu_bar_failure_falls_back_to_the_configuration_window(
    configuration_window,
    monkeypatch,
):
    class BrokenNativeStatusItem:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("AppKit indisponible")

    fake_module = ModuleType("src.ui.status_item")
    fake_module.NativeStatusItem = BrokenNativeStatusItem
    monkeypatch.setitem(sys.modules, "src.ui.status_item", fake_module)
    monkeypatch.setattr(
        main_window_module, "sys", SimpleNamespace(platform="darwin")
    )

    assert configuration_window.setup_tray_icon() is False
    assert configuration_window.tray_icon is None


def test_menu_bar_import_failure_falls_back_to_the_configuration_window(
    configuration_window,
    monkeypatch,
):
    # None in sys.modules makes the import itself raise ImportError, as a
    # missing or broken AppKit binding would: it must not escape startup.
    monkeypatch.setitem(sys.modules, "src.ui.status_item", None)
    monkeypatch.setattr(
        main_window_module, "sys", SimpleNamespace(platform="darwin")
    )

    assert configuration_window.setup_tray_icon() is False
    assert configuration_window.tray_icon is None
