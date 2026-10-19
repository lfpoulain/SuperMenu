"""Regressions: a prompt library is never hidden, emptied or lost silently."""

import json
import os
import stat
import sys
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from supermenu_core.config import prompt_restore as restore_module
from supermenu_core.config.prompt_restore import (
    prompt_backups,
    restore_prompt_backup,
    restore_prompt_defaults,
    sync_settings_or_raise,
)
from supermenu_core.config.prompt_transfer import (
    export_prompt_bundle,
    import_prompt_bundle,
)
from supermenu_core.config.prompts import (
    default_text_prompts,
    default_voice_prompts,
    normalize_prompt_collection,
    repair_prompt_collection,
)
from supermenu_core.config.voice_prompts import VoicePromptSettingsMixin
from supermenu_core.ui import prompt_restore as restore_ui


class Settings(VoicePromptSettingsMixin):
    """Text prompts stored as is, voice prompts through the shared mixin."""

    def __init__(self, path):
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)
        self.default_prompts = default_text_prompts()
        if not self.settings.contains("prompts"):
            self.settings.setValue("prompts", json.dumps(self.default_prompts))
        self.initialize_voice_prompts()

    def get_prompts(self):
        return json.loads(self.settings.value("prompts", "{}"))

    def sync(self):
        self.settings.sync()


def _prompt(name, **extra):
    return {"name": name, "prompt": f"Instruction {name}", "status": "En cours", **extra}


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def test_one_unknown_value_no_longer_hides_the_whole_library():
    raw = {
        "personnel": _prompt("Personnel", reasoning_mode="high", hotkey="Ctrl+Alt+P"),
        "futur": _prompt("Futur", model_target={"provider": "anthropic", "model": "x"}),
        "position": _prompt("Position", position="3", future_option={"kept": True}),
        "casse": ["pas", "un", "objet"],
        "intact": _prompt("Intact", position=4),
    }

    prompts, problems = repair_prompt_collection(raw)

    # A prompt bound to an unknown model is left out: running it with the
    # general engine could send the text to a service chosen for nothing.
    assert list(prompts) == ["personnel", "position", "intact"]
    assert prompts["personnel"]["reasoning_mode"] == "default"
    assert prompts["personnel"]["hotkey"] == "Ctrl+Alt+P"
    assert prompts["position"]["position"] == 999
    # Fields unknown to this version are carried along untouched.
    assert prompts["position"]["future_option"] == {"kept": True}
    assert prompts["intact"]["position"] == 4
    assert len(problems) == 4
    assert raw["personnel"]["reasoning_mode"] == "high"
    # Validation of imports and of writes stays strict.
    with pytest.raises(ValueError, match="raisonnement"):
        normalize_prompt_collection(raw)


def test_root_that_is_not_an_object_is_still_reported():
    with pytest.raises(ValueError):
        repair_prompt_collection(["not", "a", "mapping"])


