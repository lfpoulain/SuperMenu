"""Per-prompt model choices follow the configured server and never rewrite
the general settings."""

import threading
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from supermenu_core.api import openai_client as client_module
from supermenu_core.api.openai_client import OpenAIClient
from supermenu_core.config import model_target as model_target_module
from supermenu_core.config.model_target import (
    ModelTargetSettings,
    ModelTargetSettingsMixin,
    register_foundry_models,
    registered_foundry_models,
    settings_for_prompt,
    without_server,
)
from supermenu_core.ui import prompt_model as prompt_model_module
from supermenu_core.ui.model_catalog import populate_model_catalog
from supermenu_core.ui.prompt_model import PromptModelChoice


class Memory:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.writes = []

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.writes.append((key, value))
        self.values[key] = value


class Settings(ModelTargetSettingsMixin):
    """Text settings whose server can change while prompts keep their target."""

    def __init__(self, endpoint="http://localhost:1234", endpoint_type="lmstudio"):
        self.settings = Memory()
        self.endpoint = endpoint
        self.endpoint_type = endpoint_type
        self.key = "server-secret"
        self.threads = []

    def get_model(self):
        return "gpt-5.6-sol"

    def get_use_custom_endpoint(self):
        return False

    def get_custom_model(self):
        return "gemma"

    def get_custom_endpoint(self):
        return self.endpoint

    def get_custom_endpoint_type(self):
        return self.endpoint_type

    def get_custom_endpoint_api_key(self):
        return self.key

    def get_custom_reasoning_effort(self):
        self.threads.append(threading.current_thread())
        return "none"

    def get_openai_reasoning_effort(self, model=None):
        # Same behaviour as the Windows getter: it persists its normalization.
        from supermenu_core.config.openai_models import (
            normalize_openai_model,
            normalize_reasoning_effort,
        )

        self.threads.append(threading.current_thread())
        model = normalize_openai_model(model or self.get_model())
        effort = self.settings.value("openai_reasoning_effort", "medium")
        normalized = normalize_reasoning_effort(model, effort)
        if normalized != effort:
            self.settings.setValue("openai_reasoning_effort", normalized)
        return normalized

    def get_reasoning_effort(self):
        return self.get_openai_reasoning_effort()


class PCSettings(Settings):
    def get_foundry_model(self):
        return "qwen3.5-4b"


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch):
    client_module.clear_capabilities_cache()
    monkeypatch.setattr(model_target_module, "_foundry_models", ())
    yield
    client_module.clear_capabilities_cache()


def _picker_target(settings, saved=None, model="gemma"):
    picker = PromptModelChoice(settings)
    picker.set_target(saved or {})
    if not saved:
        picker.provider.setCurrentIndex(picker.provider.findData("custom"))
        picker.model.setCurrentText(model)
    target = picker.target()
    picker.close()
    return target


# The configured server is a reference, not a frozen URL.


def test_prompt_target_follows_a_server_change(app):
    settings = Settings()
    target = _picker_target(settings)
    assert target == {"provider": "custom", "model": "gemma"}

    settings.endpoint = "http://192.168.1.20:11434"
    settings.endpoint_type = "ollama"
    settings.key = "new-secret"
    # Reopening and saving the prompt keeps following the configured server.
    assert _picker_target(settings, target) == target

    view = ModelTargetSettings(settings, target)
    assert view.get_custom_endpoint() == "http://192.168.1.20:11434"
    assert view.get_custom_endpoint_type() == "ollama"
    assert view.get_custom_endpoint_api_key() == "new-secret"
    client = OpenAIClient(view, allow_images=False)
    try:
        assert client.api_url == "http://192.168.1.20:11434/api/chat"
        assert client.endpoint_api_key == "new-secret"
        assert client.model == "gemma"
    finally:
        client.close()


