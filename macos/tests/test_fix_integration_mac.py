"""Integration follow-ups on macOS (findings 6, 27, 29, 43, 51, 57, 67, 88)."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

import supermenu_core.api.openai_client as shared_client
import src.utils.context_menu as context_menu_module
from src.api import apple_foundation_client as apple
from src.config.settings import Settings
from src.ui import main_window as main_window_module
from src.ui.main_window import MainWindow
from src.utils.context_menu import ContextMenuManager


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def manager(app, tmp_path):
    value = ContextMenuManager(Settings(config_path=str(tmp_path / "settings.ini")))
    yield value
    value.close()


class FakeIndicator:
    def __init__(self):
        self.messages = []
        self.closed = False

    def set_message(self, message):
        self.messages.append(message)

    def move_near_cursor(self):
        pass

    def close(self):
        self.closed = True


class FakeResponseWindow:
    def __init__(self):
        self.responses = []
        self.stored = []
        self.presented = 0
        self.status = None
        self.paste_target = None
        self.last_reasoning_mode = "default"
        self.last_model_target = {}

    def set_status(self, status):
        self.status = status

    def set_trigger_position(self, _position):
        pass

    def set_paste_target(self, target):
        self.paste_target = target

    def store_request(self, prompt, content):
        self.stored.append((prompt, content))

    def present(self):
        self.presented += 1

    def set_response(self, text):
        self.responses.append(text)

    def set_loading(self, _loading):
        pass

    def close(self):
        pass


class FakeTarget:
    def __init__(self):
        self.activations = 0

    def request_activation(self, force=False):
        self.activations += 1
        return True


def _direct_environment(manager, monkeypatch, *, success, reason=""):
    env = SimpleNamespace(
        indicator=FakeIndicator(),
        dialogs=[],
        callbacks=[],
        window=FakeResponseWindow(),
    )
    manager.response_window = env.window

    class FakeInserter:
        def insert_text_async(self, text, target, on_finished, **_kwargs):
            env.callbacks.append(on_finished)
            if success is not None:
                on_finished(success, reason)

    monkeypatch.setattr(context_menu_module, "TextInserter", FakeInserter)
    monkeypatch.setattr(
        context_menu_module.SimpleLoadingIndicator,
        "show_near_cursor",
        lambda *_args, **_kwargs: env.indicator,
    )
    monkeypatch.setattr(
        context_menu_module.SafeDialogs,
        "show_information",
        lambda title, message, parent=None, **_kwargs: env.dialogs.append((title, message)),
    )
    monkeypatch.setattr(manager.api_client, "send_request", lambda *_args, **_kwargs: None)
    return env


# Finding 6 -- a refused direct insertion never throws the answer away.


def test_refused_direct_insertion_keeps_the_answer_in_the_response_window(
    manager, monkeypatch
):
    env = _direct_environment(manager, monkeypatch, success=False, reason="window_changed")
    target = FakeTarget()

    request_id = manager._send_request(
        "Reformule :", "texte sélectionné", True, target=target, reasoning_mode="off"
    )
    manager.on_request_finished_scoped(request_id, "réponse générée", True, target)

    assert env.window.responses == ["réponse générée"]
    assert env.window.presented == 1
    assert env.window.status == "Insertion annulée — réponse conservée"
    # « Réessayer » replays the same request with the same reasoning mode.
    assert env.window.stored == [("Reformule :", "texte sélectionné")]
    assert env.window.last_reasoning_mode == "off"
    assert env.window.paste_target is target
    assert env.indicator.messages[-1] == "Insertion annulée"
    title, message = env.dialogs[0]
    assert title == "Insertion annulée"
    assert "Une autre fenêtre" in message
    assert "fenêtre de réponse" in message
    assert request_id not in manager._pending_requests


def test_refused_answer_is_copied_when_the_window_awaits_another_one(
    app, manager, monkeypatch
):
    env = _direct_environment(manager, monkeypatch, success=False, reason="target_changed")
    waiting_id = manager._send_request("Explique :", "texte")
    direct_id = manager._send_request("Corrige :", "texte", True, target=FakeTarget())

    manager.on_request_finished_scoped(direct_id, "réponse directe", True, None)

    assert QApplication.clipboard().text() == "réponse directe"
    assert env.window.responses == []
    assert env.window.presented == 0
    assert "presse-papiers" in env.dialogs[0][1]
    assert waiting_id in manager._pending_requests


def test_successful_direct_insertion_is_unchanged(manager, monkeypatch):
    env = _direct_environment(manager, monkeypatch, success=True)
    target = FakeTarget()

    request_id = manager._send_request("Corrige :", "texte", True, target=target)
    manager.on_request_finished_scoped(request_id, "réponse", True, target)

    assert env.window.responses == [] and env.window.presented == 0
    assert env.dialogs == []
    assert env.indicator.messages[-1] == "Réponse insérée"


# Finding 27 -- shutting down mid-insertion closes the waiting indicator.


def test_insertion_finishing_after_close_closes_the_indicator(manager, monkeypatch):
    env = _direct_environment(manager, monkeypatch, success=None)
    target = FakeTarget()
    request_id = manager._send_request("Corrige :", "texte", True, target=target)
    manager.on_request_finished_scoped(request_id, "réponse", True, target)
    assert len(env.callbacks) == 1 and not env.indicator.closed

    manager.close()
    env.callbacks[0](False, "cancelled")

    assert env.indicator.closed
    assert env.dialogs == [] and env.window.responses == []


# Finding 57 -- after a direct error, closing the box returns to the target.


def test_direct_error_box_hands_the_foreground_back_to_the_target(manager, monkeypatch):
    shown = []
    monkeypatch.setattr(
        context_menu_module.SafeDialogs,
        "show_critical",
        lambda title, message, parent=None, **kwargs: shown.append((title, message, kwargs)),
    )
    target = FakeTarget()
    manager._pending_requests["directe"] = {
        "client": manager.api_client,
        "insert_directly": True,
        "target": target,
        "indicator": None,
    }

    manager.on_request_error_scoped("directe", "délai dépassé")

    assert len(shown) == 1
    title, message, kwargs = shown[0]
    assert (title, message) == ("Erreur de traitement", "délai dépassé")
    assert target.activations == 0
    kwargs["on_closed"]()
    assert target.activations == 1


# Finding 43 -- dictation correction follows the « Corriger » reasoning mode.


def test_dictation_correction_reads_the_corriger_reasoning_mode(manager, monkeypatch):
    created = []

    class FakeSession:
        def __init__(self, *args, **kwargs):
            created.append(kwargs)

        def start_voice_recognition(self):
            pass

        def cleanup(self):
            pass

        def deleteLater(self):
            pass

    monkeypatch.setattr(
        "supermenu_core.audio.dictation_flow.PlainDictationSession", FakeSession
    )
    monkeypatch.setattr(
        "supermenu_core.audio.settings.speech_options", lambda _settings: {}
    )
    monkeypatch.setattr(
        context_menu_module, "activate_current_application", lambda **_kwargs: True
    )
    prompts = {"corriger": {"reasoning_mode": "off"}}
    monkeypatch.setattr(manager.settings, "get_prompt", prompts.get)

    manager.start_dictation(target=FakeTarget())

    mode = created[0]["correction_reasoning_mode"]
    assert callable(mode) and mode() == "off"
    prompts["corriger"]["reasoning_mode"] = "on"
    assert mode() == "on"
    prompts.clear()
    assert mode() == "default"
    manager._dictation = None


# Finding 51 -- saving the settings probes the servers again.


def test_updating_the_client_forgets_shared_capability_probes(manager):
    key = ("lmstudio", "http://localhost:1234", "gemma")
    shared_client._remember_capabilities(key, {"vision": False})

    manager.update_client_config()

    assert shared_client._cached_capabilities(key) is None


# Finding 67 -- stable builds are not told to reinstall a beta.


def test_missing_apple_component_asks_to_reinstall_supermenu():
    message = apple.ERROR_MESSAGES["helper_missing"]

    assert "Réinstallez SuperMenu." in message
    assert "bêta" not in message


# Finding 88 -- the kept copy of the text prompts is reachable on macOS.


def test_previous_text_library_is_offered_from_the_prompt_actions(app, tmp_path, monkeypatch):
    monkeypatch.setattr(main_window_module.QMessageBox, "information", Mock())
    monkeypatch.setattr("supermenu_core.ui.speech_settings.microphones", lambda: [])
    calls = []
    monkeypatch.setattr(
        main_window_module,
        "restore_previous_library",
        lambda parent, settings, refreshed: calls.append((parent, settings, refreshed)),
    )
    window = MainWindow(
        Settings(str(tmp_path / "settings.ini")), context_menu_manager=Mock()
    )
    try:
        window.prompt_actions.previous_button.click()

        assert calls == [(window, window.settings, window._prompts_restored)]
    finally:
        window._quitting = True
        window.close()
        app.processEvents()
