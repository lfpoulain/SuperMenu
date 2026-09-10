from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from supermenu_core.ui.configuration_shell import ConfigurationShell
from src.config.settings import Settings
from src.ui.main_window import MainWindow


@pytest.fixture
def window(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QMessageBox, "information", Mock())
    monkeypatch.setattr("supermenu_core.ui.speech_settings.microphones", lambda: [])
    manager = Mock()
    instance = MainWindow(Settings(str(tmp_path / "settings.ini")), context_menu_manager=manager)
    yield instance
    instance._quitting = True
    instance.close()
    app.processEvents()


def test_text_save_does_not_save_prompt_or_validate_voice(window):
    window.speech_settings.save = Mock(return_value=False)
    previous = window.settings.get_prompts()
    window.prompt_instruction.setPlainText("Brouillon non enregistré")
    window.model_combo.setCurrentIndex(1)
    window.tabs.setCurrentIndex(2)
    window.settings_panel.select_page("text")
    window.text_save_button.click()
    assert window.settings.get_model() == window.model_combo.currentText()
    assert window.settings.get_prompts() == previous
    window.speech_settings.save.assert_not_called()
    window.context_menu_manager.update_client_config.assert_called_once()


def test_appearance_apply_is_independent_of_invalid_text_settings(window):
    window.provider_combo.setCurrentIndex(window.provider_combo.findData("custom"))
    window.custom_endpoint.clear()
    window.speech_settings.save = Mock(return_value=False)
    window.theme_combo.setCurrentIndex(window.theme_combo.findData("light"))
    provider = window.settings.get_ai_provider()
    window.app_save_button.click()
    assert window.settings.get_theme() == "light"
    assert window.settings.get_ai_provider() == provider
    window.speech_settings.save.assert_not_called()
    window.context_menu_manager.update_client_config.assert_not_called()


def test_dictation_footer_saves_without_touching_text_drafts(window):
    window.speech_settings.provider_combo.setCurrentIndex(window.speech_settings.provider_combo.findData("apple"))
    window.provider_combo.setCurrentIndex(window.provider_combo.findData("custom"))
    window.custom_endpoint.clear()
    previous = window.settings.get_ai_provider()
    window.speech_settings.save_button.click()
    assert window.settings.get_speech_provider() == "apple"
    assert window.settings.get_ai_provider() == previous
    window.context_menu_manager.update_client_config.assert_called_once()


def test_configuration_uses_shared_shell_and_visible_voice_actions(window):
    assert isinstance(window.centralWidget(), ConfigurationShell)
    assert window.shell.content_layout.count() == 3
    window.tabs.setCurrentIndex(2)
    window.settings_panel.select_page("voice")
    window.resize(window.minimumSize())
    window.show()
    QApplication.processEvents()
    for button in (window.speech_settings.save_button, window.speech_settings.test_button):
        assert button.isVisible()
        assert button.window() is window