def test_frozen_endpoint_of_an_older_version_is_migrated(app, monkeypatch):
    settings = Settings(endpoint="http://new-host:1234")
    legacy = {
        "provider": "custom",
        "model": "gemma",
        "device": "apple",
        "device_name": "Sur Serveur Apple (LM Link)",
        "endpoint": "http://old-host:1234",
        "endpoint_type": "lmstudio",
    }
    view = ModelTargetSettings(settings, legacy)
    assert view.get_custom_endpoint() == "http://new-host:1234"
    assert view.get_custom_endpoint_api_key() == "server-secret"
    assert "endpoint" not in view.get_custom_model_target()

    picker = PromptModelChoice(settings)
    picker.set_target(legacy)
    assert "http://new-host:1234" in picker.help.text()
    # "Actualiser" queries the configured server with its own credential.
    started = []
    monkeypatch.setattr(
        prompt_model_module.CatalogWorker,
        "start",
        lambda worker: started.append(
            (worker.endpoint, worker.endpoint_type, worker.key)
        ),
    )
    picker.refresh()
    prompt_model_module._catalog_workers.discard(picker.worker)
    assert started == [("http://new-host:1234", "lmstudio", "server-secret")]
    # Saving the prompt drops the stale server and keeps the model and device.
    assert picker.target() == without_server(legacy)
    picker.worker = None
    picker.close()


def test_saved_device_is_named_after_the_configured_server(app):
    """A stored label must not name the server the prompt no longer uses."""
    settings = Settings(endpoint="http://192.168.1.30:1234")
    picker = PromptModelChoice(settings)
    picker.set_target(
        {
            "provider": "custom",
            "model": "gemma",
            "device": None,
            "device_name": "Sur 192.168.1.20",
        }
    )
    assert picker.model.currentText() == "gemma — Sur 192.168.1.30"
    assert picker.target()["device_name"] == "Sur 192.168.1.30"

    # A remote LM Link device takes its alias on the configured server.
    settings.set_model_device_name(settings.endpoint, "opaque", "Serveur Apple")
    picker.set_target({"provider": "custom", "model": "gemma", "device": "opaque"})
    assert picker.model.currentText() == "gemma — Sur Serveur Apple (LM Link)"
    # Without an alias, an imported device keeps the neutral label.
    picker.set_target({"provider": "custom", "model": "gemma", "device": "other"})
    assert picker.model.currentText() == "gemma — Poste choisi"
    assert picker.target() == {"provider": "custom", "model": "gemma", "device": "other"}
    picker.close()


def test_exported_and_imported_prompts_carry_no_machine_label():
    from supermenu_core.config.prompt_transfer import _follow_configured_server

    prompts = {
        "corriger": {
            "prompt": "Corrige",
            "model_target": {
                "provider": "custom",
                "model": "gemma",
                "device": None,
                "device_name": "Sur 192.168.1.20",
                "endpoint": "http://192.168.1.20:1234",
            },
        },
        "resumer": {"prompt": "Résume"},
    }

    assert _follow_configured_server(prompts) == {
        "corriger": {
            "prompt": "Corrige",
            "model_target": {"provider": "custom", "model": "gemma", "device": None},
        },
        "resumer": {"prompt": "Résume"},
    }
    # The library being exported is left as it is.
    assert prompts["corriger"]["model_target"]["device_name"] == "Sur 192.168.1.20"


def test_device_choice_needs_the_configured_lmstudio_server(app):
    settings = Settings()
    picker = PromptModelChoice(settings)
    picker.set_target({"provider": "custom", "model": "gemma"})
    populate_model_catalog(
        picker.model,
        [{"id": "gemma", "sources": [None, "opaque"]}],
        lmstudio=True,
        endpoint=settings.get_custom_endpoint(),
        settings=settings,
    )
    picker.model.setCurrentIndex(1)
    assert picker.target()["device"] == "opaque"

    settings.endpoint_type = "ollama"
    assert not picker.is_valid()
    assert "LM Studio" in picker.help.text()
    with pytest.raises(ValueError):
        ModelTargetSettings(settings, {"provider": "custom", "model": "g", "device": None})
    picker.close()


def test_empty_server_choice_stays_invalid(app):
    settings = Settings()
    picker = PromptModelChoice(settings)
    picker.provider.setCurrentIndex(picker.provider.findData("custom"))
    picker.model.clear()
    picker.model.setEditText("")
    assert not picker.is_valid()
    settings.endpoint = ""
    picker.set_target({"provider": "custom", "model": "gemma"})
    assert "Réglages > Texte" in picker.help.text()
    picker.close()


