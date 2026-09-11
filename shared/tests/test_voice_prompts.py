import json

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from supermenu_core.config.prompt_transfer import (
    export_prompt_bundle,
    import_prompt_bundle,
)
from supermenu_core.config.voice_prompts import (
    VoicePromptSettingsMixin,
    compose_voice_prompt,
)
from supermenu_core.ui.controls import Menu
from supermenu_core.ui.voice_menu import populate_voice_menu
from supermenu_core.ui.voice_prompt_editor import VoicePromptEditor


class Settings(VoicePromptSettingsMixin):
    def __init__(self, path):
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)
        self.initialize_voice_prompts()

    def get_prompts(self):
        return json.loads(self.settings.value("prompts", "{}"))

    def sync(self):
        self.settings.sync()


@pytest.mark.parametrize(
    "order",
    [
        "prompt_transcription_selected",
        "prompt_selected_transcription",
        "selected_prompt_transcription",
        "transcription_prompt_selected",
        "transcription_selected_prompt",
        "selected_transcription_prompt",
    ],
)
def test_voice_request_respects_all_six_orders_and_explicit_selection_opt_in(order):
    prompt = {
        "prompt": "Instruction",
        "prompt_order": order,
        "include_selected_text": True,
    }
    request = compose_voice_prompt(prompt, "Dictée", "Sélection")
    assert (
        request.count("Instruction")
        == request.count("Texte transcrit:")
        == request.count("Texte sélectionné:")
        == 1
    )
    tokens = {
        "prompt": "Instruction",
        "transcription": "Texte transcrit: Dictée",
        "selected": "Texte sélectionné: Sélection",
    }
    assert [request.index(tokens[key]) for key in order.split("_")] == sorted(
        request.index(token) for token in tokens.values()
    )
    prompt["include_selected_text"] = False
    assert (
        compose_voice_prompt(prompt, "Dictée", "Texte privé") == "Instruction\n\nDictée"
    )
    assert compose_voice_prompt(prompt, "Dictée") == "Instruction\n\nDictée"


def test_existing_voice_library_survives_initialization_and_deleting_all(tmp_path):
    path = tmp_path / "settings.ini"
    settings = Settings(path)
    identifier = settings.add_voice_prompt(
        "custom",
        "Mon prompt",
        "Reformule",
        "En cours",
        True,
        7,
        True,
        "selected_transcription_prompt",
    )
    saved = settings.get_voice_prompts()
    assert Settings(path).get_voice_prompts() == saved
    assert Settings(path).get_voice_prompt(identifier)["position"] == 7
    settings.set_voice_prompts({})
    assert Settings(path).get_voice_prompts() == {}


def test_bundle_round_trip_preserves_voice_options_and_old_mac_import_keeps_voice(
    tmp_path,
):
    source = Settings(tmp_path / "source.ini")
    source.update_voice_prompt(
        "resumer_vocal",
        "Résumé",
        "Résume",
        "Résumé…",
        True,
        15,
        True,
        "selected_prompt_transcription",
    )
    source.settings.setValue(
        "prompts",
        json.dumps(
            {
                "text": {
                    "name": "Texte",
                    "prompt": "Corrige",
                    "status": "En cours",
                    "hotkey": "",
                    "insert_directly": False,
                    "position": 1,
                }
            }
        ),
    )
    source.sync()
    destination = Settings(tmp_path / "destination.ini")
    bundle = tmp_path / "prompts.json"
    export_prompt_bundle(source, bundle)
    assert import_prompt_bundle(destination, bundle) == 4
    assert destination.get_voice_prompts() == source.get_voice_prompts()
    assert destination.get_prompts() == source.get_prompts()
    bundle.write_text(json.dumps({"prompts": source.get_prompts()}), encoding="utf-8")
    assert import_prompt_bundle(destination, bundle) == 1
    assert destination.get_voice_prompts() == source.get_voice_prompts()


