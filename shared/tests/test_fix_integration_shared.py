"""Integration follow-ups in the shared core (findings 2, 33, 38, 57, 88, 107)."""

import json
import logging

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QHBoxLayout

from supermenu_core.audio.backends import (
    DOWNLOAD_TIMEOUT_MESSAGE,
    TIMEOUT_MESSAGE,
    ProcessSpeechBackend,
)
from supermenu_core.config import voice_prompts as voice_prompts_module
from supermenu_core.config.prompts import normalize_prompt_collection
from supermenu_core.config.voice_prompts import VoicePromptSettingsMixin
from supermenu_core.ui import voice_prompt_editor as editor_module
from supermenu_core.ui.page_actions import PromptActions
from supermenu_core.ui.response_window import BaseResponseWindow
from supermenu_core.ui.safe_dialogs import SafeDialogs
from supermenu_core.ui.voice_prompt_editor import VoicePromptEditor


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


# Finding 2 -- an old prompt target no longer keeps a server address.


def test_stored_prompt_target_drops_the_server_and_keeps_model_and_device():
    prompts = normalize_prompt_collection(
        {
            "corriger": {
                "name": "Corriger",
                "prompt": "Corrige",
                "status": "En cours",
                "model_target": {
                    "provider": "custom",
                    "model": "gemma",
                    "device": "apple",
                    "device_name": "Mac de bureau",
                    "endpoint": "http://192.168.1.20:1234",
                    "endpoint_type": "lmstudio",
                },
            }
        }
    )

    assert prompts["corriger"]["model_target"] == {
        "provider": "custom",
        "model": "gemma",
        "device": "apple",
        "device_name": "Mac de bureau",
    }


# Finding 107 -- voice library errors reach the configured "SuperMenu" logger.


class VoiceSettings(VoicePromptSettingsMixin):
    def __init__(self, path):
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)
        self.initialize_voice_prompts()

    def get_prompts(self):
        return {}

    def sync(self):
        self.settings.sync()


def test_voice_library_errors_use_a_child_of_the_supermenu_logger(app, tmp_path, caplog):
    assert voice_prompts_module.logger.name.startswith("SuperMenu.")
    settings = VoiceSettings(tmp_path / "voice.ini")
    settings.settings.setValue("voice_prompts", "{illisible")

    with caplog.at_level(logging.ERROR, logger="SuperMenu"):
        assert settings.get_voice_prompts() == {}

    assert [record.name for record in caplog.records] == ["SuperMenu.core.config"]


# Finding 33 -- an expired download says so instead of a generic message.


@pytest.mark.parametrize(
    "action, phase, preparing, expected",
    [
        ("download", "", True, DOWNLOAD_TIMEOUT_MESSAGE),
        ("probe", "hardware", True, DOWNLOAD_TIMEOUT_MESSAGE),
        ("probe", "verify", True, TIMEOUT_MESSAGE),
        ("start", "", False, TIMEOUT_MESSAGE),
    ],
)
def test_timeout_message_matches_the_expired_step(app, action, phase, preparing, expected):
    backend = ProcessSpeechBackend(("absent", []), {"provider": "foundry", "action": action})
    backend.phase = phase
    backend.preparing = preparing
    failures = []
    backend.failed.connect(failures.append)

    backend.timer.timeout.emit()

    assert failures == [expected]
    assert backend.closed


# Finding 38 -- the « Écrire » button names a change of window.


class _RefusingInserter:
    def insert_text_async(self, _text, _target, callback):
        callback(False, "window_changed")


class _Window(BaseResponseWindow):
    def _create_text_inserter(self):
        return _RefusingInserter()


def test_write_reports_another_window_of_the_target_application(app):
    window = _Window()
    window.set_response("Réponse")
    window._pending_paste_text = "Réponse"

    window._paste_text()

    assert window.status_label.text() == (
        "⚠️ Insertion annulée : une autre fenêtre de l’application cible est "
        "devenue active"
    )
    window.close()


# Finding 57 -- a dialog can hand the foreground back once it is closed.


def test_close_callback_runs_once_when_the_box_is_closed(app):
    instance = SafeDialogs.get_instance()
    closed = []

    SafeDialogs.show_critical("Erreur de traitement", "délai dépassé", on_closed=lambda: closed.append(1))
    app.processEvents()
    box = instance._open_dialogs[-1]
    assert box.text() == "délai dépassé"
    assert closed == []

    box.done(0)
    app.processEvents()

    assert closed == [1]
    assert box not in instance._open_dialogs
    assert instance._close_callbacks == {}


def test_a_failing_close_callback_is_only_logged(app, caplog):
    instance = SafeDialogs.get_instance()

    def fail():
        raise RuntimeError("cible fermée")

    SafeDialogs.show_warning("Attention", "message", on_closed=fail)
    app.processEvents()
    box = instance._open_dialogs[-1]
    with caplog.at_level(logging.ERROR, logger="SuperMenu"):
        box.done(0)
        app.processEvents()

    assert "Error after closing a dialog" in caplog.text
    assert box not in instance._open_dialogs


def test_dialogs_without_callback_keep_the_original_slots(app):
    meta = SafeDialogs.get_instance().metaObject()
    for name in ("information", "warning", "critical"):
        assert meta.indexOfMethod(f"_show_{name}_impl(QString,QString)") != -1


# Finding 88 -- the kept copy of a library is reachable from both editors.


def _row_buttons(actions):
    layout = actions.layout()
    assert isinstance(layout, QHBoxLayout)
    return [
        layout.itemAt(index).widget()
        for index in range(layout.count())
        if layout.itemAt(index).widget() is not None
    ]


def test_previous_copy_button_sits_after_restore_all(app):
    actions = PromptActions(lambda: None, lambda: None)
    emitted = []
    actions.restore_previous_requested.connect(lambda: emitted.append(True))

    buttons = _row_buttons(actions)
    assert buttons.index(actions.previous_button) == 2
    assert buttons[:3] == [
        actions.reset_button,
        actions.restore_button,
        actions.previous_button,
    ]
    assert actions.previous_button.text() == "Revenir à la copie…"
    assert "dernière restauration" in actions.previous_button.toolTip()

    actions.previous_button.click()

    assert emitted == [True]
    actions.close()


class EditorSettings(VoicePromptSettingsMixin):
    def __init__(self, path):
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)
        self.initialize_voice_prompts()

    def get_prompts(self):
        return json.loads(self.settings.value("prompts", "{}"))

    def sync(self):
        self.settings.sync()


def test_voice_editor_offers_the_previous_voice_library(app, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        editor_module,
        "restore_previous_library",
        lambda parent, settings, refreshed, *, voice=False: calls.append(
            (parent, settings, refreshed, voice)
        ),
    )
    settings = EditorSettings(tmp_path / "voice.ini")
    editor = VoicePromptEditor(settings)

    editor.actions.previous_button.click()

    assert calls == [(editor, settings, editor.reload, True)]
    editor.close()