# A prompt never routes text to a foreign server.


def test_foreign_endpoint_in_a_prompt_is_never_contacted():
    settings = Settings()
    settings.get_prompt = lambda _prompt_id: {
        "model_target": {
            "provider": "custom",
            "model": "gemma",
            "endpoint": "https://collector.example",
            "endpoint_type": "lmstudio",
        }
    }
    view = settings_for_prompt(settings, "corriger")
    client = OpenAIClient(view, allow_images=False)
    try:
        assert "collector.example" not in client.api_url
        assert client.api_url == "http://localhost:1234/api/v1/chat"
        assert client.endpoint_api_key == "server-secret"
    finally:
        client.close()


# A prompt's model never rewrites the general effort.


def test_prompt_model_does_not_rewrite_the_general_effort():
    settings = Settings()
    settings.settings.values["openai_reasoning_effort"] = "max"
    view = ModelTargetSettings(settings, {"provider": "openai", "model": "gpt-5.4"})
    assert view.get_openai_reasoning_effort("gpt-5.4") == "xhigh"
    assert view.get_reasoning_effort() == "xhigh"
    client = OpenAIClient(view, api_key="test", allow_images=False)
    try:
        data, _cleanup = client._build_request_data("Corrige", "Texte")
    finally:
        client.close()
    assert data["reasoning_effort"] == "xhigh"
    assert settings.settings.values["openai_reasoning_effort"] == "max"
    assert settings.settings.writes == []


def test_reasoning_settings_are_read_on_the_calling_thread(monkeypatch):
    settings = Settings()
    settings.settings.values["openai_reasoning_effort"] = "high"
    view = ModelTargetSettings(settings, {"provider": "openai", "model": "gpt-5.6-luna"})
    client = OpenAIClient(view, api_key="test", allow_images=False)
    read_threads = []
    original = view.get_openai_reasoning_effort

    def tracked(model=None):
        read_threads.append(threading.current_thread())
        return original(model)

    monkeypatch.setattr(view, "get_openai_reasoning_effort", tracked)
    payloads = []
    monkeypatch.setattr(
        client,
        "_perform_request",
        lambda _headers, data, **_options: payloads.append(data)
        or SimpleNamespace(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": "Réponse"}}]},
        ),
    )
    workers = []

    class Worker(threading.Thread):
        def start(self):
            workers.append(self)
            super().start()

    monkeypatch.setattr(threading, "Thread", Worker)
    try:
        client.send_request("Corrige", "Texte", include_reasoning=False)
        workers[0].join(timeout=10)
    finally:
        client.close()
    assert payloads and payloads[0]["reasoning_effort"] == "high"
    assert read_threads and set(read_threads) == {threading.main_thread()}


# The platform owns the Foundry catalogue.


def test_foundry_catalogue_comes_from_the_platform(app):
    target = {"provider": "foundry", "model": "phi-5"}
    # Without a catalogue (macOS) the platform adapter refuses the engine.
    assert ModelTargetSettings(PCSettings(), target).get_foundry_model() == "phi-5"
    register_foundry_models(["qwen3.5-4b", "phi-5", None])
    assert registered_foundry_models() == ("qwen3.5-4b", "phi-5")
    assert ModelTargetSettings(PCSettings(), target).get_foundry_model() == "phi-5"
    with pytest.raises(ValueError):
        ModelTargetSettings(PCSettings(), {"provider": "foundry", "model": "qwen3.5-9b"})

    picker = PromptModelChoice(PCSettings())
    picker.provider.setCurrentIndex(picker.provider.findData("foundry"))
    assert [picker.model.itemText(i) for i in range(picker.model.count())] == [
        "qwen3.5-4b",
        "phi-5",
    ]
    assert picker.target() == {"provider": "foundry", "model": "qwen3.5-4b"}
    picker.set_target(target)
    assert picker.target() == target
    picker.close()


def test_imported_foundry_choice_is_kept_where_foundry_is_missing(app):
    picker = PromptModelChoice(Settings())
    assert picker.provider.findData("foundry") < 0
    picker.set_target({"provider": "foundry", "model": "qwen3.5-9b"})
    assert picker.target() == {"provider": "foundry", "model": "qwen3.5-9b"}
    picker.close()
