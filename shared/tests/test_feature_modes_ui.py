"""Shared widgets behind the advanced and experimental feature switches."""

import json
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from supermenu_core.audio.backends import SpeechBackend
from supermenu_core.audio.settings import SpeechSettingsMixin
from supermenu_core.config.feature_modes import (
    ADVANCED_FEATURES_SETTING,
    EXPERIMENTAL_FEATURES_SETTING,
    FeatureModesSettingsMixin,
)
from supermenu_core.config.prompts import default_text_prompts
from supermenu_core.config.voice_prompts import VoicePromptSettingsMixin
from supermenu_core.ui import application_settings
from supermenu_core.ui.application_settings import FeatureModeSettings
from supermenu_core.ui.dictation_settings import DictationBehaviorSettings
from supermenu_core.ui.settings_panel import SettingsPanel
from supermenu_core.ui.shortcut_settings import ShortcutSettings
from supermenu_core.ui.speech_settings import SpeechSettingsWidget
from supermenu_core.ui.text_prompt_form import TextPromptForm, reset_text_prompt
from supermenu_core.ui.voice_prompt_editor import VoicePromptEditor

LINK_TARGET = {"provider": "custom", "model": "qwen", "device": "poste-1"}
OPENAI_TARGET = {"provider": "openai", "model": "gpt-5.6-luna"}


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def no_microphones(monkeypatch):
    monkeypatch.setattr("supermenu_core.ui.speech_settings.microphones", lambda: [])


class Settings(FeatureModesSettingsMixin, VoicePromptSettingsMixin, SpeechSettingsMixin):
    """Text settings on an LM Studio server with LM Link devices, plus prompts."""

    endpoint_type = "lmstudio"
    provider = "openai"

    def __init__(self, path):
        self.path = str(path)
        self.settings = QSettings(self.path, QSettings.Format.IniFormat)
        self.initialize_feature_modes(self.has_saved_preferences())
        self.default_prompts = default_text_prompts()
        if not self.settings.contains("prompts"):
            self.set_prompts(self.default_prompts)
        self.initialize_voice_prompts()
        self.key = ""

    # Text prompts, saved like the Windows adapter: None keeps the stored value.
    def get_prompts(self):
        return json.loads(self.settings.value("prompts", "{}"))

    def get_prompt(self, prompt_id):
        return self.get_prompts().get(prompt_id)

    def set_prompts(self, prompts):
        self.settings.setValue("prompts", json.dumps(prompts, ensure_ascii=False))

    def update_prompt(
        self,
        prompt_id,
        name,
        prompt,
        status,
        insert_directly=False,
        position=None,
        hotkey="",
        reasoning_mode=None,
        model_target=None,
    ):
        prompts = self.get_prompts()
        current = prompts.get(prompt_id, {})
        prompts[prompt_id] = {
            "model_target": (
                model_target
                if model_target is not None
                else current.get("model_target", {})
            ),
            "reasoning_mode": (
                reasoning_mode
                if reasoning_mode is not None
                else current.get("reasoning_mode", "default")
            ),
            "name": name,
            "prompt": prompt,
            "status": status,
            "insert_directly": insert_directly,
            "position": position if position is not None else current.get("position", 999),
            "hotkey": str(hotkey or "").strip(),
        }
        self.set_prompts(prompts)

    # Text engine, as the prompt model picker reads it.
    def get_ai_provider(self):
        return self.provider

    def get_model(self):
        return "gpt-5.6-sol"

    def get_custom_endpoint(self):
        return "http://localhost:1234"

    def get_custom_endpoint_type(self):
        return self.endpoint_type

    def get_custom_model(self):
        return ""

    def get_custom_model_target(self):
        return {}

    def get_model_device_names(self, _endpoint):
        return {}

    def get_custom_endpoint_api_key(self):
        return ""

    def get_api_key(self):
        return self.key

    def set_api_key(self, key):
        self.key = key

    def sync(self):
        self.settings.sync()


