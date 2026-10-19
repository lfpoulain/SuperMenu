"""macOS regressions: prompt libraries are repaired, never replaced silently."""

import json

import pytest

from src.config.settings import Settings
from supermenu_core.config.prompt_restore import (
    next_prompt_backup,
    restore_prompt_backup,
    restore_prompt_defaults,
)
from supermenu_core.config.prompts import default_text_prompts


def _personal(**extra):
    return {
        "name": "Personnel",
        "prompt": "Mon instruction",
        "status": "En cours",
        **extra,
    }


def test_unknown_value_keeps_personal_prompt_through_a_delete(tmp_path):
    settings = Settings(config_path=str(tmp_path / "settings.ini"))
    library = default_text_prompts()
    library["personnel"] = _personal(reasoning_mode="high")
    settings.settings.setValue("prompts", json.dumps(library))

    prompts = settings.get_prompts()

    assert set(prompts) == set(library)
    assert prompts["personnel"]["reasoning_mode"] == "default"
    settings.delete_prompt("corriger")
    stored = json.loads(settings.settings.value("prompts"))
    assert "personnel" in stored and "corriger" not in stored
    backups = json.loads(settings.settings.value("prompts_backups"))
    assert json.loads(backups[0]["value"]) == library


def test_invalid_write_is_refused_instead_of_storing_an_empty_library(tmp_path):
    settings = Settings(config_path=str(tmp_path / "settings.ini"))
    before = settings.get_prompts()
    invalid = dict(before)
    invalid["corriger"] = {**before["corriger"], "position": "3"}

    with pytest.raises(ValueError, match="position"):
        settings.set_prompts(invalid)

    assert settings.get_prompts() == before
    assert json.loads(settings.settings.value("prompts")) == before


def test_duplicate_hotkey_is_refused_without_clearing_the_other_prompt(tmp_path):
    settings = Settings(config_path=str(tmp_path / "settings.ini"))
    settings.update_prompt(
        "corriger", "Corriger", "Corrige", "Correction", hotkey="Cmd+Shift+K"
    )

    with pytest.raises(ValueError, match="plusieurs prompts"):
        settings.update_prompt(
            "reformuler", "Reformuler", "Reformule", "En cours", hotkey="cmd+shift+k"
        )

    assert settings.get_prompt("corriger")["hotkey"] == "Cmd+Shift+K"
    assert settings.get_prompt("reformuler")["hotkey"] == ""


def test_prompt_bound_to_an_unknown_model_is_left_out_not_rerouted(tmp_path):
    settings = Settings(config_path=str(tmp_path / "settings.ini"))
    library = default_text_prompts()
    library["local"] = _personal(
        model_target={"provider": "custom", "model": "m" * 600}
    )
    settings.settings.setValue("prompts", json.dumps(library))

    assert settings.get_prompt("local") is None
    assert set(settings.get_prompts()) == set(default_text_prompts())
    backups = json.loads(settings.settings.value("prompts_backups"))
    assert json.loads(backups[0]["value"]) == library


def test_cancelled_import_then_going_back_brings_personal_prompts_back(tmp_path):
    settings = Settings(config_path=str(tmp_path / "settings.ini"))
    settings.add_prompt("perso", "Perso", "p", "s", hotkey="Cmd+Shift+P")
    settings.sync()
    restore_prompt_defaults(settings)
    bundle = tmp_path / "import.json"
    bundle.write_text(
        json.dumps({"text_prompts": {"autre": _personal(hotkey="Cmd+Shift+Space")}}),
        encoding="utf-8",
    )
    # main_window.import_prompts puts the previous lists back on a conflict.
    previous_prompts = settings.get_prompts()
    previous_voice = settings.get_voice_prompts()
    settings.import_prompts(str(bundle))
    settings.set_prompts(previous_prompts)
    settings.set_voice_prompts(previous_voice)
    settings.sync()

    # The copy made before the import equals the current list: skipped.
    assert next_prompt_backup(settings) == 1
    restore_prompt_backup(settings)

    assert settings.get_prompt("perso")["hotkey"] == "Cmd+Shift+P"
