import json

import pytest
from PySide6.QtCore import QSettings

from supermenu_core.config.prompts import default_text_prompts
from supermenu_core.config.text_prompts import TextPromptSettingsMixin


class Settings(TextPromptSettingsMixin):
    def __init__(self, path, prompts=None, *, fall_back=False):
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)
        self.default_prompts = default_text_prompts()
        self.TEXT_PROMPTS_FALL_BACK_TO_DEFAULTS = fall_back
        if prompts is not None:
            self.settings.setValue("prompts", json.dumps(prompts))

    def sync(self):
        self.settings.sync()


def _prompt(name, hotkey=""):
    return {"name": name, "prompt": "Instruction", "status": "En cours", "hotkey": hotkey}


@pytest.fixture
def make(tmp_path):
    return lambda *args, **kwargs: Settings(tmp_path / "settings.ini", *args, **kwargs)


@pytest.mark.parametrize("fall_back", [False, True])
@pytest.mark.parametrize("stored", ["{}", "[]", "pas du json"])
def test_empty_or_unreadable_library_follows_the_platform_policy(make, stored, fall_back):
    settings = make(fall_back=fall_back)
    settings.settings.setValue("prompts", stored)

    expected = default_text_prompts() if fall_back else {}
    assert settings.get_prompts() == expected
    assert settings.settings.value("prompts") == stored


def test_a_bad_entry_is_left_out_and_the_library_kept_in_a_copy(make):
    unknown_model = {"provider": "custom", "model": "m" * 600}
    library = {"bon": _prompt("Bon"), "mauvais": {**_prompt("Mauvais"), "model_target": unknown_model}}
    settings = make(library)
    stored = settings.settings.value("prompts")

    assert set(settings.get_prompts()) == {"bon"}
    assert settings.settings.value("prompts") == stored
    backups = json.loads(settings.settings.value("prompts_backups"))
    assert json.loads(backups[0]["value"]) == library


def test_a_valid_library_that_migrates_is_stored_back(make):
    settings = make({"corriger": {"name": "Corriger", "prompt": "Corrige", "status": "En cours"}})

    assert settings.get_prompt("corriger")["hotkey"] == ""
    assert json.loads(settings.settings.value("prompts"))["corriger"]["hotkey"] == ""
    assert not settings.settings.contains("prompts_backups")


def test_writes_are_validated_and_keep_accents_readable(make):
    settings = make({})

    settings.set_prompts({"resume": _prompt("Résumé")})
    assert "Résumé" in settings.settings.value("prompts")
    with pytest.raises(ValueError):
        settings.set_prompts({"broken": {**_prompt("Cassé"), "position": "3"}})
    with pytest.raises(ValueError, match="plusieurs prompts"):
        settings.set_prompts({"a": _prompt("A", "Ctrl+1"), "b": _prompt("B", "ctrl+1")})
    assert set(settings.get_prompts()) == {"resume"}


def test_update_keeps_position_and_model_and_creates_missing_prompts(make):
    target = {"provider": "openai", "model": "gpt-5.6-luna"}
    settings = make({"corriger": {**_prompt("Corriger"), "position": 40, "model_target": target}})

    settings.update_prompt("corriger", "Corriger", "Nouvelle", "En cours")
    settings.update_prompt("nouveau", "", "", "")

    corrected = settings.get_prompt("corriger")
    assert corrected["position"] == 40 and corrected["prompt"] == "Nouvelle"
    assert corrected["model_target"] == target
    created = settings.get_prompt("nouveau")
    assert (created["name"], created["status"], created["position"]) == (
        "nouveau", "Traitement en cours…", 999
    )


def test_add_suffixes_taken_ids_and_names_generated_ones(make):
    settings = make({"draft": _prompt("Brouillon")})

    assert settings.add_prompt("draft", "Copie", "", "En cours") == "draft_1"
    assert settings.add_prompt("draft", "Copie", "", "En cours") == "draft_2"
    generated = settings.add_prompt(None, "", "", "")
    assert len(generated) == 32 and settings.get_prompt(generated)["name"] == "Nouveau prompt"


def test_shared_hotkeys_are_refused_and_the_platform_may_name_the_owner(make):
    settings = make({"first": _prompt("Premier", "Ctrl+Alt+1")})

    with pytest.raises(ValueError, match="plusieurs prompts"):
        settings.add_prompt("second", "Second", "", "En cours", hotkey="ctrl+alt+1")

    checked = []
    settings._check_prompt_hotkey = lambda prompts, hotkey, prompt_id: checked.append(
        (sorted(prompts), hotkey, prompt_id)
    )
    settings.update_prompt("first", "Premier", "Instruction", "En cours", hotkey=" Ctrl+Alt+2 ")
    assert checked == [(["first"], "Ctrl+Alt+2", "first")]
    assert settings.get_prompt("first")["hotkey"] == "Ctrl+Alt+2"


def test_delete_reports_whether_a_prompt_was_removed(make):
    settings = make({"first": _prompt("Premier")})

    assert settings.delete_prompt("missing") is False
    assert settings.delete_prompt("first") is True
    assert settings.get_prompts() == {}