def _reopened(path, key):
    store = QSettings(str(path), QSettings.Format.IniFormat)
    return store.value(key, type=bool) if store.contains(key) else None


def _with_targets(settings):
    prompts = settings.get_prompts()
    prompts["corriger"]["model_target"] = dict(OPENAI_TARGET)
    prompts["corriger"]["hotkey"] = "Ctrl+Alt+K"
    settings.set_prompts(prompts)
    settings.sync()


# Application settings: the two switches


def test_switches_reflect_settings_and_save_only_changes(app, tmp_path):
    settings = Settings(tmp_path / "modes.ini")
    widget = FeatureModeSettings(settings)
    emitted = []
    widget.modes_changed.connect(lambda *values: emitted.append(values))
    assert widget.title() == "Fonctions"
    assert not widget.advanced_check.isChecked()
    assert not widget.experimental_check.isChecked()
    assert widget.save() is False and emitted == []
    widget.experimental_check.setChecked(True)
    assert widget.has_unsaved_changes()
    assert widget.save() is True
    assert emitted == [(False, True)]
    assert settings.get_experimental_features_enabled()
    assert _reopened(tmp_path / "modes.ini", EXPERIMENTAL_FEATURES_SETTING) is True
    assert _reopened(tmp_path / "modes.ini", ADVANCED_FEATURES_SETTING) is False
    assert widget.save() is False and emitted == [(False, True)]
    # Changed elsewhere (another window, a reset): refresh() shows it.
    settings.set_advanced_features_enabled(True)
    widget.refresh()
    assert widget.advanced_check.isChecked()
    widget.experimental_check.setChecked(False)
    widget.refresh()
    assert widget.experimental_check.isChecked()
    widget.deleteLater()


def test_switches_accept_settings_without_the_api(app):
    settings = Mock()
    widget = FeatureModeSettings(settings)
    # No API means an older adapter: every feature stays on.
    assert widget.advanced_check.isChecked() and widget.experimental_check.isChecked()
    assert widget.save() is False
    settings.get_prompts.assert_not_called()
    widget.deleteLater()


def test_descriptions_name_only_the_features_of_the_platform(app, tmp_path):
    settings = Settings(tmp_path / "texts.ini")
    windows = FeatureModeSettings(settings, screen_capture=True, text_model_retention=True)
    mac = FeatureModeSettings(settings)
    assert "capture et analyse d’écran" in windows.experimental_description.text()
    assert "capture" not in mac.experimental_description.text()
    assert "modèles locaux en mémoire" in windows.advanced_description.text()
    assert "modèle vocal local" in mac.advanced_description.text()
    for widget in (windows, mac):
        assert widget.advanced_check.accessibleName() == "Activer les fonctions avancées"
        assert (
            widget.experimental_check.accessibleName()
            == "Activer les fonctions expérimentales"
        )
        assert (
            widget.advanced_check.accessibleDescription()
            == widget.advanced_description.text()
        )
        assert (
            widget.experimental_check.accessibleDescription()
            == widget.experimental_description.text()
        )
        widget.deleteLater()