def test_invalid_voice_import_does_not_change_either_collection(tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    before = settings.get_voice_prompts()
    payload = {
        "text_prompts": {
            "text": {"name": "Texte", "prompt": "Corrige", "status": "En cours"}
        },
        "voice_prompts": {
            "bad": {
                "name": "Voix",
                "prompt": "Résume",
                "status": "En cours",
                "prompt_order": "invalid",
            }
        },
    }
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        import_prompt_bundle(settings, path)
    assert settings.get_prompts() == {}
    assert settings.get_voice_prompts() == before


def test_shared_editor_saves_runs_reorders_and_preserves_an_empty_library(
    tmp_path, monkeypatch
):
    app = QApplication.instance() or QApplication([])
    settings = Settings(tmp_path / "settings.ini")
    editor = VoicePromptEditor(settings)
    runs = []
    editor.run_requested.connect(runs.append)
    editor.add_button.click()
    identifier = editor._current_id
    editor.run_button.click()
    assert not runs and editor.feedback.text()
    editor.name_input.setText("Répondre")
    editor.instruction_input.setPlainText("Rédige ma réponse")
    editor.include_selected.setChecked(True)
    editor.order_combo.setCurrentIndex(
        editor.order_combo.findData("selected_transcription_prompt")
    )
    editor.insert_directly.setChecked(True)
    editor.run_button.click()
    assert runs == [identifier]
    saved = settings.get_voice_prompt(identifier)
    assert saved["include_selected_text"] and saved["insert_directly"]
    assert saved["prompt_order"] == "selected_transcription_prompt"
    # Reorder the item without changing its identity or other preferences.
    item = editor.prompt_list.takeItem(editor.prompt_list.currentRow())
    editor.prompt_list.insertItem(0, item)
    editor.prompt_list.setCurrentItem(item)
    editor._reorder()
    assert settings.get_voice_prompt(identifier)["position"] == 10
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes
    )
    settings.set_voice_prompts({identifier: settings.get_voice_prompt(identifier)})
    editor.reload(identifier)
    editor.delete_button.click()
    assert settings.get_voice_prompts() == {}
    assert not editor.save_button.isEnabled() and not editor.run_button.isEnabled()
    editor.add_button.click()
    assert editor.form.isEnabled()
    editor.close()
    assert app is not None


def test_shared_voice_menu_keeps_native_action_payloads_and_order(tmp_path):
    app = QApplication.instance() or QApplication([])
    settings = Settings(tmp_path / "settings.ini")
    menu = Menu()
    target = object()
    populate_voice_menu(
        menu, settings.get_voice_prompts(), lambda kind, key: (kind, key, target)
    )
    actions = [action for action in menu.actions() if not action.isSeparator()]
    assert [action.data()[:2] for action in actions] == [
        ("voice", None),
        ("voice_prompt", "decrire_reponse"),
        ("voice_prompt", "resumer_vocal"),
        ("voice_prompt", "traduire_en_anglais_vocal"),
        ("voice_godmode", None),
    ]
    assert all(action.data()[2] is target for action in actions)
    assert actions[1].text() == "Décrire une réponse"
    assert app is not None


def test_reasoning_modes_validate_imports_without_changing_old_prompts():
    from supermenu_core.config.prompts import normalize_prompt_collection
    legacy = {"test": {"name": "Test", "prompt": "Teste", "status": "Test", "position": 1, "insert_directly": False, "hotkey": ""}}
    assert normalize_prompt_collection(legacy) == legacy
    for mode in ("default", "on", "off"):
        candidate = {"test": {**legacy["test"], "reasoning_mode": mode}}
        assert normalize_prompt_collection(candidate)["test"]["reasoning_mode"] == mode
    for bad in (True, None, "maximum", {}):
        with pytest.raises(ValueError, match="raisonnement"):
            normalize_prompt_collection({"test": {**legacy["test"], "reasoning_mode": bad}})
