import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.api.openai_client import OpenAIClient
from src.utils.context_menu import ContextMenuManager


def _app():
    return QApplication.instance() or QApplication([])


class FakeSettings:
    def get_api_key(self):
        return "key"

    def get_use_custom_endpoint(self):
        return False

    def get_custom_endpoint(self):
        return ""

    def get_custom_endpoint_type(self):
        return "ollama"

    def get_custom_model(self):
        return ""

    def get_model(self):
        return "gpt-5.6-sol"

    def get_reasoning_effort(self):
        return "none"

    def get_prompts(self):
        return {}

    def get_voice_prompts(self):
        return {}

    def sync(self):
        pass


def test_send_request_returns_and_emits_a_stable_request_id(monkeypatch):
    _app()
    client = OpenAIClient(FakeSettings(), api_key="key")
    started = []
    client.request_started_scoped.connect(
        lambda request_id, direct: started.append((request_id, direct))
    )

    class DeferredThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            pass

    monkeypatch.setattr(threading, "Thread", DeferredThread)

    request_id = client.send_request("prompt", "content")

    assert request_id
    assert started == [(request_id, False)]


def test_incomplete_custom_endpoint_never_falls_back_to_openai(monkeypatch):
    settings = FakeSettings()
    settings.get_use_custom_endpoint = lambda: True
    settings.get_custom_endpoint = lambda: ""
    settings.get_custom_model = lambda: ""
    client = OpenAIClient(settings, api_key=None)
    errors = []
    client.request_error.connect(errors.append)
    thread_calls = []
    monkeypatch.setattr(
        threading,
        "Thread",
        lambda *_args, **_kwargs: thread_calls.append("thread"),
    )

    request_id = client.send_request("prompt", "content")

    assert request_id
    assert client.api_url == ""
    assert errors and "incomplète" in errors[0]
    assert thread_calls == []


def test_stale_response_cannot_replace_latest_response():
    _app()
    manager = ContextMenuManager(FakeSettings())
    responses = []
    manager.response_window.set_response = responses.append
    manager.response_window.set_loading = lambda _value: None
    manager._active_response_request_id = "new"
    manager._pending_requests = {
        "old": {"insert_directly": False, "client": manager.api_client},
        "new": {"insert_directly": False, "client": manager.api_client},
    }

    manager.on_request_finished_scoped("old", "old response", False, None)
    manager.on_request_finished_scoped("new", "new response", False, None)

    assert responses == ["new response"]


def test_direct_completion_finishes_without_touching_response_window(monkeypatch):
    _app()
    manager = ContextMenuManager(FakeSettings())
    loading_calls = []
    manager.response_window.set_loading = loading_calls.append
    manager._pending_requests = {
        "direct": {
            "insert_directly": True,
            "target": object(),
            "client": manager.api_client,
        }
    }
    inserted = []
    monkeypatch.setattr(
        "src.utils.context_menu.TextInserter.insert_text",
        lambda _self, text, target=None: inserted.append((text, target)) or True,
    )

    manager.on_request_finished_scoped("direct", "result", True, object())

    assert inserted and inserted[0][0] == "result"
    assert loading_calls == []
    assert "direct" not in manager._pending_requests


def test_prompt_hotkey_uses_its_prompt_without_forcing_display_mode(monkeypatch):
    _app()
    settings = FakeSettings()
    manager = ContextMenuManager(settings)
    target = object()
    calls = []

    monkeypatch.setattr(
        "src.utils.context_menu.PasteTarget.capture",
        lambda: target,
    )
    monkeypatch.setattr(
        manager,
        "_try_get_selected_text",
        lambda: "texte sélectionné",
    )
    monkeypatch.setattr(
        manager,
        "_handle_menu_action",
        lambda prompt_id, **kwargs: calls.append((prompt_id, kwargs)),
    )

    manager.run_prompt_hotkey("corriger")

    assert calls == [
        (
            "corriger",
            {
                "selected_text": "texte sélectionné",
                "target": target,
            },
        )
    ]


def test_prompt_hotkey_direct_insert_setting_skips_response_window(monkeypatch):
    _app()
    settings = FakeSettings()
    settings.get_prompt = lambda _prompt_id: {
        "prompt": "Corrige :",
        "status": "Correction en cours",
        "insert_directly": True,
    }
    manager = ContextMenuManager(settings)
    presented = []
    requests = []
    manager.response_window.present = lambda: presented.append("present")
    monkeypatch.setattr(
        manager,
        "_send_request",
        lambda *args, **kwargs: requests.append((args, kwargs)),
    )

    manager._handle_menu_action(
        "corriger",
        selected_text="texte sélectionné",
        target=object(),
    )

    assert presented == []
    assert requests[0][0][:3] == ("Corrige :", "texte sélectionné", True)


def test_prompt_hotkey_window_setting_presents_response_window(monkeypatch):
    _app()
    settings = FakeSettings()
    settings.get_prompt = lambda _prompt_id: {
        "prompt": "Explique :",
        "status": "Explication en cours",
        "insert_directly": False,
    }
    manager = ContextMenuManager(settings)
    presented = []
    stored_requests = []
    requests = []
    manager.response_window.present = lambda: presented.append("present")
    manager.response_window.store_request = (
        lambda *args: stored_requests.append(args)
    )
    monkeypatch.setattr(
        manager,
        "_send_request",
        lambda *args, **kwargs: requests.append((args, kwargs)),
    )

    manager._handle_menu_action(
        "expliquer",
        selected_text="texte sélectionné",
        target=object(),
    )

    assert presented == ["present"]
    assert stored_requests == [("Explique :", "texte sélectionné")]
    assert requests[0][0][:3] == ("Explique :", "texte sélectionné", False)