@pytest.mark.parametrize("answer", ["no", "yes"])
def test_turning_advanced_off_asks_when_prompts_have_their_own_model(
    app, tmp_path, monkeypatch, answer
):
    settings = Settings(tmp_path / "confirm.ini")
    settings.set_advanced_features_enabled(True)
    _with_targets(settings)
    questions = []

    def question(_parent, title, text, _buttons, default):
        questions.append((title, text, default))
        return getattr(QMessageBox.StandardButton, answer.capitalize())

    monkeypatch.setattr(application_settings.QMessageBox, "question", question)
    widget = FeatureModeSettings(settings)
    emitted = []
    widget.modes_changed.connect(lambda *values: emitted.append(values))
    widget.advanced_check.setChecked(False)
    saved = widget.save()
    assert len(questions) == 1
    title, text, default = questions[0]
    assert title == "Désactiver les fonctions avancées"
    assert text.startswith("1 prompt(s) utilisent un modèle choisi pour eux.")
    assert "(OpenAI)" in text
    assert default == QMessageBox.StandardButton.No
    if answer == "no":
        assert saved is False and emitted == []
        assert widget.advanced_check.isChecked()
        assert settings.get_advanced_features_enabled()
    else:
        assert saved is True and emitted == [(False, False)]
        assert not settings.get_advanced_features_enabled()
    # The prompts themselves are never changed by the switch.
    assert settings.get_prompt("corriger")["model_target"] == OPENAI_TARGET
    widget.deleteLater()


def test_refusing_to_turn_advanced_off_still_applies_the_other_switch(
    app, tmp_path, monkeypatch
):
    settings = Settings(tmp_path / "both.ini")
    settings.set_advanced_features_enabled(True)
    _with_targets(settings)
    monkeypatch.setattr(
        application_settings.QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.No,
    )
    widget = FeatureModeSettings(settings)
    emitted = []
    widget.modes_changed.connect(lambda *values: emitted.append(values))
    widget.advanced_check.setChecked(False)
    widget.experimental_check.setChecked(True)
    assert widget.save() is True
    assert emitted == [(True, True)]
    assert settings.get_advanced_features_enabled()
    assert settings.get_experimental_features_enabled()
    widget.deleteLater()


def test_turning_advanced_off_without_own_models_does_not_ask(
    app, tmp_path, monkeypatch
):
    settings = Settings(tmp_path / "quiet.ini")
    settings.set_advanced_features_enabled(True)
    question = Mock()
    monkeypatch.setattr(application_settings.QMessageBox, "question", question)
    widget = FeatureModeSettings(settings)
    widget.advanced_check.setChecked(False)
    assert widget.save() is True
    question.assert_not_called()
    assert not settings.get_advanced_features_enabled()
    widget.deleteLater()


# Text prompt editor


def test_hidden_advanced_rows_are_neither_checked_nor_saved(app, tmp_path):
    settings = Settings(tmp_path / "form.ini")
    form = TextPromptForm(settings=settings)
    form.model_choice.set_target(LINK_TARGET)
    # The Text page switched to Ollama: the LM Link device is no longer valid.
    settings.endpoint_type = "ollama"
    assert form.is_advanced_visible()
    assert not form.model_choice_is_valid()
    with pytest.raises(ValueError):
        form.model_target_for_save()
    form.set_advanced_visible(False)
    assert not form.is_advanced_visible()
    assert not form.form.isRowVisible(form.model_choice)
    assert not form.form.isRowVisible(form.hotkey_row)
    assert form.hotkey.isHidden()
    # Reasoning stays a standard feature.
    assert form.form.isRowVisible(form.reasoning)
    assert form.form.isRowVisible(form.instruction)
    assert form.model_choice_is_valid()
    assert form.model_target_for_save() is None
    form.set_advanced_visible(True)
    assert form.form.isRowVisible(form.model_choice)
    assert form.form.isRowVisible(form.hotkey_row)
    settings.endpoint_type = "lmstudio"
    assert form.model_target_for_save()["device"] == "poste-1"
    form.deleteLater()


def _accept(app, parent):
    dialog = parent._confirmation_dialog
    dialog.done(QMessageBox.StandardButton.Yes)
    app.processEvents()


