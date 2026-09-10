"""Asynchronous transports; platform workers never run native inference in Qt."""

import base64
import json

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkRequest
from PySide6.QtWebSockets import QWebSocket

from .settings import OPENAI_SPEECH_MODEL


class SpeechBackend(QObject):
    ready = Signal()
    transcript = Signal(str)
    completed = Signal(str)
    failed = Signal(str)
    progress = Signal(str, int)
    result = Signal(object)
    sample_rate = 16000


class ProcessSpeechBackend(SpeechBackend):
    def __init__(self, command, options, parent=None):
        super().__init__(parent)
        self.command, self.options = command, options
        self.process = QProcess(self)
        self.process.setStandardErrorFile(QProcess.nullDevice())
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.remove("PYINSTALLER_RESET_ENVIRONMENT")
        self.process.setProcessEnvironment(env)
        self.process.started.connect(lambda: self._send(self.options))
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.errorOccurred.connect(
            lambda _e: self._fail("Le moteur vocal local n’a pas pu démarrer.")
        )
        self.process.finished.connect(self._exited)
        self.buffer = b""
        self.closed = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(
            lambda: self._fail("Le moteur vocal n’a pas répondu à temps. Réessayez.")
        )

    def start(self):
        self.timer.start(
            1_800_000 if self.options.get("action") == "download" else 120_000
        )
        self.process.start(*self.command)

    def _send(self, data):
        if self.closed:
            return
        if self.process.bytesToWrite() > 2_000_000:
            self._fail(
                "Le moteur vocal ne suit plus le microphone. Arrêtez les tâches lourdes et réessayez."
            )
            return
        self.process.write((json.dumps(data) + "\n").encode("utf-8"))

    def append(self, pcm):
        self._send({"audio": base64.b64encode(pcm).decode("ascii")})

    def finish(self):
        self._send({"action": "stop"})
        self.timer.start(60_000)

    def _read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        if len(self.buffer) > 2_000_000:
            self._fail("Réponse invalide du moteur vocal.")
            return
        while b"\n" in self.buffer and not self.closed:
            line, self.buffer = self.buffer.split(b"\n", 1)
            try:
                event = json.loads(line)
                kind = event["event"]
                if kind == "ready":
                    self.timer.stop()
                    self.ready.emit()
                elif kind == "transcript":
                    self.transcript.emit(str(event["text"]))
                elif kind == "progress":
                    self.progress.emit(
                        str(event.get("message", "Préparation…")),
                        int(event.get("percent", -1)),
                    )
                elif kind in {"complete", "result"}:
                    self.closed = True
                    self.timer.stop()
                    self.process.closeWriteChannel()
                    if kind == "complete":
                        self.completed.emit(str(event["text"]))
                    else:
                        self.result.emit(event["data"])
                elif kind == "error":
                    self._fail(str(event["message"]))
                else:
                    raise ValueError("event")
            except (ValueError, KeyError, TypeError):
                self._fail("Réponse invalide du moteur vocal.")

    def _exited(self, *_args):
        self._read()
        if not self.closed:
            self._fail("Le moteur vocal s’est arrêté avant la fin de la transcription.")

    def _fail(self, message):
        if not self.closed:
            self.cancel()
            self.failed.emit(message)

    def cancel(self):
        self.closed = True
        self.timer.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)


class OpenAISpeechBackend(SpeechBackend):
    sample_rate = 24000

    def __init__(self, api_key, options, parent=None):
        super().__init__(parent)
        self.api_key, self.options = api_key, options
        self.socket = QWebSocket(parent=self)
        self.socket.connected.connect(self._configure)
        self.socket.textMessageReceived.connect(self._receive)
        self.socket.errorOccurred.connect(
            lambda _e: self._fail(
                "Connexion à OpenAI impossible. Vérifiez la connexion et la clé API."
            )
        )
        self.socket.disconnected.connect(
            lambda: self._fail("La connexion OpenAI a été interrompue.")
        )
        self.closed = False
        self.stopping = False
        self.audio_bytes = 0
        self.items = {}
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(
            lambda: self._fail("OpenAI n’a pas répondu à temps. Réessayez.")
        )

    def start(self):
        if not self.api_key:
            QTimer.singleShot(
                0,
                lambda: self._fail(
                    "Ajoutez votre clé API OpenAI dans les réglages pour utiliser la dictée en ligne."
                ),
            )
            return
        request = QNetworkRequest(
            QUrl("wss://api.openai.com/v1/realtime?intent=transcription")
        )
        request.setRawHeader(
            b"Authorization", ("Bearer " + self.api_key).encode("utf-8")
        )
        self.socket.open(request)
        self.timer.start(30_000)

    def _send(self, event):
        if not self.closed:
            self.socket.sendTextMessage(json.dumps(event))

    def _configure(self):
        transcription = {"model": OPENAI_SPEECH_MODEL, "delay": "low"}
        for name in ("languages", "prompt", "keywords"):
            if self.options.get(name):
                transcription[name] = self.options[name]
        self._send(
            {
                "type": "session.update",
                "session": {
                    "type": "transcription",
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcm", "rate": self.sample_rate},
                            "transcription": transcription,
                            "turn_detection": None,
                        }
                    },
                },
            }
        )

    def append(self, pcm):
        if self.socket.bytesToWrite() > 2_000_000:
            self._fail(
                "La connexion est trop lente pour la dictée en direct. Réessayez."
            )
            return
        self.audio_bytes += len(pcm)
        self._send(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm).decode("ascii"),
            }
        )

    def finish(self):
        if self.audio_bytes < self.sample_rate // 5:
            self._fail(
                "L’enregistrement est trop court. Parlez puis terminez la dictée."
            )
            return
        self.stopping = True
        self._send({"type": "input_audio_buffer.commit"})
        self.timer.start(60_000)

    def _receive(self, message):
        if self.closed:
            return
        try:
            event = json.loads(message)
            kind = event.get("type", "")
            if kind == "session.updated":
                self.timer.stop()
                self.ready.emit()
            elif kind.endswith("input_audio_transcription.delta"):
                key = event["item_id"]
                self.items[key] = self.items.get(key, "") + event.get("delta", "")
                self.transcript.emit(" ".join(self.items.values()).strip())
            elif kind.endswith("input_audio_transcription.completed"):
                self.items[event["item_id"]] = event.get("transcript", "")
                text = " ".join(self.items.values()).strip()
                self.transcript.emit(text)
                if self.stopping:
                    self.cancel()
                    self.completed.emit(text)
            elif kind == "error" or kind.endswith("input_audio_transcription.failed"):
                code = event.get("error", {}).get("code", "")
                message = (
                    "Clé API OpenAI absente ou invalide."
                    if code == "invalid_api_key"
                    else (
                        "Votre limite OpenAI est atteinte."
                        if code in {"rate_limit_exceeded", "insufficient_quota"}
                        else "OpenAI a refusé la transcription. Vérifiez l’accès à GPT Live Transcribe, les langues et le vocabulaire dans les réglages."
                    )
                )
                self._fail(message)
        except (ValueError, KeyError, TypeError):
            self._fail("Réponse OpenAI invalide pendant la dictée.")

    def _fail(self, message):
        if not self.closed:
            self.cancel()
            self.failed.emit(message)

    def cancel(self):
        self.closed = True
        self.timer.stop()
        self.socket.abort()
        self.api_key = ""