def test_voice_library_with_a_future_provider_survives_reading_and_editing(tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    library = default_voice_prompts()
    target = {"provider": "anthropic", "model": "x"}
    library["resumer_vocal"]["model_target"] = target
    stored = json.dumps(library)
    settings.settings.setValue("voice_prompts", stored)

    prompts = settings.get_voice_prompts()

    # Every other prompt stays usable; the one bound to an unknown model is
    # left out instead of being sent to the general engine.
    assert set(prompts) == set(library) - {"resumer_vocal"}
    # Reading does not rewrite the stored library...
    assert settings.settings.value("voice_prompts") == stored
    # ...and a raw copy is kept before the next edit replaces it.
    backups = json.loads(settings.settings.value("voice_prompts_backups"))
    assert [backup["value"] for backup in backups] == [stored]
    settings.get_voice_prompts()
    assert len(json.loads(settings.settings.value("voice_prompts_backups"))) == 1

    identifier = settings.add_voice_prompt(None, "Nouveau", "", "En cours")

    assert set(settings.get_voice_prompts()) == (
        set(library) - {"resumer_vocal"}
    ) | {identifier}
    [kept] = json.loads(settings.settings.value("voice_prompts_backups"))
    assert json.loads(kept["value"])["resumer_vocal"]["model_target"] == target


def test_prompt_bound_to_an_unknown_model_is_never_run_by_the_general_engine():
    raw = {
        "local": _prompt("Local", model_target={"provider": "custom", "model": "m" * 600}),
        "lien": _prompt(
            "Lien",
            model_target={
                "provider": "custom",
                "model": "qwen",
                "device": "poste",
                "endpoint_type": "ollama",
            },
        ),
        "futur": _prompt("Futur", model_target={"provider": "anthropic", "model": "x"}),
        "general": _prompt("Général", model_target={}),
    }

    for voice in (False, True):
        prompts, problems = repair_prompt_collection(raw, voice=voice)

        assert list(prompts) == ["general"]
        assert prompts["general"]["model_target"] == {}
        assert len(problems) == 3
        assert all("Prompt '" in problem for problem in problems)


def test_unreadable_voice_library_is_kept_before_the_next_edit(tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    settings.settings.setValue("voice_prompts", '{"tronqué": ')

    assert settings.get_voice_prompts() == {}
    settings.add_voice_prompt(None, "Nouveau", "Instruction", "En cours")

    backups = json.loads(settings.settings.value("voice_prompts_backups"))
    assert backups[0]["value"] == '{"tronqué": '
    assert backups[0]["reason"] == "repair"


def test_export_with_drafts_can_be_imported_and_errors_name_the_prompt(tmp_path):
    source = Settings(tmp_path / "source.ini")
    text = default_text_prompts()
    text["brouillon"] = {**_prompt("Brouillon texte"), "prompt": ""}
    source.settings.setValue("prompts", json.dumps(text))
    voice_id = source.add_voice_prompt(None, "Nouveau prompt vocal", "", "En cours")
    bundle = tmp_path / "prompts.json"
    export_prompt_bundle(source, bundle)

    destination = Settings(tmp_path / "destination.ini")
    assert import_prompt_bundle(destination, bundle) == len(text) + len(
        source.get_voice_prompts()
    )
    assert destination.get_prompts()["brouillon"]["prompt"] == ""
    assert destination.get_voice_prompts()[voice_id]["prompt"] == ""

    payload = json.loads(bundle.read_text(encoding="utf-8"))
    payload["voice_prompts"][voice_id]["status"] = " "
    bundle.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Nouveau prompt vocal") as error:
        import_prompt_bundle(destination, bundle)
    assert voice_id not in str(error.value)


def test_import_accepts_a_utf8_bom(tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    bundle = tmp_path / "bom.json"
    bundle.write_text(
        json.dumps({"text_prompts": {"bom": _prompt("Avec BOM")}}),
        encoding="utf-8-sig",
    )

    assert import_prompt_bundle(settings, bundle) == 1
    assert settings.get_prompts()["bom"]["name"] == "Avec BOM"


def test_import_keeps_a_copy_that_can_be_restored(tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    personal = {"perso": _prompt("Personnel")}
    settings.settings.setValue("prompts", json.dumps(personal))
    bundle = tmp_path / "import.json"
    bundle.write_text(json.dumps({"text_prompts": {"autre": _prompt("Autre")}}), encoding="utf-8")

    import_prompt_bundle(settings, bundle)

    assert list(settings.get_prompts()) == ["autre"]
    [backup] = prompt_backups(settings)
    assert backup["count"] == 1 and backup["reason"] == "avant un import"
    assert restore_prompt_backup(settings) == 1
    assert settings.get_prompts() == personal
    # Going back keeps the imported list as a copy in turn, and the copy put
    # back stays in the history.
    kept = json.loads(settings.settings.value("prompts_backups"))
    assert [backup["reason"] for backup in kept] == ["undo", "import"]
    assert json.loads(kept[0]["value"]) == normalize_prompt_collection(
        {"autre": _prompt("Autre")}
    )
    assert json.loads(kept[1]["value"]) == personal


def test_two_restores_do_not_erase_the_copy_of_personal_prompts(tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    personal = {"perso": _prompt("Personnel", hotkey="Ctrl+Alt+P")}
    settings.settings.setValue("prompts", json.dumps(personal))

    restore_prompt_defaults(settings)
    restore_prompt_defaults(settings)

    assert json.loads(settings.settings.value("prompts_before_restore")) == personal
    assert [backup["count"] for backup in prompt_backups(settings)] == [1]

    # A restore after a few tweaks keeps both copies.
    tweaked = default_text_prompts()
    tweaked["corriger"]["prompt"] = "Ma correction"
    settings.settings.setValue("prompts", json.dumps(tweaked))
    restore_prompt_defaults(settings)

    values = [json.loads(b["value"]) for b in json.loads(settings.settings.value("prompts_backups"))]
    assert values == [tweaked, personal]


def test_backup_history_is_bounded(tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    for index in range(restore_module.BACKUP_LIMIT + 3):
        settings.settings.setValue("prompts", json.dumps({f"p{index}": _prompt(str(index))}))
        restore_prompt_defaults(settings)

    backups = json.loads(settings.settings.value("prompts_backups"))
    assert len(backups) == restore_module.BACKUP_LIMIT
    assert json.loads(backups[0]["value"]) == {
        f"p{restore_module.BACKUP_LIMIT + 2}": _prompt(str(restore_module.BACKUP_LIMIT + 2))
    }


def _import_file(tmp_path, prompts):
    bundle = tmp_path / "import.json"
    bundle.write_text(json.dumps({"text_prompts": prompts}), encoding="utf-8")
    return bundle


def test_restore_then_import_two_steps_back_bring_personal_prompts_back(tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    personal = {"perso": _prompt("Personnel")}
    settings.settings.setValue("prompts", json.dumps(personal))
    restore_prompt_defaults(settings)
    import_prompt_bundle(settings, _import_file(tmp_path, {"autre": _prompt("Autre")}))

    restore_prompt_backup(settings)
    assert set(settings.get_prompts()) == set(default_text_prompts())
    restore_prompt_backup(settings)
    assert settings.get_prompts() == personal

    # Going further back walks through every kept list, then starts again.
    seen = []
    for _ in range(3):
        restore_prompt_backup(settings)
        seen.append(sorted(settings.get_prompts())[0])
    assert seen == ["autre", "corrections_montage", "perso"]
    assert len(json.loads(settings.settings.value("prompts_backups"))) == 3


def test_cancelled_import_leaves_no_copy_identical_to_the_current_list(tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    personal = {"perso": _prompt("Personnel")}
    settings.settings.setValue("prompts", json.dumps(personal))
    restore_prompt_defaults(settings)
    current = settings.settings.value("prompts")
    import_prompt_bundle(settings, _import_file(tmp_path, {"autre": _prompt("Autre")}))
    # The macOS window puts the previous list back on a hotkey conflict.
    settings.settings.setValue(
        "prompts", json.dumps(normalize_prompt_collection(json.loads(current)))
    )

    assert restore_module.next_prompt_backup(settings) == 1
    restore_prompt_backup(settings)

    assert settings.get_prompts() == personal


def test_repair_copy_of_the_current_list_does_not_hide_an_older_copy(tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    personal = {"perso": _prompt("Personnel")}
    settings.settings.setValue("prompts", json.dumps(personal))
    restore_prompt_defaults(settings)
    # A value unknown to this version, then a read: "repair" copy of it.
    library = default_text_prompts()
    library["corriger"]["reasoning_mode"] = "auto"
    repaired = json.dumps(library)
    settings.settings.setValue("prompts", repaired)
    restore_module.backup_prompt_library(settings, "prompts", repaired, "repair")

    restore_prompt_backup(settings)
    assert settings.get_prompts() == personal

    restore_prompt_backup(settings)
    assert settings.settings.value("prompts") == repaired
    # Reading the repaired list again does not put it back first.
    restore_module.backup_prompt_library(settings, "prompts", repaired, "repair")
    restore_prompt_backup(settings)
    assert settings.get_prompts() == personal


def test_unreadable_copy_does_not_hide_older_copies(tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    personal = {"perso": _prompt("Personnel")}
    settings.settings.setValue("prompts", json.dumps(personal))
    restore_prompt_defaults(settings)
    restore_module.backup_prompt_library(settings, "prompts", '{"tronqué": ', "repair")

    assert [backup["count"] for backup in prompt_backups(settings)] == [None, 1]
    assert restore_module.next_prompt_backup(settings) == 1
    restore_prompt_backup(settings)
    assert settings.get_prompts() == personal
    counts = [backup["count"] for backup in prompt_backups(settings)]
    with pytest.raises(ValueError, match="illisible"):
        restore_prompt_backup(settings, index=counts.index(None))
    assert settings.get_prompts() == personal


def test_going_back_with_a_full_history_keeps_the_copy_put_back(tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    oldest = json.dumps({"ancien": _prompt("Ancien")})
    restore_module.backup_prompt_library(settings, "prompts", oldest, "restore")
    for index in range(restore_module.BACKUP_LIMIT - 1):
        restore_module.backup_prompt_library(
            settings, "prompts", f'{{"tronqué{index}": ', "repair"
        )
    current = json.dumps({"actuel": _prompt("Actuel")})
    settings.settings.setValue("prompts", current)

    restore_prompt_backup(settings)

    values = [
        backup["value"]
        for backup in json.loads(settings.settings.value("prompts_backups"))
    ]
    assert len(values) == restore_module.BACKUP_LIMIT
    # The current list is kept first; the oldest unreadable copy makes room.
    assert values[0] == current
    assert values[-1] == oldest
    assert '{"tronqué0": ' not in values
    assert settings.settings.value("prompts") == oldest


def test_no_copy_left_to_go_back_to_is_reported(tmp_path):
    settings = Settings(tmp_path / "settings.ini")
    with pytest.raises(ValueError, match="Aucune autre copie"):
        restore_prompt_backup(settings)


class FailingStore(QSettings):
    """A store whose file refuses writes, as QSettings reports it."""

    failing = False

    def status(self):
        if self.failing:
            return QSettings.Status.AccessError
        return super().status()


def _failing_settings(path):
    settings = Settings(path)
    store = FailingStore(str(path), QSettings.Format.IniFormat)
    settings.settings = store

    def sync():
        store.failing = True
        store.sync()

    settings.sync = sync
    return settings, store


def test_import_reports_a_refused_write_and_restores_previous_values(tmp_path):
    settings, store = _failing_settings(tmp_path / "settings.ini")
    before = store.value("prompts")
    bundle = tmp_path / "import.json"
    bundle.write_text(json.dumps({"text_prompts": {"autre": _prompt("Autre")}}), encoding="utf-8")

    with pytest.raises(OSError, match="n’a pas pu être enregistrée"):
        import_prompt_bundle(settings, bundle)

    assert store.value("prompts") == before
    assert store.value("prompts_backups") is None


def test_restore_reports_a_refused_write_and_restores_previous_values(tmp_path):
    settings, store = _failing_settings(tmp_path / "settings.ini")
    store.setValue("prompts", json.dumps({"perso": _prompt("Personnel")}))
    before = store.value("prompts")

    with pytest.raises(OSError):
        restore_prompt_defaults(settings)

    assert store.value("prompts") == before
    assert store.value("prompts_before_restore") is None
    assert store.value("prompts_backups") is None


def test_an_older_write_error_does_not_block_later_operations():
    class Store:
        def status(self):
            return QSettings.Status.AccessError

    sync_settings_or_raise(SimpleNamespace(settings=Store(), sync=lambda: None))
    sync_settings_or_raise(SimpleNamespace(settings=object(), sync=lambda: None))


class StuckStore(QSettings):
    """A store whose status keeps the error of an earlier write, as Qt does."""

    writable = True

    def status(self):
        return QSettings.Status.AccessError

    def sync(self):
        if self.writable:
            super().sync()


def _stuck_settings(path):
    settings = Settings(path)
    settings.sync()
    store = StuckStore(str(path), QSettings.Format.IniFormat)
    settings.settings = store
    return settings, store


def test_an_earlier_write_error_does_not_hide_a_new_failure(tmp_path):
    settings, store = _stuck_settings(tmp_path / "settings.ini")
    store.writable = False
    before = store.value("prompts")

    with pytest.raises(OSError, match="n’a pas pu être enregistrée"):
        import_prompt_bundle(settings, _import_file(tmp_path, {"autre": _prompt("Autre")}))

    assert store.value("prompts") == before
    assert store.value("prompts_backups") is None


def test_an_earlier_write_error_does_not_block_a_successful_write(tmp_path):
    path = tmp_path / "settings.ini"
    settings, _store = _stuck_settings(path)

    assert import_prompt_bundle(
        settings, _import_file(tmp_path, {"autre": _prompt("Autre")})
    ) == 1
    assert "autre" in path.read_text(encoding="utf-8")


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Attribut lecture seule de Windows ; la logique est couverte par FailingStore.",
)
def test_read_only_configuration_file_makes_the_import_fail(tmp_path):
    path = tmp_path / "settings.ini"
    settings = Settings(path)
    settings.sync()
    before = settings.settings.value("prompts")
    bundle = tmp_path / "import.json"
    bundle.write_text(json.dumps({"text_prompts": {"autre": _prompt("Autre")}}), encoding="utf-8")
    os.chmod(path, stat.S_IREAD)
    try:
        if os.access(path, os.W_OK):
            pytest.skip("Le compte de test peut écrire dans un fichier en lecture seule.")
        with pytest.raises(OSError):
            import_prompt_bundle(settings, bundle)
        assert settings.settings.value("prompts") == before
    finally:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Attribut lecture seule de Windows ; la logique est couverte par StuckStore.",
)
def test_read_only_file_after_an_earlier_failed_write_makes_the_import_fail(tmp_path):
    path = tmp_path / "settings.ini"
    settings = Settings(path)
    settings.sync()
    bundle = _import_file(tmp_path, {"autre": _prompt("Autre")})
    os.chmod(path, stat.S_IREAD)
    try:
        if os.access(path, os.W_OK):
            pytest.skip("Le compte de test peut écrire dans un fichier en lecture seule.")
        # At startup the daily update check date is written first.
        settings.settings.setValue("last_update_check_date", "2026-10-15")
        settings.sync()
        assert settings.settings.status() != QSettings.Status.NoError
        before = settings.settings.value("prompts")

        with pytest.raises(OSError):
            import_prompt_bundle(settings, bundle)

        assert settings.settings.value("prompts") == before
        assert settings.settings.value("prompts_backups") is None
    finally:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


def test_previous_library_can_be_brought_back_from_the_editor(tmp_path, qt_app):
    settings = Settings(tmp_path / "settings.ini")
    personal = {"perso": _prompt("Personnel")}
    settings.settings.setValue("prompts", json.dumps(personal))
    owner, refreshed = QWidget(), []

    empty = restore_ui.restore_previous_library(owner, settings, lambda: refreshed.append(1))
    assert empty.icon() == QMessageBox.Icon.Information
    empty.done(QMessageBox.StandardButton.Ok)
    qt_app.processEvents()

    restore_prompt_defaults(settings)
    box = restore_ui.restore_previous_library(owner, settings, lambda: refreshed.append(1))
    assert "1 prompt(s)" in box.text()
    box.done(QMessageBox.StandardButton.Yes)
    qt_app.processEvents()

    assert settings.get_prompts() == personal
    assert refreshed == [1]
    owner.close()


def test_editor_offers_the_copy_that_differs_from_the_current_list(tmp_path, qt_app):
    settings = Settings(tmp_path / "settings.ini")
    personal = {"perso": _prompt("Personnel")}
    settings.settings.setValue("prompts", json.dumps(personal))
    restore_prompt_defaults(settings)
    current = settings.settings.value("prompts")
    import_prompt_bundle(settings, _import_file(tmp_path, {"autre": _prompt("Autre")}))
    settings.settings.setValue("prompts", current)
    owner, refreshed = QWidget(), []

    box = restore_ui.restore_previous_library(owner, settings, lambda: refreshed.append(1))
    assert "avant la restauration" in box.text() and "1 prompt(s)" in box.text()
    box.done(QMessageBox.StandardButton.Yes)
    qt_app.processEvents()
    assert settings.get_prompts() == personal
    assert refreshed == [1]

    # With only copies of the current list, nothing is offered.
    settings.settings.setValue("prompts_backups", json.dumps([
        {"saved_at": "2026-10-15T10:00:00", "reason": "import", "value": current},
    ]))
    settings.settings.setValue("prompts", current)
    info = restore_ui.restore_previous_library(owner, settings, lambda: refreshed.append(1))
    assert info.icon() == QMessageBox.Icon.Information
    assert "identiques" in info.text()
    info.done(QMessageBox.StandardButton.Ok)
    qt_app.processEvents()
    assert refreshed == [1]
    owner.close()


def test_failed_restore_is_reported_instead_of_escaping_the_dialog(
    tmp_path, qt_app, monkeypatch
):
    settings = Settings(tmp_path / "settings.ini")
    owner, refreshed, shown = QWidget(), [], []

    def fail(*_args, **_kwargs):
        raise OSError("disque plein")

    monkeypatch.setattr(restore_ui, "restore_prompt_defaults", fail)
    monkeypatch.setattr(
        restore_ui, "_notify", lambda parent, icon, title, message: shown.append(message)
    )
    box = restore_ui.restore_library(owner, settings, lambda: refreshed.append(1))
    box.done(QMessageBox.StandardButton.Yes)
    qt_app.processEvents()

    assert shown == ["disque plein"]
    assert refreshed == []
    owner.close()