@pytest.mark.parametrize("advanced", [False, True])
def test_resetting_a_text_prompt_keeps_hidden_choices(app, tmp_path, advanced):
    settings = Settings(tmp_path / "reset.ini")
    settings.set_advanced_features_enabled(advanced)
    _with_targets(settings)
    settings.update_prompt(
        "corriger",
        "Mon correcteur",
        "Instruction modifiée",
        "En cours",
        True,
        hotkey="Ctrl+Alt+K",
        reasoning_mode="on",
    )
    parent = QWidget()
    refreshed = Mock()
    reset_text_prompt(settings, "corriger", parent, refreshed)
    _accept(app, parent)
    refreshed.assert_called_once()
    prompt = settings.get_prompt("corriger")
    default = settings.default_prompts["corriger"]
    assert (prompt["name"], prompt["prompt"]) == (default["name"], default["prompt"])
    assert prompt["insert_directly"] is False
    assert prompt["reasoning_mode"] == "default"
    if advanced:
        assert prompt["hotkey"] == ""
        assert prompt["model_target"] == {}
    else:
        assert prompt["hotkey"] == "Ctrl+Alt+K"
        assert prompt["model_target"] == OPENAI_TARGET
    parent.deleteLater()


# Voice prompt editor


def _voice_editor(tmp_path):
    settings = Settings(tmp_path / "voice.ini")
    prompts = settings.get_voice_prompts()
    first = min(prompts, key=lambda key: prompts[key].get("position", 999))
    prompts[first]["model_target"] = {**LINK_TARGET, "device_name": "Bureau"}
    settings.set_voice_prompts(prompts)
    settings.endpoint_type = "ollama"
    editor = VoicePromptEditor(settings)
    editor.set_advanced_visible(False)
    assert editor._current_id == first
    return settings, editor, first


def test_hidden_voice_model_is_kept_when_saving(app, tmp_path):
    settings, editor, first = _voice_editor(tmp_path)
    stored = settings.get_voice_prompt(first)["model_target"]
    assert not editor.is_advanced_visible()
    assert not editor._fields.isRowVisible(editor.model_choice)
    assert editor._fields.isRowVisible(editor.reasoning)
    assert not editor.has_unsaved_changes()
    editor.instruction_input.setPlainText("Nouvelle instruction vocale")
    assert editor.save() is True
    saved = settings.get_voice_prompt(first)
    assert saved["prompt"] == "Nouvelle instruction vocale"
    assert saved["model_target"] == stored
    assert not editor.has_unsaved_changes()
    # Shown again, the invalid choice must be fixed before saving.
    editor.set_advanced_visible(True)
    assert editor._fields.isRowVisible(editor.model_choice)
    assert editor.save() is False
    editor.close()


def test_hiding_the_voice_model_drops_its_unsaved_choice(app, tmp_path):
    settings = Settings(tmp_path / "pending.ini")
    prompts = settings.get_voice_prompts()
    first = min(prompts, key=lambda key: prompts[key].get("position", 999))
    prompts[first]["model_target"] = dict(OPENAI_TARGET)
    settings.set_voice_prompts(prompts)
    editor = VoicePromptEditor(settings)
    provider = editor.model_choice.provider
    assert editor._current_id == first
    assert editor.model_choice.target() == OPENAI_TARGET
    # A model choice left unsaved when the advanced features are turned off.
    provider.setCurrentIndex(provider.findData("default"))
    assert editor.has_unsaved_changes()
    editor.set_advanced_visible(False)
    assert editor.model_choice.target() == OPENAI_TARGET
    assert not editor.has_unsaved_changes()
    # The other edits stay pending and are saved with the stored model.
    editor.instruction_input.setPlainText("Instruction en attente")
    assert editor.has_unsaved_changes()
    # Whatever the hidden row holds, saving shows the stored model.
    provider.setCurrentIndex(provider.findData("default"))
    assert editor.save() is True
    saved = settings.get_voice_prompt(first)
    assert saved["prompt"] == "Instruction en attente"
    assert saved["model_target"] == OPENAI_TARGET
    assert editor.model_choice.target() == OPENAI_TARGET
    assert not editor.has_unsaved_changes()
    editor.set_advanced_visible(True)
    assert editor.model_choice.target() == OPENAI_TARGET
    assert not editor.has_unsaved_changes()
    editor.close()


