"""Anthropic as a text engine in the macOS settings and client factory."""

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from src.config.settings import Settings
from src.ui.main_window import MainWindow
from src.utils.context_menu import ContextMenuManager
from supermenu_core.config.anthropic_models import DEFAULT_ANTHROPIC_MODEL
from supermenu_core.config.settings_contract import contract_violations

KEY = "sk-ant-test-key-0123456789"


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def test_provider_key_model_and_effort_are_persisted(tmp_path):
    path = str(tmp_path / "settings.ini")
    settings = Settings(path)

    assert contract_violations(settings) == []
    assert settings.get_anthropic_api_key() == ""
    assert settings.get_anthropic_model() == DEFAULT_ANTHROPIC_MODEL
    assert settings.get_anthropic_reasoning_effort() == "medium"

    settings.set_api_key("openai-secret")
    settings.set_anthropic_api_key(f"  {KEY}  ")
    settings.set_ai_provider("anthropic")
    settings.set_anthropic_model("claude-haiku-5-5")
    settings.set_anthropic_reasoning_effort("high")
    settings.sync()

    reopened = Settings(path)
    assert reopened.get_ai_provider() == "anthropic"
    assert reopened.get_use_custom_endpoint() is False
    assert reopened.get_anthropic_api_key() == KEY
    assert reopened.get_api_key() == "openai-secret"
    assert reopened.get_anthropic_model() == "claude-haiku-5-5"
    assert reopened.get_reasoning_effort() == "high"
    # The OpenAI effort keeps its own value.
    assert reopened.get_openai_reasoning_effort() == "medium"

    with pytest.raises(ValueError):
        reopened.set_ai_provider("inconnu")


def test_settings_page_saves_anthropic_and_switches_the_client(
    qt_app, tmp_path, monkeypatch
):
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _parent, title, text: warnings.append(text)
    )
    settings = Settings(str(tmp_path / "settings.ini"))
    manager = ContextMenuManager(settings)
    window = MainWindow(settings, context_menu_manager=manager)
    try:
        assert window.anthropic_group.isHidden()
        window.provider_combo.setCurrentIndex(
            window.provider_combo.findData("anthropic")
        )
        assert not window.anthropic_group.isHidden()
        assert window.openai_group.isHidden() and window.custom_group.isHidden()
        assert window.apple_group.isHidden()

        group = window.anthropic_group
        group.model_combo.setCurrentIndex(
            group.model_combo.findData("claude-sonnet-5-5")
        )
        group.reasoning_combo.setCurrentText("low")

        # An obviously incomplete key is refused before anything is stored.
        group.api_key_input.setText("sk-ant court")
        assert window.save_text_settings() is False
        assert len(warnings) == 1
        assert settings.get_ai_provider() == "openai"

        group.api_key_input.setText(KEY)
        assert window.save_text_settings() is True
        assert settings.get_ai_provider() == "anthropic"
        assert settings.get_anthropic_api_key() == KEY
        assert settings.get_anthropic_model() == "claude-sonnet-5-5"
        assert settings.get_anthropic_reasoning_effort() == "low"

        client = manager.api_client
        assert client.use_anthropic_api is True
        # The macOS client stays text only, whatever the engine.
        assert client.allow_images is False
        assert client.model == "claude-sonnet-5-5"
        assert client._build_headers()["x-api-key"] == KEY
        assert "Authorization" not in client._build_headers()
    finally:
        manager.close()
        window._quitting = True
        window.close()
        window.deleteLater()


def test_openai_model_list_is_the_wide_catalogue(qt_app, tmp_path):
    settings = Settings(str(tmp_path / "settings.ini"))
    window = MainWindow(settings)
    try:
        models = [
            window.model_combo.itemText(index)
            for index in range(window.model_combo.count())
        ]
        assert models[:4] == [
            "gpt-6.2-astra",
            "gpt-6.2-sol",
            "gpt-6.1-terra",
            "gpt-6-luna",
        ]
        assert {"gpt-5.6-sol", "gpt-5.5", "gpt-5.4-mini"} <= set(models)
        # The saved model stays selected in the longer list.
        assert window.model_combo.currentText() == settings.get_model()

        window.model_combo.setCurrentText("gpt-6.2-sol")
        efforts = [
            window.reasoning_combo.itemText(index)
            for index in range(window.reasoning_combo.count())
        ]
        # This model always reasons: "none" is not offered.
        assert efforts == ["low", "medium", "high", "xhigh", "max"]
    finally:
        window._quitting = True
        window.close()
        window.deleteLater()
