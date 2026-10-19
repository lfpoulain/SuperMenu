from unittest.mock import Mock, patch

import pytest

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel

from supermenu_core.ui.configuration_shell import ConfigurationShell, close_footer
from supermenu_core.ui.settings_panel import SettingsPanel
from supermenu_core.ui.theme_manager import ThemeManager
from supermenu_core.ui.application_settings import ApplicationSettings


@pytest.mark.parametrize("work_area_height", [1392, 1040, 752])
def test_initial_window_height_fits_screen_work_area(work_area_height):
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    screen = Mock()
    screen.availableGeometry.return_value = QRect(0, 0, 1920, work_area_height)
    with patch.object(QMainWindow, "screen", return_value=screen):
        ConfigurationShell(window, window.windowIcon())
    assert window.height() + 48 <= work_area_height
    assert window.height() >= window.minimumHeight()
    if work_area_height > 1128:
        assert window.height() == 1080
    else:
        assert window.height() + 48 == work_area_height
    window.deleteLater()
    app.processEvents()


def test_changing_update_channel_allows_a_fresh_check_without_saving_theme():
    app = QApplication.instance() or QApplication([])
    settings = Mock()
    settings.get_theme.return_value = "dark"
    settings.get_update_channel.return_value = "stable"
    check = Mock()
    widget = ApplicationSettings(settings, check)
    widget.theme_combo.setCurrentIndex(widget.theme_combo.findData("light"))
    widget.channel_combo.setCurrentIndex(widget.channel_combo.findData("beta"))
    settings.set_update_channel.assert_called_once_with("beta")
    settings.set_last_update_check_date.assert_called_once_with("")
    settings.set_theme.assert_not_called()
    check.assert_not_called()
    widget.deleteLater()
    app.processEvents()


def test_scrolling_settings_keeps_only_current_page_actions_reachable():
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    shell = ConfigurationShell(window, window.windowIcon())
    panel = SettingsPanel()
    pages = panel.add_standard_pages()
    shell.tabs.addTab(panel, "Réglages")
    close = Mock()
    shell.content_layout.addLayout(close_footer(close))
    callbacks = {key: Mock() for key in pages}
    buttons = {key: panel.set_save_action(key, callback) for key, callback in callbacks.items()}
    for layout in pages.values():
        for _ in range(30):
            layout.addWidget(QLabel("Contenu à faire défiler"))
    try:
        for theme in ("dark", "light"):
            ThemeManager.apply_theme(app, theme)
            window.resize(window.minimumSize())
            window.show()
            for key in pages:
                panel.select_page(key)
                app.processEvents()
                button = buttons[key]
                assert button.isVisible()
                assert window.rect().contains(button.mapTo(window, QPoint(0, button.height())))
                assert all(other.isHidden() or not other.isVisible() for name, other in buttons.items() if name != key)
                button.click()
            assert shell.tabs.tabBar().geometry().left() == 0
        assert all(callback.call_count == 2 for callback in callbacks.values())
    finally:
        window.close()
