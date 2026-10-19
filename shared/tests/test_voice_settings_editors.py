"""Regressions for the voice settings page and the voice prompt editor."""

import json

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QLineEdit

from supermenu_core.audio.backends import SpeechBackend
from supermenu_core.audio.settings import SpeechSettingsMixin
from supermenu_core.config.voice_prompts import VoicePromptSettingsMixin
from supermenu_core.ui.confirmations import UnsavedChangesDialog
from supermenu_core.ui.speech_settings import SpeechSettingsWidget
from supermenu_core.ui.voice_prompt_editor import VoicePromptEditor


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def no_microphones(monkeypatch):
    monkeypatch.setattr("supermenu_core.ui.speech_settings.microphones", lambda: [])


class FakeBackend(SpeechBackend):
    def __init__(self):
        super().__init__()
        self.cancelled = False

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True


class SpeechSettings(SpeechSettingsMixin):
    def __init__(self, path):
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)
        self.key = ""

    def get_api_key(self):
        return self.key

    def set_api_key(self, key):
        self.key = key

    def sync(self):
        self.settings.sync()


def _speech_widget(tmp_path, backend):
    settings = SpeechSettings(tmp_path / "speech.ini")
    widget = SpeechSettingsWidget(settings, lambda _options: backend, platform="win32")
    # Same mirror as both main windows: the text page shares its key.
    text_page_key = QLineEdit()
    text_page_key.textChanged.connect(widget.api_key_input.setText)
    return settings, widget, text_page_key


def test_text_page_key_does_not_cancel_a_local_model_download(app, tmp_path):
    backend = FakeBackend()
    _settings, widget, text_page_key = _speech_widget(tmp_path, backend)
    widget.provider_combo.setCurrentIndex(widget.provider_combo.findData("foundry"))
    widget.prepare("download")
    assert widget.backend is backend
    assert not widget.api_key_input.isEnabled()
    text_page_key.setText("sk-new")
    assert widget.api_key_input.text() == "sk-new"
    assert not backend.cancelled
    assert widget.backend is backend
    assert widget.status.title.text() == "Installation du modèle vocal…"
    widget.cancel(silent=True)
    assert widget.api_key_input.isEnabled()


def test_openai_key_change_still_requires_a_new_check(app, tmp_path):
    backend = FakeBackend()
    _settings, widget, text_page_key = _speech_widget(tmp_path, backend)
    assert widget.provider_combo.currentData() == "openai"
    widget.prepare("probe")
    text_page_key.setText("sk-other")
    assert backend.cancelled
    assert widget.backend is None
    assert widget.status.title.text() == "Moteur vocal à vérifier"


def test_voice_page_reports_changes_until_they_are_saved(app, tmp_path):
    settings, widget, _text_page_key = _speech_widget(tmp_path, FakeBackend())
    assert not widget.has_unsaved_changes()
    assert widget.unsaved_label.isHidden()
    widget.provider_combo.setCurrentIndex(widget.provider_combo.findData("foundry"))
    assert widget.has_unsaved_changes()
    assert not widget.unsaved_label.isHidden()
    assert settings.get_speech_provider() == "openai"
    assert widget.save()
    assert settings.get_speech_provider() == "foundry"
    assert not widget.has_unsaved_changes()
    assert widget.unsaved_label.isHidden()
    widget.keywords_input.setText("SuperMenu")
    assert not widget.unsaved_label.isHidden()
    widget.keywords_input.setText("")
    assert widget.unsaved_label.isHidden()


