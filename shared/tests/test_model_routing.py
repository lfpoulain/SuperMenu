"""Routing invariants for models installed on more than one device."""

import json
import threading
import time

import pytest

from supermenu_core.api import lmstudio_transport as transport
from supermenu_core.api.openai_client import OpenAIClient


class Socket:
    def __init__(self, device=None, stop="eosFound", error=False):
        self.device, self.stop, self.error = device, stop, error
        self.replies = [{"success": True}]
        self.sent = []
        self.closed = False

    def settimeout(self, _timeout):
        pass

    def send(self, message):
        data = json.loads(message)
        self.sent.append(data)
        if data.get("type") != "channelCreate":
            return
        channel = data["channelId"]
        if data["endpoint"] == "getOrLoad":
            packets = [
                {
                    "type": "alreadyLoaded",
                    "info": {
                        "deviceIdentifier": self.device,
                        "instanceReference": "fixed-instance",
                    },
                }
            ]
        else:
            if self.error:
                self.replies.append(
                    {
                        "type": "channelError",
                        "channelId": channel,
                        "error": {"message": "secret server stack"},
                    }
                )
                return
            packets = [
                {
                    "type": "fragment",
                    "fragment": {"content": "Thinking", "reasoningType": "reasoning"},
                },
                {
                    "type": "fragment",
                    "fragment": {"content": "Corrected", "reasoningType": "none"},
                },
                {"type": "success", "stats": {"stopReason": self.stop}},
            ]
        self.replies.extend(
            {"type": "channelSend", "channelId": channel, "message": p} for p in packets
        )
        self.replies.append({"type": "channelClose", "channelId": channel})

    def recv(self):
        return json.dumps(self.replies.pop(0))

    def shutdown(self):
        self.closed = True


@pytest.mark.parametrize("device", [None, "remote-apple"])
def test_exact_device_and_instance_are_used_before_sending_text(monkeypatch, device):
    import websocket

    socket = Socket(device)
    monkeypatch.setattr(websocket, "create_connection", lambda *_a, **_k: socket)
    result = transport.targeted_completion(
        "http://localhost:1234",
        None,
        {"model": "gemma", "input": "Private text", "reasoning": "off"},
        device,
    )
    load, predict = [m for m in socket.sent if m.get("type") == "channelCreate"]
    assert load["creationParameter"]["deviceIdentifier"] == device
    assert load["creationParameter"]["loadTtlMs"] == 300000
    assert "Private text" not in json.dumps(load)
    assert predict["creationParameter"]["modelSpecifier"] == {
        "type": "instanceReference",
        "instanceReference": "fixed-instance",
    }
    fields = predict["creationParameter"]["predictionConfigStack"]["layers"][0][
        "config"
    ]["fields"]
    assert {"key": "llm.prediction.reasoning.enableThinking", "value": False} in fields
    assert result["output"] == [{"type": "message", "content": "Corrected"}]
    assert socket.closed


def test_wrong_device_refuses_text_and_closes(monkeypatch):
    import websocket

    socket = Socket(None)
    monkeypatch.setattr(websocket, "create_connection", lambda *_a, **_k: socket)
    with pytest.raises(RuntimeError, match="Aucun texte"):
        transport.targeted_completion(
            "http://localhost:1234",
            None,
            {"model": "gemma", "input": "Private"},
            "remote",
        )
    assert not any(m.get("endpoint") == "predict" for m in socket.sent)
    assert socket.closed


@pytest.mark.parametrize("stop", ["maxPredictedTokensReached", "contextLengthReached"])
def test_truncation_remains_detectable(monkeypatch, stop):
    import websocket

    socket = Socket(stop=stop)
    monkeypatch.setattr(websocket, "create_connection", lambda *_a, **_k: socket)
    result = transport.targeted_completion(
        "http://localhost:1234", None, {"model": "gemma", "input": "Text"}, None
    )
    assert OpenAIClient._response_was_truncated(result)


def test_server_failure_cancels_channel_and_hides_raw_errors(monkeypatch):
    import websocket

    socket = Socket(error=True)
    monkeypatch.setattr(websocket, "create_connection", lambda *_a, **_k: socket)
    with pytest.raises(RuntimeError, match="poste choisi") as error:
        transport.targeted_completion(
            "http://localhost:1234", None, {"model": "gemma", "input": "Text"}, None
        )
    assert "secret" not in str(error.value)
    assert socket.sent[-1]["message"] == {"type": "cancel"}
    assert socket.closed


def test_cancelled_session_does_not_connect(monkeypatch):
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(RuntimeError, match="annulée"):
        transport.StudioSession(
            "http://localhost:1234", "llm", {}, time.monotonic() + 10, cancelled
        )


def test_explicit_routing_never_falls_back_to_rest(monkeypatch):
    client = OpenAIClient.__new__(OpenAIClient)
    client.use_lmstudio_api = True
    client.model_target = {"device": "remote"}
    client.custom_endpoint = "http://localhost:1234"
    client.endpoint_api_key = ""
    client._closing = threading.Event()
    calls = []

    def fail(*args, **kwargs):
        calls.append(args[3])
        raise RuntimeError("Offline")

    monkeypatch.setattr(transport, "targeted_completion", fail)
    client._make_request_with_retry = lambda *_a, **_k: pytest.fail("Must not fallback")
    with pytest.raises(RuntimeError, match="Offline"):
        client._perform_request({}, {"model": "gemma"}, 10)
    assert calls == ["remote"]
