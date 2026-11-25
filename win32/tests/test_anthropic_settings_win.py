"""Anthropic as a text engine in the Windows settings and client factory."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from src.config import settings as settings_module  # noqa: E402
from src.config.settings import Settings  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402
from src.utils.context_menu import ContextMenuManager  # noqa: E402
from supermenu_core.config.anthropic_models import DEFAULT_ANTHROPIC_MODEL  # noqa: E402
from supermenu_core.config.settings_contract import contract_violations  # noqa: E402

KEY = "sk-ant-test-key-0123456789"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        settings_module.os.path, "expanduser", lambda _path: str(tmp_path)
    )
    monkeypatch.setattr("supermenu_core.ui.speech_settings.microphones", lambda: [])
    instance = Settings()
    yield instance
    instance.settings.clear()
    instance.settings.sync()


def test_anthropic_key_has_its_own_keyring_entry(settings):
    settings.set_api_key("openai-secret")
    settings.set_anthropic_api_key(f"  {KEY}  ")

    assert settings.get_anthropic_api_key() == KEY
    assert settings.get_api_key() == "openai-secret"
    # Never written to the INI file next to the other settings.
    assert KEY not in "".join(
        str(settings.settings.value(name)) for name in settings.settings.allKeys()
    )


def test_provider_model_and_effort_are_persisted_and_reset(settings):
    assert contract_violations(settings) == []
    assert settings.get_anthropic_model() == DEFAULT_ANTHROPIC_MODEL
    assert settings.get_anthropic_reasoning_effort() == "medium"

    settings.set_ai_provider("anthropic")
    settings.set_anthropic_model("claude-haiku-5-5")
    settings.set_anthropic_reasoning_effort("high")

    assert settings.get_ai_provider() == "anthropic"
    assert settings.get_use_custom_endpoint() is False
    assert settings.get_reasoning_effort() == "high"
    settings.set_reasoning_effort("max")
    assert settings.get_anthropic_reasoning_effort() == "max"
    # The OpenAI effort keeps its own value.
    assert settings.get_openai_reasoning_effort() == "medium"

    settings.reset_to_defaults()
    assert settings.get_ai_provider() == "openai"
    assert settings.get_anthropic_model() == DEFAULT_ANTHROPIC_MODEL
    assert settings.get_anthropic_reasoning_effort() == "medium"


def test_settings_page_saves_anthropic_and_switches_the_client(settings, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _parent, title, text: warnings.append(text)
    )
    manager = ContextMenuManager(settings)
    window = MainWindow(settings, context_menu_manager=manager)
    try:
        assert window.anthropic_group.isHidden()
        window.ai_provider_combo.setCurrentIndex(
            window.ai_provider_combo.findData("anthropic")
        )
        assert not window.anthropic_group.isHidden()
        assert window.openai_group.isHidden() and window.custom_group.isHidden()

        group = window.anthropic_group
        group.model_combo.setCurrentIndex(
            group.model_combo.findData("claude-sonnet-5-5")
        )
        group.reasoning_combo.setCurrentText("low")

        # An obviously incomplete key is refused before anything is stored.
        group.api_key_input.setText("sk-ant court")
        window.save_api_key()
        assert len(warnings) == 1
        assert settings.get_ai_provider() == "openai"

        group.api_key_input.setText(KEY)
        window.save_api_key()
        assert settings.get_ai_provider() == "anthropic"
        assert settings.get_anthropic_api_key() == KEY
        assert settings.get_anthropic_model() == "claude-sonnet-5-5"
        assert settings.get_anthropic_reasoning_effort() == "low"

        client = manager.api_client
        assert client.use_anthropic_api is True
        assert client.model == "claude-sonnet-5-5"
        assert client._build_headers()["x-api-key"] == KEY
        assert "Authorization" not in client._build_headers()
    finally:
        manager.close()
        window.close()
        window.deleteLater()


def test_openai_model_list_is_the_wide_catalogue(settings):
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
            window.reasoning_effort_combo.itemText(index)
            for index in range(window.reasoning_effort_combo.count())
        ]
        # This model always reasons: "none" is not offered.
        assert efforts == ["low", "medium", "high", "xhigh", "max"]
    finally:
        window.close()
        window.deleteLater()
