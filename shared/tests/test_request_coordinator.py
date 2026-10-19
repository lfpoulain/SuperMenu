from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from supermenu_core.ui import request_coordinator as coordinator_module
from supermenu_core.ui.request_coordinator import (
    PromptRequestCoordinator,
    RequestFeedback,
)


class Settings:
    def get_model(self):
        return "gpt-5.6-sol"

    def sync(self):
        pass


class Client(QObject):
    request_started_scoped = Signal(str, bool)
    request_finished_scoped = Signal(str, str, bool, object)
    request_error_scoped = Signal(str, str)

    def __init__(self, settings):
        super().__init__()
        self.settings, self.sent, self.closed = settings, [], 0

    def send_request(self, prompt, content, **kwargs):
        self.sent.append((prompt, content, kwargs))

    def close(self):
        self.closed += 1


class ResponseWindow(QObject):
    retry_requested = Signal()

    def __init__(self):
        super().__init__()
        self.calls = []
        self.last_request = (None, None)

    def __getattr__(self, name):
        if name.startswith(("set_", "present", "close")):
            return lambda *args: self.calls.append((name, *args))
        raise AttributeError(name)

    def store_request(self, prompt, content):
        self.last_request = (prompt, content)

    def get_last_request(self):
        return self.last_request


class Indicator:
    def __init__(self, message):
        self.messages, self.closed = [message], 0

    def close(self):
        self.closed += 1


class Coordinator(PromptRequestCoordinator):
    REQUEST_FEEDBACK = RequestFeedback(
        direct_pending="En attente",
        response_error="Erreur : {error}",
        send_error="Refusé : {error}",
    )

    def __init__(self):
        self.clients, self.insertions, self.failures = [], [], []
        self.refuse_retry, self.released = False, 0
        super().__init__(Settings(), ResponseWindow)

    def _create_api_client(self, settings=None):
        client = Client(settings or self.settings)
        self.clients.append(client)
        return client

    def _insert_directly(self, response, target, indicator, client, request=None):
        self.insertions.append((response, target, indicator, client, request))

    def _report_direct_failure(self, request, error):
        self.failures.append((request["indicator"], error))

    def _retry_refused(self, prompt, content):
        return self.refuse_retry

    def _release_platform_resources(self):
        self.released += 1


def _coordinator(monkeypatch):
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        coordinator_module.SimpleLoadingIndicator, "show_near_cursor", Indicator
    )
    monkeypatch.setattr(
        coordinator_module, "effective_model_target", lambda _settings, target: target
    )
    return Coordinator()


def _window_calls(manager, name):
    return [call[1:] for call in manager.response_window.calls if call[0] == name]


def test_only_the_latest_window_request_updates_the_response(monkeypatch):
    manager = _coordinator(monkeypatch)
    first = manager._send_request("Corrige", "a")
    second = manager._send_request("Corrige", "b")
    third = manager._send_request("Corrige", "c")

    manager.api_client.request_error_scoped.emit(first, "délai dépassé")
    manager.api_client.request_finished_scoped.emit(third, "récente", False, None)
    manager.api_client.request_finished_scoped.emit(second, "tardive", False, None)

    assert _window_calls(manager, "set_response") == [("récente",)]
    assert _window_calls(manager, "set_error") == []
    assert manager.failures == [] and manager._pending_requests == {}
    manager.close()


def test_direct_answers_reach_the_platform_with_their_request(monkeypatch):
    manager = _coordinator(monkeypatch)
    target = object()
    request_id = manager._send_request(
        "Corrige", "Texte", True, target=target, model_target={"model": "tiny"}
    )
    default, dedicated = manager.clients
    assert dedicated.sent[0][2]["request_id"] == request_id

    dedicated.request_finished_scoped.emit(request_id, "Résultat", True, None)

    response, inserted_target, indicator, client, request = manager.insertions[0]
    assert (response, inserted_target, client) == ("Résultat", target, dedicated)
    assert indicator.messages == ["En attente"]
    assert (request["prompt"], request["content"]) == ("Corrige", "Texte")
    assert request["model_target"] == {"model": "tiny"}
    # The platform releases the dedicated client once its paste is done.
    assert dedicated.closed == 0 and dedicated in manager._retired_clients
    manager._release_retired_client_if_idle(dedicated)
    assert dedicated.closed == 1 and manager._retired_clients == []
    assert default.closed == 0
    manager.close()


def test_failures_go_to_the_window_or_to_the_platform(monkeypatch):
    manager = _coordinator(monkeypatch)
    window_request = manager._send_request("Corrige", "a")
    direct_request = manager._send_request("Corrige", "b", True)
    indicator = manager._pending_requests[direct_request]["indicator"]

    manager.api_client.request_error_scoped.emit(window_request, "hors ligne")
    manager.api_client.request_error_scoped.emit(direct_request, "hors ligne")

    assert _window_calls(manager, "set_error") == [("Erreur : hors ligne",)]
    assert manager.failures == [(indicator, "hors ligne")]

    def refuse(*_args, **_kwargs):
        raise RuntimeError("clé absente")

    manager.api_client.send_request = refuse
    manager._send_request("Corrige", "c")
    assert _window_calls(manager, "set_error")[-1] == ("Erreur : Refusé : clé absente",)
    manager.close()


def test_retry_resends_the_last_request_unless_the_platform_refuses(monkeypatch):
    manager = _coordinator(monkeypatch)
    manager._send_request("Corrige", "a", model_target={"model": "tiny"})
    manager.response_window.store_request("Corrige", "a")

    manager.refuse_retry = True
    manager.on_retry_requested()
    assert len(manager.clients) == 2 and len(manager.clients[1].sent) == 1

    manager.refuse_retry = False
    manager.on_retry_requested()
    retried = manager.clients[2]
    assert retried.settings.target["model"] == "tiny"
    assert retried.sent[0][:2] == ("Corrige", "a")
    manager.close()


def test_close_releases_everything_once_and_ignores_late_results(monkeypatch):
    manager = _coordinator(monkeypatch)
    request_id = manager._send_request(
        "Corrige", "a", True, model_target={"model": "tiny"}
    )
    default, dedicated = manager.clients
    indicator = manager._pending_requests[request_id]["indicator"]

    manager.close()
    manager.close()
    dedicated.request_finished_scoped.emit(request_id, "tardif", True, None)

    assert manager.released == 1
    assert (default.closed, dedicated.closed, indicator.closed) == (1, 1, 1)
    assert manager.insertions == []
    assert manager._send_request("Corrige", "b") is None
