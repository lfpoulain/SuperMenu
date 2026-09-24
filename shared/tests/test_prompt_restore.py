import json
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox

from supermenu_core.config.prompt_restore import restore_prompt_defaults
from supermenu_core.ui.confirmations import confirm_action
from supermenu_core.ui.prompt_restore import restore_library


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.parametrize("voice", [False, True])
def test_restore_preserves_settings_and_other_library_and_saves_backup(tmp_path, voice):
    store = QSettings(str(tmp_path / "restore.ini"), QSettings.Format.IniFormat)
    custom = {
        "custom": {"name": "Personnel", "prompt": "Privé", "hotkey": "Ctrl+Alt+C"}
    }
    for key in ("prompts", "voice_prompts"):
        store.setValue(key, json.dumps(custom))
    store.setValue("ai_provider", "foundry")
    store.setValue("dictation_hotkey", "Ctrl+Alt+D")
    settings = SimpleNamespace(
        settings=store,
        sync=store.sync,
        default_prompts={"corriger": {"name": "Corriger"}},
        default_voice_prompts={"dicter": {"name": "Dicter"}},
    )
    restore_prompt_defaults(settings, voice=voice)
    key = "voice_prompts" if voice else "prompts"
    assert json.loads(store.value(key)) == (
        settings.default_voice_prompts if voice else settings.default_prompts
    )
    assert json.loads(store.value(key + "_before_restore")) == custom
    assert json.loads(store.value("prompts" if voice else "voice_prompts")) == custom
    assert store.value("ai_provider") == "foundry"
    assert store.value("dictation_hotkey") == "Ctrl+Alt+D"


def test_confirmation_is_non_blocking_declines_by_default_and_ignores_duplicates(
    qt_app,
):
    app = QApplication.instance() or QApplication([])
    owner, calls = QWidget(), []
    box = confirm_action(
        owner, "Confirmer", "Supprimer ?", lambda: calls.append("first")
    )
    assert not calls
    assert box.testOption(QMessageBox.Option.DontUseNativeDialog)
    assert box.defaultButton() == box.button(QMessageBox.StandardButton.No)
    assert (
        confirm_action(owner, "Autre", "Autre ?", lambda: calls.append("second")) is box
    )
    box.done(QMessageBox.StandardButton.No)
    app.processEvents()
    assert not calls and owner._confirmation_dialog is None
    box = confirm_action(
        owner, "Confirmer", "Supprimer ?", lambda: calls.append("accepted")
    )
    box.done(QMessageBox.StandardButton.Yes)
    app.processEvents()
    assert calls == ["accepted"]
    owner.close()


def test_library_reset_waits_for_explicit_acceptance(tmp_path, qt_app):
    app = QApplication.instance() or QApplication([])
    store = QSettings(str(tmp_path / "restore.ini"), QSettings.Format.IniFormat)
    store.setValue("prompts", '{"custom": {}}')
    settings = SimpleNamespace(
        settings=store, sync=store.sync, default_prompts={"original": {}}
    )
    owner, refreshed = QWidget(), []
    box = restore_library(owner, settings, lambda: refreshed.append(True))
    assert json.loads(store.value("prompts")) == {"custom": {}}
    box.done(QMessageBox.StandardButton.Yes)
    app.processEvents()
    assert json.loads(store.value("prompts")) == {"original": {}}
    assert refreshed == [True]
    owner.close()
