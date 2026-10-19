"""OpenAISpeechBackend socket lifecycle against a local WebSocket server."""

import json
import time

import pytest
from PySide6.QtNetwork import QHostAddress
from PySide6.QtTest import QTest
from PySide6.QtWebSockets import QWebSocketServer
from PySide6.QtWidgets import QApplication

from supermenu_core.audio.backends import OpenAISpeechBackend


def wait_for(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate()


class RealtimeServer:
    def __init__(self):
        self.server = QWebSocketServer(
            "realtime-test", QWebSocketServer.SslMode.NonSecureMode
        )
        assert self.server.listen(QHostAddress("127.0.0.1"), 0)
        self.client = None
        self.messages = []
        self.server.newConnection.connect(self._accept)

    @property
    def url(self):
        return f"ws://127.0.0.1:{self.server.serverPort()}/v1/realtime"

    def _accept(self):
        self.client = self.server.nextPendingConnection()
        self.client.textMessageReceived.connect(
            lambda text: self.messages.append(json.loads(text))
        )

    def types(self):
        return [message.get("type") for message in self.messages]

    def send(self, event):
        self.client.sendTextMessage(json.dumps(event))

    def close(self):
        if self.client is not None:
            self.client.abort()
        self.server.close()


@pytest.fixture
def realtime():
    QApplication.instance() or QApplication([])
    server = RealtimeServer()
    backends = []

    def connect(api_key="test-key", url=None):
        backend = OpenAISpeechBackend(api_key, {"languages": ["fr"]})
        backend.realtime_url = url or server.url
        backend.events = {"ready": [], "failed": [], "completed": []}
        backend.ready.connect(lambda: backend.events["ready"].append(True))
        backend.failed.connect(backend.events["failed"].append)
        backend.completed.connect(backend.events["completed"].append)
        backends.append(backend)
        backend.start()
        return backend

    def ready(backend):
        wait_for(lambda: "session.update" in server.types())
        server.send({"type": "session.updated"})
        wait_for(lambda: backend.events["ready"])

    server.connect, server.ready = connect, ready
    yield server
    for backend in backends:
        backend.cancel()
    server.close()


def test_production_url_is_unchanged():
    assert (
        OpenAISpeechBackend.realtime_url
        == "wss://api.openai.com/v1/realtime?intent=transcription"
    )


def test_full_dictation_streams_audio_then_closes_without_late_error(realtime):
    backend = realtime.connect()
    realtime.ready(backend)
    session = realtime.messages[0]["session"]["audio"]["input"]
    assert session["transcription"]["languages"] == ["fr"]
    backend.append(b"\x00\x00" * 4800)
    backend.finish()
    wait_for(lambda: "input_audio_buffer.commit" in realtime.types())
    assert realtime.types() == [
        "session.update",
        "input_audio_buffer.append",
        "input_audio_buffer.commit",
    ]
    realtime.send(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "item_id": "a",
            "transcript": "Bonjour.",
        }
    )
    wait_for(lambda: backend.events["completed"])
    QTest.qWait(100)
    assert backend.events["completed"] == ["Bonjour."]
    assert not backend.events["failed"] and backend.closed
    assert backend.api_key == ""


def test_too_short_recording_is_never_committed(realtime):
    backend = realtime.connect()
    realtime.ready(backend)
    backend.append(b"\x00\x00" * 10)
    backend.finish()
    QTest.qWait(100)
    assert backend.events["failed"] == [
        "L’enregistrement est trop court. Parlez puis terminez la dictée."
    ]
    assert "input_audio_buffer.commit" not in realtime.types()


@pytest.mark.parametrize(
    "code, expected",
    [
        ("invalid_api_key", "Clé API OpenAI absente ou invalide."),
        ("insufficient_quota", "Votre limite OpenAI est atteinte."),
        ("other", "OpenAI a refusé la transcription."),
    ],
)
def test_server_errors_are_translated_once(realtime, code, expected):
    backend = realtime.connect()
    realtime.ready(backend)
    realtime.send({"type": "error", "error": {"code": code}})
    wait_for(lambda: backend.events["failed"])
    QTest.qWait(100)
    assert len(backend.events["failed"]) == 1
    assert backend.events["failed"][0].startswith(expected)


def test_server_closing_the_session_interrupts_the_dictation(realtime):
    backend = realtime.connect()
    realtime.ready(backend)
    realtime.client.close()
    wait_for(lambda: backend.events["failed"])
    QTest.qWait(100)
    assert backend.events["failed"] == ["La connexion OpenAI a été interrompue."]
    assert backend.closed


def test_unreachable_server_reports_connection_failure_once(realtime):
    probe = QWebSocketServer("closed", QWebSocketServer.SslMode.NonSecureMode)
    assert probe.listen(QHostAddress("127.0.0.1"), 0)
    url = f"ws://127.0.0.1:{probe.serverPort()}/v1/realtime"
    probe.close()
    backend = realtime.connect(url=url)
    # Windows retries a refused connection for a few seconds.
    wait_for(lambda: backend.events["failed"], seconds=20)
    QTest.qWait(100)
    assert backend.events["failed"] == [
        "Connexion à OpenAI impossible. Vérifiez la connexion et la clé API."
    ]


def test_missing_key_never_opens_a_connection(realtime):
    backend = realtime.connect(api_key="")
    wait_for(lambda: backend.events["failed"])
    QTest.qWait(50)
    assert realtime.client is None
    assert backend.events["failed"][0].startswith("Ajoutez votre clé API OpenAI")


def test_backpressure_fails_instead_of_buffering_audio(realtime, monkeypatch):
    backend = realtime.connect()
    realtime.ready(backend)
    monkeypatch.setattr(backend.socket, "bytesToWrite", lambda: 3_000_000)
    backend.append(b"\x00\x00")
    assert backend.events["failed"] == [
        "La connexion est trop lente pour la dictée en direct. Réessayez."
    ]
    assert backend.audio_bytes == 0
