"""Per-prompt routing with the real settings of this platform (cluster api2)."""

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.config.settings import Settings
from supermenu_core.api.openai_client import OpenAIClient
from supermenu_core.config.model_target import (
    ModelTargetSettings,
    registered_foundry_models,
    settings_for_prompt,
)
from supermenu_core.config.prompt_transfer import (
    export_prompt_bundle,
    import_prompt_bundle,
)
from supermenu_core.ui.prompt_model import PromptModelChoice

WINDOWS = Path(__file__).parents[1].name == "win32"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    if WINDOWS:
        monkeypatch.setattr(
            "src.config.settings.os.path.expanduser", lambda _: str(tmp_path)
        )
        value = Settings()
    else:
        value = Settings(str(tmp_path / "settings.ini"))
    monkeypatch.setattr(value, "get_api_key", lambda: "")
    monkeypatch.setattr(value, "get_custom_endpoint_api_key", lambda: "server-secret")
    value.set_custom_endpoint("http://localhost:1234")
    value.set_custom_endpoint_type("lmstudio")
    value._test_app = app
    return value


def _client(view):
    return OpenAIClient(view, api_key="test", allow_images=False)


def test_prompt_effort_never_rewrites_the_general_setting(settings):
    settings.set_model("gpt-5.6-sol")
    settings.set_openai_reasoning_effort("max")
    view = ModelTargetSettings(settings, {"provider": "openai", "model": "gpt-5.4"})
    client = _client(view)
    try:
        data, _cleanup = client._build_request_data("Corrige", "Texte")
    finally:
        client.close()
    assert data["model"] == "gpt-5.4"
    assert data["reasoning_effort"] == "xhigh"
    assert settings.settings.value("openai_reasoning_effort") == "max"
    assert settings.get_openai_reasoning_effort() == "max"


def test_saved_prompt_follows_the_new_server(settings):
    picker = PromptModelChoice(settings)
    picker.set_target({"provider": "custom", "model": "gemma", "device": None})
    target = picker.target()
    picker.close()
    assert "endpoint" not in target
    settings.update_prompt(
        "corriger", "Corriger", "Corrige", "Correction", model_target=target
    )

    settings.set_custom_endpoint("http://192.168.1.20:11434")
    settings.set_custom_endpoint_type("ollama")
    stored = settings.get_prompt("corriger")["model_target"]
    with pytest.raises(ValueError, match="LM Studio"):
        ModelTargetSettings(settings, stored)
    settings.update_prompt(
        "corriger",
        "Corriger",
        "Corrige",
        "Correction",
        model_target={"provider": "custom", "model": "gemma"},
    )
    client = _client(settings_for_prompt(settings, "corriger"))
    try:
        assert client.api_url == "http://192.168.1.20:11434/api/chat"
        assert client.model == "gemma"
    finally:
        client.close()


def test_imported_foreign_server_is_dropped(settings, tmp_path):
    path = tmp_path / "shared-prompts.json"
    export_prompt_bundle(settings, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    corriger = next(iter(payload["text_prompts"]))
    payload["text_prompts"][corriger]["model_target"] = {
        "provider": "custom",
        "model": "gemma",
        "endpoint": "https://collector.example",
        "endpoint_type": "lmstudio",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    import_prompt_bundle(settings, path)

    assert settings.get_prompt(corriger)["model_target"] == {
        "provider": "custom",
        "model": "gemma",
    }
    client = _client(settings_for_prompt(settings, corriger))
    try:
        assert client.api_url == "http://localhost:1234/api/v1/chat"
        assert client.endpoint_api_key == "server-secret"
    finally:
        client.close()


def test_legacy_frozen_server_in_storage_is_ignored(settings):
    settings.update_prompt(
        "corriger",
        "Corriger",
        "Corrige",
        "Correction",
        model_target={
            "provider": "custom",
            "model": "gemma",
            "endpoint": "http://old-host:1234",
            "endpoint_type": "lmstudio",
        },
    )
    client = _client(settings_for_prompt(settings, "corriger"))
    try:
        assert "old-host" not in client.api_url
        assert client.api_url == "http://localhost:1234/api/v1/chat"
    finally:
        client.close()


@pytest.mark.skipif(not WINDOWS, reason="Foundry Local n'existe que sur Windows")
def test_windows_registers_its_foundry_catalogue():
    from src.config.foundry_models import FOUNDRY_MODELS

    assert registered_foundry_models() == tuple(FOUNDRY_MODELS)
