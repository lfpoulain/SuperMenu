import json
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from src.config.settings import Settings
from src.utils.context_menu import ContextMenuManager
from supermenu_core.config.prompt_transfer import (
    export_prompt_bundle,
    import_prompt_bundle,
)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    if Path(__file__).parents[1].name == "win32":
        monkeypatch.setattr(
            "src.config.settings.os.path.expanduser", lambda _: str(tmp_path)
        )
        value = Settings()
    else:
        value = Settings(str(tmp_path / "settings.ini"))
    monkeypatch.setattr(value, "get_api_key", lambda: "")
    value._test_app = app
    return value


def test_text_and_voice_targets_survive_export_import(settings, tmp_path):
    target = {
        "provider": "custom",
        "model": "gemma",
        "device": "apple",
        "device_name": "Sur Serveur Apple (LM Link)",
        "endpoint": "http://localhost:1234",
        "endpoint_type": "lmstudio",
    }
    settings.update_prompt(
        "corriger", "Corriger", "Corrige", "Correction", model_target=target
    )
    voice = settings.add_voice_prompt(
        None, "Vocal", "Reformule", "En cours", model_target=target
    )
    path = tmp_path / "prompts.json"
    export_prompt_bundle(settings, path)
    settings.update_prompt(
        "corriger", "Corriger", "Corrige", "Correction", model_target={}
    )
    assert settings.get_prompt("corriger")["model_target"] == {}
    import_prompt_bundle(settings, path)
    # The model and its device survive; the server always comes from the Text
    # settings, so the exported file does not carry it.
    kept = {"provider": "custom", "model": "gemma", "device": "apple"}
    assert settings.get_prompt("corriger")["model_target"] == kept
    assert settings.get_voice_prompt(voice)["model_target"] == kept
    # Old callers that update only instructions must preserve the explicit route.
    settings.update_prompt("corriger", "Corriger", "Nouvelle instruction", "En cours")
    assert settings.get_prompt("corriger")["model_target"] == kept
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "localhost:1234" not in path.read_text(encoding="utf-8")
    # Nor the name of a machine: it describes the exporting server.
    assert "Serveur Apple" not in path.read_text(encoding="utf-8")
    payload["voice_prompts"][voice]["model_target"] = {
        "provider": "unknown",
        "model": "a",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        import_prompt_bundle(settings, path)
    assert settings.get_prompt("corriger")["prompt"] == "Nouvelle instruction"


class Client(QObject):
    request_started_scoped = Signal(str, bool)
    request_finished_scoped = Signal(str, str, bool, object)
    request_error_scoped = Signal(str, str)

    def __init__(self, settings):
        super().__init__()
        self.settings, self.sent, self.closed = settings, [], False

    def send_request(self, *args, **kwargs):
        self.sent.append((args, kwargs))

    def close(self):
        self.closed = True


def test_parallel_prompt_requests_keep_their_model_and_release_clients(
    settings, monkeypatch
):
    created = []

    def create(manager, config=None):
        client = Client(config or manager.settings)
        created.append(client)
        return client

    monkeypatch.setattr(ContextMenuManager, "_create_api_client", create)
    manager = ContextMenuManager(settings)
    manager.response_window.set_response = lambda *_a: None
    manager.response_window.set_loading = lambda *_a: None
    tiny = {"provider": "openai", "model": "gpt-5.6-luna"}
    large = {"provider": "openai", "model": "gpt-5.6-sol"}
    first = manager._send_request("Correct", "Text", model_target=tiny)
    second = manager._send_request("Rewrite", "Text", model_target=large)
    assert created[1].settings.get_model() == "gpt-5.6-luna"
    assert created[2].settings.get_model() == "gpt-5.6-sol"
    assert manager.api_client is created[0]
    assert manager.response_window.last_model_target == large
    manager.on_request_finished_scoped(first, "Result", False, None)
    assert created[1].closed and not created[2].closed
    assert (
        first not in manager._pending_requests and second in manager._pending_requests
    )
    manager.on_request_finished_scoped(second, "Result", False, None)
    assert created[2].closed and manager._retired_clients == []
    manager.response_window.store_request("Rewrite", "Text")
    retries = []
    monkeypatch.setattr(manager, "_send_request", lambda *a, **kw: retries.append(kw))
    manager.on_retry_requested()
    assert retries[0]["model_target"] == large
    manager.close()