def test_voice_page_reports_an_unsaved_openai_key(app, tmp_path):
    settings = SpeechSettings(tmp_path / "speech.ini")
    settings.key = "sk-old"
    widget = SpeechSettingsWidget(
        settings, lambda _options: FakeBackend(), platform="win32"
    )
    assert widget.provider_combo.currentData() == "openai"
    assert not widget.has_unsaved_changes()
    widget.api_key_input.setText("sk-new")
    assert widget.has_unsaved_changes()
    assert not widget.unsaved_label.isHidden()
    assert settings.get_api_key() == "sk-old"
    assert widget.save()
    assert settings.get_api_key() == "sk-new"
    assert widget.unsaved_label.isHidden()
    # A local engine does not save the key, so editing it is not a change.
    widget.provider_combo.setCurrentIndex(widget.provider_combo.findData("foundry"))
    assert widget.save()
    widget.api_key_input.setText("sk-other")
    assert not widget.has_unsaved_changes()
    assert widget.unsaved_label.isHidden()
    widget.close()


def test_key_saved_by_the_text_page_clears_the_notice_on_show(app, tmp_path):
    settings, widget, text_page_key = _speech_widget(tmp_path, FakeBackend())
    text_page_key.setText("sk-text")
    assert not widget.unsaved_label.isHidden()
    # The text page stores the shared key while the voice page is hidden.
    settings.set_api_key("sk-text")
    widget.show()
    assert widget.unsaved_label.isHidden()
    widget.close()


def test_saved_value_unavailable_here_is_not_reported_as_a_change(app, tmp_path):
    settings = SpeechSettings(tmp_path / "speech.ini")
    settings.set_speech_provider("apple")
    widget = SpeechSettingsWidget(
        settings, lambda _options: FakeBackend(), platform="win32"
    )
    assert widget.provider_combo.currentData() == "openai"
    assert not widget.has_unsaved_changes()
    assert widget.unsaved_label.isHidden()


class VoiceSettings(VoicePromptSettingsMixin):
    def __init__(self, path):
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)
        self.initialize_voice_prompts()

    def get_prompts(self):
        return json.loads(self.settings.value("prompts", "{}"))

    def sync(self):
        self.settings.sync()


class LinkVoiceSettings(VoiceSettings):
    """Text settings pointing at an LM Studio server with LM Link devices."""

    endpoint_type = "lmstudio"

    def get_model(self):
        return "gpt-5-mini"

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


def _editor(tmp_path):
    settings = VoiceSettings(tmp_path / "voice.ini")
    editor = VoicePromptEditor(settings)
    first = editor.prompt_list.item(0)
    second = editor.prompt_list.item(1)
    return settings, editor, first, second


def _identifier(item):
    return item.data(Qt.ItemDataRole.UserRole)


def _pending_dialog(app, editor):
    app.processEvents()
    dialog = getattr(editor, "_confirmation_dialog", None)
    assert isinstance(dialog, UnsavedChangesDialog)
    return dialog


def test_switching_without_edits_needs_no_confirmation(app, tmp_path):
    settings, editor, _first, second = _editor(tmp_path)
    editor.prompt_list.setCurrentItem(second)
    app.processEvents()
    assert editor._current_id == _identifier(second)
    assert editor.instruction_input.toPlainText() == settings.get_voice_prompt(
        _identifier(second)
    )["prompt"]
    assert getattr(editor, "_confirmation_dialog", None) is None
    editor.close()


def test_edited_prompt_is_kept_when_switching_is_cancelled(app, tmp_path):
    settings, editor, first, second = _editor(tmp_path)
    stored = settings.get_voice_prompt(_identifier(first))["prompt"]
    editor.instruction_input.setPlainText("Une longue instruction en cours")
    editor.prompt_list.setCurrentItem(second)
    dialog = _pending_dialog(app, editor)
    assert editor.prompt_list.currentItem() is first
    dialog.cancel_button.click()
    app.processEvents()
    assert editor._current_id == _identifier(first)
    assert editor.prompt_list.currentItem() is first
    assert editor.instruction_input.toPlainText() == "Une longue instruction en cours"
    assert settings.get_voice_prompt(_identifier(first))["prompt"] == stored
    editor.close()


