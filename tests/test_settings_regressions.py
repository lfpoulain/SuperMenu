import json

import pytest

from src.config import settings as settings_module
from src.config.openai_models import (
    AVAILABLE_MODELS,
    DEFAULT_OPENAI_MODEL,
    get_default_reasoning_effort_for_model,
    get_reasoning_efforts_for_model,
    normalize_openai_model,
    normalize_reasoning_effort,
)
from src.config.settings import Settings


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module.os.path, "expanduser", lambda _path: str(tmp_path))
    instance = Settings()
    yield instance
    instance.settings.clear()
    instance.settings.sync()


def test_current_openai_models_use_documented_reasoning_efforts():
    gpt_54_efforts = ["none", "low", "medium", "high", "xhigh"]
    gpt_56_efforts = [*gpt_54_efforts, "max"]

    assert AVAILABLE_MODELS == [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.4",
    ]
    assert get_reasoning_efforts_for_model("gpt-5.4") == gpt_54_efforts
    for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
        assert get_reasoning_efforts_for_model(model) == gpt_56_efforts
        assert get_default_reasoning_effort_for_model(model) == "medium"

    assert get_default_reasoning_effort_for_model("gpt-5.4") == "none"
    assert normalize_reasoning_effort("gpt-5.4", "minimal") == "low"
    assert normalize_reasoning_effort("gpt-5.4", "max") == "xhigh"
    assert normalize_reasoning_effort("gpt-5.6-sol", "invalid") == "medium"


@pytest.mark.parametrize(
    ("legacy_model", "target_model"),
    [
        ("gpt-5.2", "gpt-5.6-sol"),
        ("gpt-5.4-mini", "gpt-5.6-terra"),
        ("gpt-5-mini", "gpt-5.6-terra"),
        ("gpt-5.4-nano", "gpt-5.6-luna"),
        ("gpt-4.1-mini", "gpt-5.6-luna"),
    ],
)
def test_legacy_models_are_migrated_by_role(legacy_model, target_model):
    assert normalize_openai_model(legacy_model) == target_model


def test_new_install_uses_current_flagship_and_documented_effort(isolated_settings):
    assert isolated_settings.get_model() == DEFAULT_OPENAI_MODEL
    assert isolated_settings.get_openai_reasoning_effort() == "medium"


def test_legacy_reasoning_is_migrated_without_mixing_providers(isolated_settings):
    isolated_settings.settings.setValue("model", "gpt-5.4-mini")
    isolated_settings.settings.setValue("reasoning_effort", "high")
    isolated_settings.settings.remove("openai_reasoning_effort")
    isolated_settings.settings.remove("custom_reasoning_effort")

    isolated_settings._initialize_settings()

    assert isolated_settings.get_model() == "gpt-5.6-terra"
    assert isolated_settings.get_openai_reasoning_effort() == "high"
    assert isolated_settings.get_custom_reasoning_effort() == "high"


def test_openai_and_custom_reasoning_settings_are_independent(isolated_settings):
    isolated_settings.set_model("gpt-5.6-sol")
    isolated_settings.set_openai_reasoning_effort("max")
    isolated_settings.set_custom_reasoning_effort("low")

    isolated_settings.set_use_custom_endpoint(False)
    assert isolated_settings.get_reasoning_effort() == "max"

    isolated_settings.set_use_custom_endpoint(True)
    assert isolated_settings.get_reasoning_effort() == "low"

    isolated_settings.set_custom_reasoning_effort("none")
    isolated_settings.set_use_custom_endpoint(False)
    assert isolated_settings.get_reasoning_effort() == "max"


def test_corrupt_model_settings_fall_back_without_crashing(isolated_settings):
    isolated_settings.settings.setValue("model", 42)
    isolated_settings.settings.setValue("openai_reasoning_effort", 42)

    assert isolated_settings.get_model() == DEFAULT_OPENAI_MODEL
    assert isolated_settings.get_openai_reasoning_effort() == "medium"


def test_prompt_import_is_atomic_when_one_collection_is_invalid(isolated_settings, tmp_path):
    original_text = isolated_settings.get_prompts()
    original_voice = isolated_settings.get_voice_prompts()
    import_path = tmp_path / "invalid-prompts.json"
    import_path.write_text(
        json.dumps(
            {
                "text_prompts": {
                    "valid": {
                        "name": "Valide",
                        "prompt": "Prompt",
                        "status": "Traitement",
                    }
                },
                "voice_prompts": [],
            }
        ),
        encoding="utf-8",
    )

    success, _message = isolated_settings.import_prompts(str(import_path))

    assert success is False
    assert isolated_settings.get_prompts() == original_text
    assert isolated_settings.get_voice_prompts() == original_voice


