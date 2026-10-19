"""Per-prompt models with the real settings of each platform.

test_prompt_model_routing_win.py and test_prompt_model_routing_mac.py are
identical: keep them in sync.
"""

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from src.config.settings import Settings
from src.utils.context_menu import ContextMenuManager
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
    value._test_app = app
    return value


@pytest.fixture
def lmstudio_settings(settings, monkeypatch):
    """Settings whose Text server is LM Studio, protected by its own key."""
    monkeypatch.setattr(
        settings, "get_custom_endpoint_api_key", lambda: "server-secret"
    )
    settings.set_custom_endpoint("http://localhost:1234")
    settings.set_custom_endpoint_type("lmstudio")
    return settings


def test_text_and_voice_targets_survive_export_import(settings, tmp_path):
    target = {
        "provider": "custom",
        "model": "gemma",
        "device": "apple",
        "device_name": "Sur Serveur Apple (LM Link)",
        "endpoint": "http://localhost:1234",
        "endpoint_type": "lmstudio",
    }
    settings.update_prompt(
        "corriger", "Corriger", "Corrige", "Correction", model_target=target
    )
    voice = settings.add_voice_prompt(
        None, "Vocal", "Reformule", "En cours", model_target=target
    )
    path = tmp_path / "prompts.json"
    export_prompt_bundle(settings, path)
    settings.update_prompt(
        "corriger", "Corriger", "Corrige", "Correction", model_target={}
    )
    assert settings.get_prompt("corriger")["model_target"] == {}
    import_prompt_bundle(settings, path)
    # The model and its device survive; the server always comes from the Text
    # settings, so the exported file does not carry it.
    kept = {"provider": "custom", "model": "gemma", "device": "apple"}
    assert settings.get_prompt("corriger")["model_target"] == kept
    assert settings.get_voice_prompt(voice)["model_target"] == kept
    # Old callers that update only instructions must preserve the explicit route.
    settings.update_prompt("corriger", "Corriger", "Nouvelle instruction", "En cours")
    assert settings.get_prompt("corriger")["model_target"] == kept
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "localhost:1234" not in path.read_text(encoding="utf-8")
    # Nor the name of a machine: it describes the exporting server.
    assert "Serveur Apple" not in path.read_text(encoding="utf-8")
    payload["voice_prompts"][voice]["model_target"] = {
        "provider": "unknown",
        "model": "a",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        import_prompt_bundle(settings, path)
    assert settings.get_prompt("corriger")["prompt"] == "Nouvelle instruction"


class Client(QObject):
    request_started_scoped = Signal(str, bool)
    request_finished_scoped = Signal(str, str, bool, object)
    request_error_scoped = Signal(str, str)

    def __init__(self, settings):
        super().__init__()
        self.settings, self.sent, self.closed = settings, [], False

    def send_request(self, *args, **kwargs):
        self.sent.append((args, kwargs))

    def close(self):
        self.closed = True


def test_parallel_prompt_requests_keep_their_model_and_release_clients(
    settings, monkeypatch
):
    created = []

    def create(manager, config=None):
        client = Client(config or manager.settings)
        created.append(client)
        return client

    monkeypatch.setattr(ContextMenuManager, "_create_api_client", create)
    manager = ContextMenuManager(settings)
    manager.response_window.set_response = lambda *_a: None
    manager.response_window.set_loading = lambda *_a: None
    tiny = {"provider": "openai", "model": "gpt-5.6-luna"}
    large = {"provider": "openai", "model": "gpt-5.6-sol"}
    first = manager._send_request("Correct", "Text", model_target=tiny)
    second = manager._send_request("Rewrite", "Text", model_target=large)
    assert created[1].settings.get_model() == "gpt-5.6-luna"
    assert created[2].settings.get_model() == "gpt-5.6-sol"
    assert manager.api_client is created[0]
    assert manager.response_window.last_model_target == large
    manager.on_request_finished_scoped(first, "Result", False, None)
    assert created[1].closed and not created[2].closed
    assert (
        first not in manager._pending_requests and second in manager._pending_requests
    )
    manager.on_request_finished_scoped(second, "Result", False, None)
    assert created[2].closed and manager._retired_clients == []
    manager.response_window.store_request("Rewrite", "Text")
    retries = []
    monkeypatch.setattr(manager, "_send_request", lambda *a, **kw: retries.append(kw))
    manager.on_retry_requested()
    assert retries[0]["model_target"] == large
    manager.close()


# A prompt's model follows the configured Text server.


def _client(view):
    return OpenAIClient(view, api_key="test", allow_images=False)


def test_prompt_effort_never_rewrites_the_general_setting(lmstudio_settings):
    lmstudio_settings.set_model("gpt-5.6-sol")
    lmstudio_settings.set_openai_reasoning_effort("max")
    view = ModelTargetSettings(
        lmstudio_settings, {"provider": "openai", "model": "gpt-5.4"}
    )
    client = _client(view)
    try:
        data, _cleanup = client._build_request_data("Corrige", "Texte")
    finally:
        client.close()
    assert data["model"] == "gpt-5.4"
    assert data["reasoning_effort"] == "xhigh"
    assert lmstudio_settings.settings.value("openai_reasoning_effort") == "max"
    assert lmstudio_settings.get_openai_reasoning_effort() == "max"


def test_saved_prompt_follows_the_new_server(lmstudio_settings):
    picker = PromptModelChoice(lmstudio_settings)
    picker.set_target({"provider": "custom", "model": "gemma", "device": None})
    target = picker.target()
    picker.close()
    assert "endpoint" not in target
    lmstudio_settings.update_prompt(
        "corriger", "Corriger", "Corrige", "Correction", model_target=target
    )

    lmstudio_settings.set_custom_endpoint("http://192.168.1.20:11434")
    lmstudio_settings.set_custom_endpoint_type("ollama")
    stored = lmstudio_settings.get_prompt("corriger")["model_target"]
    with pytest.raises(ValueError, match="LM Studio"):
        ModelTargetSettings(lmstudio_settings, stored)
    lmstudio_settings.update_prompt(
        "corriger",
        "Corriger",
        "Corrige",
        "Correction",
        model_target={"provider": "custom", "model": "gemma"},
    )
    client = _client(settings_for_prompt(lmstudio_settings, "corriger"))
    try:
        assert client.api_url == "http://192.168.1.20:11434/api/chat"
        assert client.model == "gemma"
    finally:
        client.close()


def test_imported_foreign_server_is_dropped(lmstudio_settings, tmp_path):
    path = tmp_path / "shared-prompts.json"
    export_prompt_bundle(lmstudio_settings, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    corriger = next(iter(payload["text_prompts"]))
    payload["text_prompts"][corriger]["model_target"] = {
        "provider": "custom",
        "model": "gemma",
        "endpoint": "https://collector.example",
        "endpoint_type": "lmstudio",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    import_prompt_bundle(lmstudio_settings, path)

    assert lmstudio_settings.get_prompt(corriger)["model_target"] == {
        "provider": "custom",
        "model": "gemma",
    }
    client = _client(settings_for_prompt(lmstudio_settings, corriger))
    try:
        assert client.api_url == "http://localhost:1234/api/v1/chat"
        assert client.endpoint_api_key == "server-secret"
    finally:
        client.close()


def test_legacy_frozen_server_in_storage_is_ignored(lmstudio_settings):
    lmstudio_settings.update_prompt(
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
    client = _client(settings_for_prompt(lmstudio_settings, "corriger"))
    try:
        assert "old-host" not in client.api_url
        assert client.api_url == "http://localhost:1234/api/v1/chat"
    finally:
        client.close()


@pytest.mark.skipif(not WINDOWS, reason="Foundry Local n'existe que sur Windows")
def test_windows_registers_its_foundry_catalogue():
    from src.config.foundry_models import FOUNDRY_MODELS

    assert registered_foundry_models() == tuple(FOUNDRY_MODELS)