def test_edited_prompt_can_be_saved_before_switching(app, tmp_path):
    settings, editor, first, second = _editor(tmp_path)
    editor.instruction_input.setPlainText("Instruction enregistrée")
    editor.prompt_list.setCurrentItem(second)
    _pending_dialog(app, editor).save_button.click()
    app.processEvents()
    assert settings.get_voice_prompt(_identifier(first))["prompt"] == (
        "Instruction enregistrée"
    )
    assert editor._current_id == _identifier(second)
    assert editor.prompt_list.currentItem() is second
    editor.close()


def test_edited_prompt_can_be_discarded_before_switching(app, tmp_path):
    settings, editor, first, second = _editor(tmp_path)
    stored = settings.get_voice_prompt(_identifier(first))["prompt"]
    editor.instruction_input.setPlainText("Brouillon abandonné")
    editor.prompt_list.setCurrentItem(second)
    _pending_dialog(app, editor).discard_button.click()
    app.processEvents()
    assert editor._current_id == _identifier(second)
    assert settings.get_voice_prompt(_identifier(first))["prompt"] == stored
    assert not editor.has_unsaved_changes()
    editor.close()


def test_invalid_edit_stays_selected_when_saving_fails(app, tmp_path):
    _settings, editor, first, second = _editor(tmp_path)
    editor.name_input.setText("")
    editor.prompt_list.setCurrentItem(second)
    _pending_dialog(app, editor).save_button.click()
    app.processEvents()
    assert editor._current_id == _identifier(first)
    assert editor.feedback.text() == "Renseignez le nom et les instructions du prompt."
    editor.close()


def test_adding_a_prompt_asks_before_replacing_edits(app, tmp_path):
    settings, editor, first, _second = _editor(tmp_path)
    count = len(settings.get_voice_prompts())
    editor.instruction_input.setPlainText("Brouillon")
    editor.add_prompt()
    dialog = _pending_dialog(app, editor)
    dialog.cancel_button.click()
    app.processEvents()
    assert len(settings.get_voice_prompts()) == count
    assert editor._current_id == _identifier(first)
    editor.add_prompt()
    _pending_dialog(app, editor).discard_button.click()
    app.processEvents()
    assert len(settings.get_voice_prompts()) == count + 1
    assert editor.name_input.text() == "Nouveau prompt vocal"
    editor.close()


def test_text_server_change_alone_is_not_an_unsaved_edit(app, tmp_path):
    settings = LinkVoiceSettings(tmp_path / "voice.ini")
    prompts = settings.get_voice_prompts()
    first_id = min(prompts, key=lambda key: prompts[key].get("position", 999))
    prompts[first_id]["model_target"] = {
        "provider": "custom",
        "model": "qwen",
        "device": "poste-1",
        "device_name": "Bureau",
    }
    settings.set_voice_prompts(prompts)
    editor = VoicePromptEditor(settings)
    assert editor._current_id == first_id
    assert not editor.has_unsaved_changes()
    # The Text page switches to Ollama: the LM Link device is no longer valid,
    # yet nothing was edited in this prompt.
    settings.endpoint_type = "ollama"
    assert not editor.has_unsaved_changes()
    provider = editor.model_choice.provider
    provider.setCurrentIndex(provider.findData("default"))
    assert editor.has_unsaved_changes()
    provider.setCurrentIndex(provider.findData("custom"))
    assert not editor.has_unsaved_changes()
    second = editor.prompt_list.item(1)
    editor.prompt_list.setCurrentItem(second)
    app.processEvents()
    assert getattr(editor, "_confirmation_dialog", None) is None
    assert editor._current_id == _identifier(second)
    editor.close()


def test_explicit_reload_replaces_edits_without_asking(app, tmp_path):
    _settings, editor, first, _second = _editor(tmp_path)
    editor.instruction_input.setPlainText("Brouillon")
    editor.reload(_identifier(first))
    app.processEvents()
    assert getattr(editor, "_confirmation_dialog", None) is None
    assert not editor.has_unsaved_changes()
    editor.close()