@pytest.mark.parametrize(
    ("setting_name", "getter_name"),
    [
        ("prompts", "get_prompts"),
        ("voice_prompts", "get_voice_prompts"),
    ],
)
def test_invalid_prompt_root_is_rejected_without_crashing(
    isolated_settings, setting_name, getter_name
):
    isolated_settings.settings.setValue(setting_name, json.dumps(["not", "a", "mapping"]))

    assert getattr(isolated_settings, getter_name)() == {}


def test_valid_prompt_reads_do_not_write_settings(isolated_settings, monkeypatch):
    writes = []
    monkeypatch.setattr(
        isolated_settings,
        "set_prompts",
        lambda prompts: writes.append(prompts),
    )

    assert isolated_settings.get_prompts()
    assert writes == []


def test_draft_prompt_with_empty_body_remains_editable(isolated_settings):
    isolated_settings.add_prompt(
        "draft",
        "Brouillon",
        "",
        "Configuration en cours",
    )

    assert isolated_settings.get_prompt("draft")["prompt"] == ""


def test_each_prompt_can_have_its_own_hotkey(isolated_settings):
    isolated_settings.add_prompt(
        "first",
        "Premier",
        "Premier prompt",
        "Traitement",
        hotkey="Ctrl+Alt+1",
    )
    isolated_settings.add_prompt(
        "second",
        "Second",
        "Second prompt",
        "Traitement",
        hotkey="Ctrl+Alt+2",
    )

    assert isolated_settings.get_prompt("first")["hotkey"] == "Ctrl+Alt+1"
    assert isolated_settings.get_prompt("second")["hotkey"] == "Ctrl+Alt+2"


def test_duplicate_prompt_hotkeys_are_rejected(isolated_settings):
    isolated_settings.add_prompt(
        "first",
        "Premier",
        "Premier prompt",
        "Traitement",
        hotkey="Ctrl+Alt+1",
    )

    with pytest.raises(ValueError, match="déjà utilisé"):
        isolated_settings.add_prompt(
            "second",
            "Second",
            "Second prompt",
            "Traitement",
            hotkey="ctrl+alt+1",
        )


def test_legacy_instant_hotkey_is_migrated_to_its_prompt(
    isolated_settings,
):
    prompts = isolated_settings.get_prompts()
    prompts["corriger"]["instant_hotkey"] = True
    prompts["corriger"].pop("hotkey", None)
    isolated_settings.settings.setValue("prompts", json.dumps(prompts))
    isolated_settings.settings.setValue("instant_hotkey", "Ctrl+Shift+C")

    isolated_settings._migrate_legacy_instant_hotkey()

    assert isolated_settings.get_prompt("corriger")["hotkey"] == "Ctrl+Shift+C"
    assert not isolated_settings.settings.contains("instant_hotkey")


def test_reset_restores_voice_hotkey_and_screenshot_mode(isolated_settings):
    isolated_settings.set_voice_hotkey("Ctrl+Shift+V")
    isolated_settings.set_screenshot_capture_mode("ask")
    isolated_settings.set_transcription_languages("en")
    isolated_settings.set_transcription_keywords("Codex")
    isolated_settings.set_transcription_prompt("A custom context")
    isolated_settings.set_update_channel("beta")

    isolated_settings.reset_to_defaults()

    assert isolated_settings.get_voice_hotkey() == isolated_settings.default_voice_hotkey
    assert (
        isolated_settings.get_screenshot_capture_mode()
        == isolated_settings.default_screenshot_capture_mode
    )
    assert (
        isolated_settings.get_transcription_languages()
        == isolated_settings.default_transcription_languages
    )
    assert isolated_settings.get_transcription_keywords() == ""
    assert isolated_settings.get_transcription_prompt() == ""
    assert isolated_settings.get_update_channel() == "stable"


def test_update_channel_defaults_to_stable_and_rejects_unknown_values(
    isolated_settings,
):
    assert isolated_settings.get_update_channel() == "stable"

    isolated_settings.set_update_channel("beta")
    assert isolated_settings.get_update_channel() == "beta"

    isolated_settings.set_update_channel("nightly")
    assert isolated_settings.get_update_channel() == "stable"


def test_legacy_response_window_mode_is_removed(isolated_settings):
    isolated_settings.settings.setValue(
        "response_window_open_mode",
        "win32_foreground",
    )

    isolated_settings._initialize_settings()

    assert not isolated_settings.settings.contains(
        "response_window_open_mode"
    )
