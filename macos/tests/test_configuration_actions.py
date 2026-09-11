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


def test_text_reset_requires_confirmation_and_preserves_other_prompts(window, monkeypatch):
    from PySide6.QtCore import Qt

    prompt_id = window.prompt_list.currentItem().data(Qt.ItemDataRole.UserRole)
    prompts = window.settings.get_prompts()
    prompts[prompt_id].update(prompt="Instructions modifiées", position=1234, hotkey="Cmd+Shift+K")
    window.settings.set_prompts(prompts)
    window._reload_prompts(prompt_id)
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.No)
    window.prompt_actions.reset_button.click()
    assert window.settings.get_prompts() == prompts
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    window.prompt_actions.reset_button.click()
    expected = {**window.settings.default_prompts[prompt_id], "position": 1234}
    actual = window.settings.get_prompt(prompt_id)
    assert actual["prompt"] == expected["prompt"]
    assert actual["position"] == 1234
    assert actual["hotkey"] == expected.get("hotkey", "")
    assert window.prompt_instruction.toPlainText() == expected["prompt"]
    remaining = window.settings.get_prompts()
    remaining.pop(prompt_id)
    prompts.pop(prompt_id)
    assert remaining == prompts


def test_custom_text_prompt_has_no_reset_to_defaults(window):
    prompt_id = window.settings.add_prompt(None, "Personnel", "Mon instruction", "Travail")
    window._reload_prompts(prompt_id)
    assert not window.prompt_actions.reset_button.isEnabled()


def test_prompt_editor_saves_reasoning_independently(window):
    window._reload_prompts("corriger")
    window.text_prompt_form.reasoning.set_mode("off")
    assert window.save_current_prompt()
    assert window.settings.get_prompt("corriger")["reasoning_mode"] == "off"
    window.voice_prompt_editor.reload("resumer_vocal")
    window.voice_prompt_editor.reasoning.set_mode("on")
    assert window.voice_prompt_editor.save()
    assert window.settings.get_voice_prompt("resumer_vocal")["reasoning_mode"] == "on"
    window._reload_prompts("corriger")
    assert window.text_prompt_form.reasoning.currentData() == "off"
