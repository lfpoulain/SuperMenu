"""Windows regressions: an invalid prompt no longer empties the library."""

import json
import os
import stat

import pytest
from PySide6.QtCore import QSettings

from src.config import settings as settings_module
from src.config.settings import Settings
from supermenu_core.config.prompt_restore import (
    restore_prompt_backup,
    restore_prompt_defaults,
)
from supermenu_core.config.prompts import default_text_prompts


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module.os.path, "expanduser", lambda _path: str(tmp_path))
    instance = Settings()
    yield instance
    instance.settings.clear()
    instance.settings.sync()


def test_unknown_reasoning_mode_keeps_every_prompt_and_survives_an_edit(isolated_settings):
    library = default_text_prompts()
    library["personnel"] = {
        "name": "Personnel",
        "prompt": "Mon instruction",
        "status": "En cours",
        "hotkey": "Ctrl+Alt+P",
        "reasoning_mode": "auto",
    }
    stored = json.dumps(library)
    isolated_settings.settings.setValue("prompts", stored)

    prompts = isolated_settings.get_prompts()

    assert set(prompts) == set(library)
    assert prompts["personnel"]["reasoning_mode"] == "default"
    assert prompts["personnel"]["hotkey"] == "Ctrl+Alt+P"
    assert isolated_settings.settings.value("prompts") == stored
    backups = json.loads(isolated_settings.settings.value("prompts_backups"))
    assert [backup["value"] for backup in backups] == [stored]

    new_id = isolated_settings.add_prompt("nouveau", "Nouveau", "", "En cours")

    assert set(isolated_settings.get_prompts()) == set(library) | {new_id}
    assert isolated_settings.get_prompt("personnel")["prompt"] == "Mon instruction"


def test_unreadable_library_is_copied_before_it_is_replaced(isolated_settings):
    isolated_settings.settings.setValue("prompts", '{"corriger": ')

    assert isolated_settings.get_prompts() == {}
    isolated_settings.add_prompt("nouveau", "Nouveau", "Instruction", "En cours")

    backups = json.loads(isolated_settings.settings.value("prompts_backups"))
    assert backups[0]["value"] == '{"corriger": '


def test_valid_library_reads_keep_no_copy(isolated_settings):
    assert isolated_settings.get_prompts() == default_text_prompts()
    assert isolated_settings.get_voice_prompts()
    assert not isolated_settings.settings.contains("prompts_backups")
    assert not isolated_settings.settings.contains("voice_prompts_backups")


def test_export_with_a_draft_can_be_imported_again(isolated_settings, tmp_path):
    isolated_settings.add_prompt("brouillon", "Brouillon", "", "Configuration en cours")
    isolated_settings.add_voice_prompt(None, "Nouveau prompt vocal", "", "En cours")
    path = tmp_path / "prompts.json"

    assert isolated_settings.export_prompts(str(path))[0] is True
    success, message = isolated_settings.import_prompts(str(path))

    assert success is True, message
    assert isolated_settings.get_prompt("brouillon")["prompt"] == ""


def test_full_reset_keeps_a_copy_of_personal_prompts_only(isolated_settings):
    isolated_settings.add_prompt("perso", "Personnel", "Mon instruction", "En cours")
    personal = isolated_settings.settings.value("prompts")

    isolated_settings.reset_to_defaults()
    isolated_settings.reset_to_defaults()

    assert isolated_settings.get_prompts() == default_text_prompts()
    backups = json.loads(isolated_settings.settings.value("prompts_backups"))
    assert [backup["value"] for backup in backups] == [personal]
    assert not isolated_settings.settings.contains("voice_prompts_backups")


def _bundle(tmp_path, prompts):
    path = tmp_path / "import.json"
    path.write_text(json.dumps({"text_prompts": prompts}), encoding="utf-8")
    return str(path)


def test_prompt_bound_to_an_unknown_model_is_left_out_not_rerouted(isolated_settings):
    library = default_text_prompts()
    target = {"provider": "anthropic", "model": "claude"}
    library["local"] = {
        "name": "Local",
        "prompt": "Texte confidentiel",
        "status": "En cours",
        "model_target": target,
    }
    stored = json.dumps(library)
    isolated_settings.settings.setValue("prompts", stored)

    # The context menu runs nothing for a prompt it cannot find, so this
    # prompt never reaches the general engine (possibly OpenAI online).
    assert isolated_settings.get_prompt("local") is None
    assert set(isolated_settings.get_prompts()) == set(default_text_prompts())

    isolated_settings.add_prompt("nouveau", "Nouveau", "Instruction", "En cours")

    [kept] = json.loads(isolated_settings.settings.value("prompts_backups"))
    assert kept["value"] == stored
    assert json.loads(kept["value"])["local"]["model_target"] == target


def test_restore_then_import_two_steps_back_bring_personal_prompts_back(
    isolated_settings, tmp_path
):
    isolated_settings.add_prompt("perso", "Personnel", "Mon instruction", "En cours")
    restore_prompt_defaults(isolated_settings)
    success, message = isolated_settings.import_prompts(
        _bundle(tmp_path, {"autre": {"name": "Autre", "prompt": "x", "status": "y"}})
    )
    assert success is True, message

    restore_prompt_backup(isolated_settings)
    assert "perso" not in isolated_settings.get_prompts()
    restore_prompt_backup(isolated_settings)

    assert isolated_settings.get_prompt("perso")["prompt"] == "Mon instruction"


def test_read_only_ini_after_a_failed_startup_write_makes_the_import_fail(
    isolated_settings, tmp_path
):
    isolated_settings.sync()
    path = tmp_path / "SuperMenu.ini"
    before = isolated_settings.get_prompts()
    os.chmod(path, stat.S_IREAD)
    try:
        if os.access(path, os.W_OK):
            pytest.skip("Le compte de test peut écrire dans un fichier en lecture seule.")
        # The daily update check date is written and synced at startup.
        isolated_settings.set_last_update_check_date("2026-10-15")
        isolated_settings.sync()
        assert isolated_settings.settings.status() != QSettings.Status.NoError

        success, message = isolated_settings.import_prompts(
            _bundle(tmp_path, {"autre": {"name": "Autre", "prompt": "x", "status": "y"}})
        )

        assert success is False
        assert "n’a pas pu être enregistrée" in message
        assert isolated_settings.get_prompts() == before
        assert not isolated_settings.settings.contains("prompts_backups")
    finally:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
