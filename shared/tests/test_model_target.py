import json

from PySide6.QtWidgets import QApplication

from supermenu_core.config.model_target import (
    ModelTargetSettings,
    ModelTargetSettingsMixin,
    normalize_model_target,
)
from supermenu_core.ui.prompt_model import PromptModelChoice
from supermenu_core.ui.model_catalog import populate_model_catalog


class Memory:
    def __init__(self):
        self.values = {}

    def value(self, key, default):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value


class Settings(ModelTargetSettingsMixin):
    def __init__(self):
        self.settings = Memory()

    def get_model(self):
        return "gpt-5.6-sol"

    def get_custom_model(self):
        return "gemma"

    def get_custom_endpoint(self):
        return "http://localhost:1234"

    def get_custom_endpoint_type(self):
        return "lmstudio"

    def get_custom_endpoint_api_key(self):
        return "server-secret"

    def get_foundry_model(self):
        return "qwen3.5-4b"


def test_local_null_is_distinct_from_automatic_and_remote():
    for device in [None, "remote"]:
        target = {"provider": "custom", "model": "gemma", "device": device}
        assert normalize_model_target(json.loads(json.dumps(target))) == target
    assert "device" not in normalize_model_target(
        {"provider": "custom", "model": "gemma"}
    )


def test_settings_views_isolate_model_device_and_credentials():
    settings = Settings()
    local = ModelTargetSettings(
        settings, {"provider": "custom", "model": "tiny", "device": None}
    )
    remote = ModelTargetSettings(
        settings,
        {
            "provider": "custom",
            "model": "large",
            "device": "apple",
            "endpoint": "http://other:1234",
        },
    )
    assert local.get_custom_model() == "tiny"
    assert remote.get_custom_model() == "large"
    assert settings.get_custom_model() == "gemma"
    assert local.get_custom_endpoint_api_key() == "server-secret"
    # A server stored in the prompt (older version, imported file) is ignored:
    # the request goes to the configured server, with its own credential.
    assert remote.get_custom_endpoint() == "http://localhost:1234"
    assert remote.get_custom_endpoint_api_key() == "server-secret"
    assert remote.get_custom_model_target() == {
        "provider": "custom",
        "model": "large",
        "device": "apple",
    }


def test_global_target_and_friendly_names_are_persisted_per_endpoint():
    settings = Settings()
    settings.set_custom_model_target(
        {"provider": "custom", "model": "gemma", "device": "remote"}
    )
    assert settings.get_custom_model_target()["device"] == "remote"
    settings.set_model_device_name("http://localhost:1234", "remote", "Serveur Apple")
    assert (
        settings.get_model_device_names("http://localhost:1234/")["remote"]
        == "Serveur Apple"
    )
    assert not settings.get_model_device_names("http://other:1234")
    settings.get_custom_endpoint = lambda: "http://other:1234"
    assert settings.get_custom_model_target() == {}


def test_prompt_picker_preserves_separate_models_devices_and_reset():
    app = QApplication.instance() or QApplication([])
    settings = Settings()
    picker = PromptModelChoice(settings)
    target = {"provider": "custom", "model": "gemma", "device": "opaque"}
    picker.set_target(target)
    settings.set_model_device_name(
        settings.get_custom_endpoint(), "opaque", "Serveur Apple"
    )
    populate_model_catalog(
        picker.model,
        [{"id": "gemma", "sources": [None, "opaque"]}],
        lmstudio=True,
        endpoint=settings.get_custom_endpoint(),
        settings=settings,
    )
    assert "Serveur Apple" in picker.model.currentText()
    assert picker.target()["device"] == "opaque"
    picker.model.setCurrentIndex(0)
    assert picker.target()["device"] is None
    picker.set_target({})
    assert picker.target() == {}
    picker.set_target({"provider": "openai", "model": "gpt-5.6-sol"})
    assert picker.target() == {"provider": "openai", "model": "gpt-5.6-sol"}
    picker.close()
    app.processEvents()


def test_dictation_correction_uses_corriger_target_or_general_settings():
    from supermenu_core.config.model_target import settings_for_prompt

    settings = Settings()
    settings.get_prompt = lambda _: {
        "model_target": {"provider": "openai", "model": "gpt-5.6-luna"}
    }
    assert settings_for_prompt(settings, "corriger").get_model() == "gpt-5.6-luna"
    settings.get_prompt = lambda _: None
    assert settings_for_prompt(settings, "corriger") is settings
