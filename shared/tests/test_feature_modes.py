"""Advanced and experimental feature switches: storage, migration and helpers."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from PySide6.QtCore import QSettings

from supermenu_core.audio.settings import SpeechSettingsMixin
from supermenu_core.config import feature_modes
from supermenu_core.config.feature_modes import (
    ADVANCED_FEATURES_SETTING,
    EXPERIMENTAL_FEATURES_SETTING,
    FeatureModesSettingsMixin,
    advanced_enabled,
    effective_model_target,
    effective_speech_idle_seconds,
    effective_text_idle_seconds,
    experimental_enabled,
    prompts_with_model_target,
)
from supermenu_core.config.model_memory import DEFAULT_IDLE_SECONDS, TextMemorySettingsMixin
from supermenu_core.config.model_target import ModelTargetSettings, settings_for_prompt
from supermenu_core.config.prompt_transfer import export_prompt_bundle, import_prompt_bundle
from supermenu_core.config.voice_prompts import VoicePromptSettingsMixin

KEYS = (ADVANCED_FEATURES_SETTING, EXPERIMENTAL_FEATURES_SETTING)
TARGET = {"provider": "openai", "model": "gpt-5.6-luna"}


class Switches(FeatureModesSettingsMixin):
    """Only the switches, opened like both applications open their settings."""

    def __init__(self, path):
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)
        self.syncs = 0
        self.initialize_feature_modes(self.has_saved_preferences())

    def sync(self):
        self.syncs += 1
        self.settings.sync()


class Settings(
    FeatureModesSettingsMixin,
    VoicePromptSettingsMixin,
    TextMemorySettingsMixin,
    SpeechSettingsMixin,
):
    """Settings with prompts, retention and the switches."""

    def __init__(self, path):
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)
        self.initialize_feature_modes(self.has_saved_preferences())
        if not self.settings.contains("prompts"):
            self.set_prompts(
                {
                    "corriger": {
                        "name": "Corriger",
                        "prompt": "Corrige",
                        "status": "Correction…",
                        "insert_directly": False,
                        "position": 1,
                        "hotkey": "Ctrl+Alt+C",
                        "reasoning_mode": "default",
                        "model_target": dict(TARGET),
                    },
                    "traduire": {
                        "name": "Traduire",
                        "prompt": "Traduis",
                        "status": "Traduction…",
                        "insert_directly": False,
                        "position": 2,
                        "hotkey": "",
                        "reasoning_mode": "default",
                        "model_target": {},
                    },
                }
            )
        self.initialize_voice_prompts()

    def get_prompts(self):
        return json.loads(self.settings.value("prompts", "{}"))

    def get_prompt(self, prompt_id):
        return self.get_prompts().get(prompt_id)

    def set_prompts(self, prompts):
        self.settings.setValue("prompts", json.dumps(prompts, ensure_ascii=False))

    def get_model(self):
        return "gpt-5.6-sol"

    def sync(self):
        self.settings.sync()


def _stored(path):
    """Read the switches back from the file, as a later launch would."""
    store = QSettings(str(path), QSettings.Format.IniFormat)
    return {
        key: store.value(key, type=bool) if store.contains(key) else None
        for key in KEYS
    }


def test_new_installation_starts_with_both_switches_off_and_saves_them(tmp_path):
    path = tmp_path / "new.ini"
    settings = Switches(path)
    assert not settings.get_advanced_features_enabled()
    assert not settings.get_experimental_features_enabled()
    assert _stored(path) == {key: False for key in KEYS}
    assert settings.syncs == 1


@pytest.mark.parametrize("marker", feature_modes.LEGACY_MARKER_KEYS)
def test_update_from_an_earlier_version_keeps_every_feature_on(tmp_path, marker):
    path = tmp_path / "update.ini"
    earlier = QSettings(str(path), QSettings.Format.IniFormat)
    earlier.setValue(marker, "valeur d’une version précédente")
    earlier.sync()
    settings = Switches(path)
    assert settings.get_advanced_features_enabled()
    assert settings.get_experimental_features_enabled()
    assert _stored(path) == {key: True for key in KEYS}
    # The earlier value is untouched.
    assert _stored_value(path, marker) == "valeur d’une version précédente"


def _stored_value(path, key):
    return QSettings(str(path), QSettings.Format.IniFormat).value(key)


def test_an_unrelated_key_does_not_make_an_existing_installation(tmp_path):
    path = tmp_path / "unrelated.ini"
    store = QSettings(str(path), QSettings.Format.IniFormat)
    store.setValue("prompts_backups", "[]")
    store.sync()
    Switches(path)
    assert _stored(path) == {key: False for key in KEYS}


def test_saved_choices_are_never_overwritten(tmp_path):
    path = tmp_path / "choices.ini"
    store = QSettings(str(path), QSettings.Format.IniFormat)
    for key in ("hotkey", "prompts"):
        store.setValue(key, "x")
    store.setValue(ADVANCED_FEATURES_SETTING, False)
    store.sync()
    settings = Switches(path)
    # Only the missing switch is added, as for any existing installation.
    assert not settings.get_advanced_features_enabled()
    assert settings.get_experimental_features_enabled()
    settings.set_experimental_features_enabled(False)
    settings.sync()
    syncs = settings.syncs
    settings.initialize_feature_modes(True)
    assert settings.syncs == syncs, "nothing to write, nothing to sync"
    assert _stored(path) == {key: False for key in KEYS}
    assert not Switches(path).get_experimental_features_enabled()


def test_new_installation_default_is_read_when_used(tmp_path, monkeypatch):
    monkeypatch.setattr(feature_modes, "NEW_INSTALL_ENABLED", True)
    path = tmp_path / "seam.ini"
    Switches(path)
    assert _stored(path) == {key: True for key in KEYS}
    bare = FeatureModesSettingsMixin()
    bare.settings = QSettings(str(tmp_path / "empty.ini"), QSettings.Format.IniFormat)
    assert bare.get_advanced_features_enabled()
    monkeypatch.setattr(feature_modes, "NEW_INSTALL_ENABLED", False)
    assert not bare.get_advanced_features_enabled()
    assert not bare.get_experimental_features_enabled()


def test_unreadable_settings_count_as_a_new_installation():
    broken = FeatureModesSettingsMixin()
    broken.settings = Mock()
    broken.settings.contains.side_effect = RuntimeError("illisible")
    assert broken.has_saved_preferences() is False


@pytest.mark.parametrize("settings", [SimpleNamespace(), Mock(), MagicMock()])
def test_settings_without_switches_keep_every_feature(settings):
    assert advanced_enabled(settings) is True
    assert experimental_enabled(settings) is True
    assert effective_model_target(settings, TARGET) == TARGET


def test_prompt_views_forward_the_switches(tmp_path):
    settings = Settings(tmp_path / "view.ini")
    view = ModelTargetSettings(settings, TARGET)
    assert not advanced_enabled(view) and not experimental_enabled(view)
    settings.set_advanced_features_enabled(True)
    assert advanced_enabled(view) and not experimental_enabled(view)
    # A view over settings without the switches keeps every feature.
    legacy = SimpleNamespace(get_custom_endpoint_type=lambda: "ollama")
    assert advanced_enabled(ModelTargetSettings(legacy, TARGET))


def test_effective_values_follow_the_switch_without_rewriting_settings(tmp_path):
    path = tmp_path / "effective.ini"
    settings = Settings(path)
    settings.set_text_idle_seconds(-1)
    settings.set_speech_idle_seconds(0)
    settings.sync()
    before = _stored_value(path, "text_idle_seconds"), _stored_value(
        path, "speech_idle_seconds"
    )
    assert effective_model_target(settings, TARGET) == {}
    assert effective_model_target(settings, None) == {}
    assert effective_text_idle_seconds(settings) == DEFAULT_IDLE_SECONDS == 300
    assert effective_speech_idle_seconds(settings) == DEFAULT_IDLE_SECONDS
    settings.set_advanced_features_enabled(True)
    target = effective_model_target(settings, TARGET)
    assert target == TARGET and target is not TARGET
    assert effective_model_target(settings, None) == {}
    assert effective_text_idle_seconds(settings) == -1
    assert effective_speech_idle_seconds(settings) == 0
    settings.sync()
    after = _stored_value(path, "text_idle_seconds"), _stored_value(
        path, "speech_idle_seconds"
    )
    assert before == after


def test_prompts_with_their_own_model_are_counted_without_changes(tmp_path):
    settings = Settings(tmp_path / "count.ini")
    voice = settings.get_voice_prompts()
    first = next(iter(voice))
    voice[first]["model_target"] = {"provider": "custom", "model": "gemma"}
    settings.set_voice_prompts(voice)
    stored = settings.settings.value("prompts"), settings.settings.value("voice_prompts")
    assert prompts_with_model_target(settings) == 2
    assert (settings.settings.value("prompts"), settings.settings.value("voice_prompts")) == stored
    assert prompts_with_model_target(Mock()) == 0
    assert prompts_with_model_target(SimpleNamespace()) == 0
    failing = SimpleNamespace(get_prompts=Mock(side_effect=ValueError("illisible")))
    assert prompts_with_model_target(failing) == 0


def test_dictation_correction_uses_the_text_settings_without_advanced_features(
    tmp_path,
):
    settings = Settings(tmp_path / "correction.ini")
    assert settings.get_prompt("corriger")["model_target"] == TARGET
    assert settings_for_prompt(settings, "corriger") is settings
    settings.set_advanced_features_enabled(True)
    view = settings_for_prompt(settings, "corriger")
    assert isinstance(view, ModelTargetSettings)
    assert view.get_model() == "gpt-5.6-luna"
    assert settings_for_prompt(settings, "traduire") is settings


def test_export_and_import_keep_every_field_with_both_switches_off(tmp_path):
    source = Settings(tmp_path / "source.ini")
    voice = source.get_voice_prompts()
    first = next(iter(voice))
    voice[first]["model_target"] = {"provider": "openai", "model": "gpt-5.6-terra"}
    source.set_voice_prompts(voice)
    assert not advanced_enabled(source) and not experimental_enabled(source)
    destination = Settings(tmp_path / "destination.ini")
    destination.set_prompts({})
    destination.set_voice_prompts({})
    bundle = tmp_path / "prompts.json"
    export_prompt_bundle(source, bundle)
    exported = json.loads(bundle.read_text(encoding="utf-8"))
    assert exported["text_prompts"]["corriger"]["hotkey"] == "Ctrl+Alt+C"
    assert exported["text_prompts"]["corriger"]["model_target"] == TARGET
    import_prompt_bundle(destination, bundle)
    assert destination.get_prompts() == source.get_prompts()
    assert destination.get_voice_prompts() == source.get_voice_prompts()
    assert destination.get_voice_prompt(first)["model_target"]["model"] == "gpt-5.6-terra"