def test_resetting_a_voice_prompt_keeps_the_hidden_model(app, tmp_path):
    settings, editor, first = _voice_editor(tmp_path)
    stored = settings.get_voice_prompt(first)["model_target"]
    editor.instruction_input.setPlainText("Brouillon")
    assert editor.save()
    editor.reset_prompt()
    _accept(app, editor)
    restored = settings.get_voice_prompt(first)
    assert restored["prompt"] == settings.default_voice_prompts[first]["prompt"]
    assert restored["model_target"] == stored
    assert not editor.has_unsaved_changes()
    editor.set_advanced_visible(True)
    editor.reset_prompt()
    _accept(app, editor)
    assert not settings.get_voice_prompt(first).get("model_target")
    editor.close()


# Voice settings


class FakeBackend(SpeechBackend):
    def __init__(self):
        super().__init__()
        self.cancelled = False

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True


class FakeResident(QObject):
    state_changed = Signal()

    def __init__(self):
        super().__init__()
        self.busy = self.loaded = False
        self.idle_seconds = []
        self.unloads = 0

    def set_idle_seconds(self, seconds):
        self.idle_seconds.append(seconds)

    def unload_idle(self):
        self.unloads += 1
        return True


@pytest.fixture
def resident(monkeypatch):
    service = FakeResident()
    monkeypatch.setattr(
        "supermenu_core.ui.speech_settings.get_resident_service", lambda: service
    )
    return service


def _speech(tmp_path, platform, provider):
    settings = Settings(tmp_path / f"speech-{platform}.ini")
    settings.set_speech_provider(provider)
    settings.set_speech_idle_seconds(-1)
    settings.sync()
    backend = FakeBackend()
    widget = SpeechSettingsWidget(settings, lambda _options: backend, platform=platform)
    return settings, widget, backend


def test_hidden_retention_keeps_the_stored_delay_and_applies_the_default(
    app, tmp_path, resident
):
    settings, widget, _backend = _speech(tmp_path, "win32", "foundry")
    assert widget.is_retention_visible()
    assert not widget.memory_options.isHidden()
    widget.set_retention_visible(False)
    assert not widget.is_retention_visible()
    assert widget.memory_options.isHidden()
    # The device choice keeps "Plus d’options" useful for the local engine.
    assert not widget.advanced.isHidden()
    assert not widget.has_unsaved_changes()
    assert widget.save()
    assert settings.get_speech_idle_seconds() == -1
    assert resident.idle_seconds == [300]
    assert not widget.has_unsaved_changes()
    widget.set_retention_visible(True)
    assert not widget.memory_options.isHidden()
    assert widget.save()
    assert settings.get_speech_idle_seconds() == -1
    assert resident.idle_seconds == [300, -1]
    widget.close()


def test_hiding_retention_drops_an_unsaved_delay(app, tmp_path, resident):
    settings, widget, _backend = _speech(tmp_path, "win32", "foundry")
    widget.idle_combo.setCurrentIndex(widget.idle_combo.findData(60))
    assert widget.has_unsaved_changes() and not widget.unsaved_label.isHidden()
    widget.set_retention_visible(False)
    assert widget.idle_combo.currentData() == -1
    assert not widget.has_unsaved_changes() and widget.unsaved_label.isHidden()
    assert widget.save_button.toolTip() == ""
    # The other edits stay pending until they are saved.
    widget.languages_input.setText("en")
    assert widget.has_unsaved_changes() and not widget.unsaved_label.isHidden()
    assert widget.save()
    assert settings.get_speech_idle_seconds() == -1
    assert settings.get_transcription_languages() == "en"
    assert not widget.has_unsaved_changes() and widget.unsaved_label.isHidden()
    assert widget.save_button.toolTip() == ""
    widget.set_retention_visible(True)
    assert widget.idle_combo.currentData() == -1
    assert not widget.has_unsaved_changes()
    widget.close()


def test_hidden_retention_does_not_leave_an_empty_disclosure(app, tmp_path, resident):
    _settings, widget, _backend = _speech(tmp_path, "darwin", "apple")
    assert not widget.advanced.isHidden()
    widget.set_retention_visible(False)
    assert widget.memory_options.isHidden() and widget.advanced.isHidden()
    widget.provider_combo.setCurrentIndex(widget.provider_combo.findData("openai"))
    assert not widget.advanced.isHidden()
    assert widget.memory_options.isHidden()
    widget.provider_combo.setCurrentIndex(widget.provider_combo.findData("apple"))
    assert widget.advanced.isHidden()
    widget.set_retention_visible(True)
    assert not widget.advanced.isHidden() and not widget.memory_options.isHidden()
    widget.close()


def test_hiding_retention_does_not_interrupt_a_running_check(app, tmp_path, resident):
    _settings, widget, backend = _speech(tmp_path, "win32", "foundry")
    # Dropping an unsaved delay while hiding must not stop the check either.
    widget.idle_combo.setCurrentIndex(widget.idle_combo.findData(60))
    widget.prepare("probe")
    title = widget.status.title.text()
    assert widget.backend is backend
    widget.set_retention_visible(False)
    assert widget.idle_combo.currentData() == -1
    assert widget.backend is backend and not backend.cancelled
    assert widget.status.title.text() == title
    widget.cancel(silent=True)
    widget.close()


def test_dictation_hint_names_the_model_used_for_the_correction(app, tmp_path):
    settings = Settings(tmp_path / "hint.ini")
    widget = DictationBehaviorSettings(settings)
    assert "« Corriger »" in widget.hint.text()
    widget.set_prompt_model_hint(False)
    assert "« Corriger »" not in widget.hint.text()
    assert "moteur et le modèle des réglages Texte" in widget.hint.text()
    widget.set_prompt_model_hint(True)
    assert "« Corriger »" in widget.hint.text()
    widget.deleteLater()


# Settings navigation and shortcut rows


def test_hidden_settings_page_keeps_keys_and_moves_the_selection(app):
    panel = SettingsPanel()
    panel.add_standard_pages()
    keys = list(panel.keys)
    panel.select_page("voice")
    panel.set_page_visible("voice", False)
    assert not panel.is_page_visible("voice")
    assert panel.navigation.item(keys.index("voice")).isHidden()
    assert panel.navigation.currentRow() == keys.index("text")
    assert panel.pages.currentIndex() == keys.index("text")
    panel.select_page("app")
    assert panel.pages.currentIndex() == keys.index("app")
    # Hiding another page than the current one keeps the selection.
    panel.set_page_visible("shortcuts", False)
    assert panel.navigation.currentRow() == keys.index("app")
    panel.set_page_visible("voice", True)
    panel.set_page_visible("shortcuts", True)
    assert panel.is_page_visible("voice") and panel.is_page_visible("shortcuts")
    assert panel.keys == keys and panel.pages.count() == len(keys)
    panel.deleteLater()


def test_hidden_shortcut_row_hides_its_label_only(app):
    group = ShortcutSettings()
    main = group.add_shortcut("Menu principal", "Ctrl+²", Mock())
    voice = group.add_shortcut("Menu vocal", "Ctrl+Alt+²", Mock())
    group.set_shortcut_visible(voice, False)
    assert not group.is_shortcut_visible(voice)
    assert voice.isHidden()
    assert group.form.labelForField(group._rows[voice]).isHidden()
    assert group.is_shortcut_visible(main) and not main.isHidden()
    assert not group.form.labelForField(group._rows[main]).isHidden()
    group.set_shortcut_visible(voice, True)
    assert group.is_shortcut_visible(voice) and not voice.isHidden()
    group.deleteLater()
