"""One local voice worker per app, with short-lived, isolated dictation leases."""

import base64
import json
import time
import uuid

from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    QProcess,
    QProcessEnvironment,
    QTimer,
    Signal,
)

from .backends import SpeechBackend


class ResidentSpeechBackend(SpeechBackend):
    def __init__(self, command, options, idle_seconds=300, parent=None):
        super().__init__(parent)
        self.command, self.options = command, dict(options)
        self.idle_seconds = idle_seconds
        self.session_id = uuid.uuid4().hex
        self.closed = False
        self.service = get_resident_service()

    def start(self):
        if not self.closed:
            self.service.begin(self)

    def append(self, pcm):
        self.service.append(self, pcm)

    def finish(self):
        self.service.finish(self)

    def cancel(self):
        if not self.closed:
            self.closed = True
            self.service.cancel(self)


class ResidentSpeechService(QObject):
    state_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.active = None
        self.pending = None
        self.draining = None
        self.key = None
        self.buffer = b""
        self.loaded = False
        self.idle_seconds = 300
        self.idle_since = None
        self.closed = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._timeout)
        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self.unload_idle)

    @property
    def busy(self):
        return self.active is not None or self.draining is not None

    @staticmethod
    def backend_key(backend):
        return (
            backend.command[0],
            tuple(backend.command[1]),
            backend.options.get("provider"),
            backend.options.get("device", "auto"),
            backend.options.get("language", ""),
        )

    def begin(self, backend):
        if self.active is backend:
            return
        if self.closed or self.active or self.pending:
            backend.closed = True
            backend.failed.emit(
                "Une dictée locale est déjà en cours. Terminez-la avant d’en ouvrir une autre."
            )
            return
        if self.draining:
            self.pending = backend
            return
        key = self.backend_key(backend)
        if self.key != key:
            self._stop()
        self.key = key
        self.idle_timer.stop()
        self.idle_since = None
        self.idle_seconds = backend.idle_seconds
        self.active = backend
        self.timer.start(120_000)
        if self.process is None:
            self._launch(backend.command)
        else:
            self._start_request()
        self.state_changed.emit()

    def _launch(self, command):
        process = self.process = QProcess(self)
        self.buffer = b""
        process.setStandardErrorFile(QProcess.nullDevice())
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.remove("PYINSTALLER_RESET_ENVIRONMENT")
        process.setProcessEnvironment(env)
        process.started.connect(
            lambda: self._start_request() if self.process is process else None
        )
        process.readyReadStandardOutput.connect(lambda: self._read(process))
        process.errorOccurred.connect(lambda _e: self._process_failed(process))
        process.finished.connect(lambda *_: self._process_failed(process))
        process.start(*command)

    def _start_request(self):
        if self.active:
            self._send(
                {
                    **self.active.options,
                    "action": "start",
                    "keep_alive": True,
                    "session_id": self.active.session_id,
                }
            )

    def _send(self, message):
        if self.process is None:
            return
        if self.process.bytesToWrite() > 2_000_000:
            self._fail(
                "Le moteur vocal ne suit plus le microphone. Réessayez après avoir fermé les tâches lourdes."
            )
            return
        self.process.write((json.dumps(message) + "\n").encode("utf-8"))

    def append(self, backend, pcm):
        if self.active is backend and not backend.closed:
            self._send(
                {
                    "session_id": backend.session_id,
                    "audio": base64.b64encode(pcm).decode("ascii"),
                }
            )

    def finish(self, backend):
        if self.active is backend and not backend.closed:
            self.timer.start(60_000)
            self._send({"session_id": backend.session_id, "action": "stop"})

    def cancel(self, backend):
        if self.pending is backend:
            self.pending = None
        if self.active is not backend:
            return
        self.active = None
        if self.loaded:
            self.draining = backend.session_id
            self.timer.start(15_000)
            self._send({"session_id": backend.session_id, "action": "cancel"})
            self.state_changed.emit()
        else:
            self._stop()

    def _read(self, process):
        if self.process is not process:
            return
        self.buffer += bytes(process.readAllStandardOutput())
        if len(self.buffer) > 2_000_000:
            self._fail("Réponse invalide du moteur vocal.")
            return
        while b"\n" in self.buffer and self.process is process:
            line, self.buffer = self.buffer.split(b"\n", 1)
            try:
                self._event(json.loads(line))
            except (ValueError, KeyError, TypeError):
                self._fail("Réponse invalide du moteur vocal.")

    def _event(self, event):
        if not isinstance(event, dict):
            raise ValueError("event")
        sid, kind = event.get("session_id"), event["event"]
        if self.draining and sid == self.draining:
            if kind in {"cancelled", "complete"}:
                self.draining = None
                self._idle()
                pending, self.pending = self.pending, None
                if pending and not pending.closed:
                    self.begin(pending)
            elif kind == "error":
                self._fail(str(event["message"]))
            return
        backend = self.active
        if backend is None or backend.closed or sid != backend.session_id:
            return
        if kind == "ready":
            self.loaded = True
            self.timer.stop()
            self.state_changed.emit()
            backend.ready.emit()
        elif kind == "transcript":
            backend.transcript.emit(str(event["text"]))
        elif kind == "progress":
            backend.phase = str(event.get("phase", ""))
            backend.progress.emit(
                str(event.get("message", "Préparation…")), int(event.get("percent", -1))
            )
        elif kind == "complete":
            text = str(event["text"])
            self.active = None
            backend.closed = True
            self._idle()
            backend.completed.emit(text)
        elif kind == "error":
            self._fail(str(event["message"]))
        else:
            raise ValueError("event")

    def _idle(self):
        self.timer.stop()
        self.idle_since = time.monotonic()
        self.set_idle_seconds(self.idle_seconds)
        self.state_changed.emit()

    def set_idle_seconds(self, seconds):
        self.idle_seconds = max(-1, int(seconds))
        self.idle_timer.stop()
        if self.busy or not self.loaded or self.idle_since is None:
            return
        if self.idle_seconds < 0:
            return
        remaining = self.idle_seconds - (time.monotonic() - self.idle_since)
        if remaining <= 0:
            self.unload_idle()
        else:
            self.idle_timer.start(max(1, round(remaining * 1000)))

    def unload_idle(self):
        if self.busy:
            return False
        self._stop()
        return True

    def _stop(self):
        self.timer.stop()
        self.idle_timer.stop()
        process, self.process = self.process, None
        self.loaded = False
        self.draining = None
        self.idle_since = None
        self.buffer = b""
        self.key = None
        if process is not None:
            if process.state() != QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(1000)
            process.deleteLater()
        self.state_changed.emit()

    def _fail(self, message):
        active, self.active = self.active, None
        pending, self.pending = self.pending, None
        self._stop()
        for backend in (active, pending):
            if backend and not backend.closed:
                backend.closed = True
                backend.failed.emit(message)

    def _process_failed(self, process):
        if self.process is process:
            self._read(process)
            if self.process is process:
                self._fail(
                    "Le moteur vocal local s’est arrêté. La prochaine dictée rechargera le modèle."
                )

    def _timeout(self):
        if self.draining:
            pending, self.pending = self.pending, None
            self._stop()
            if pending and not pending.closed:
                self.begin(pending)
        else:
            self._fail("Le moteur vocal n’a pas répondu à temps. Réessayez.")

    def close(self):
        self.closed = True
        for backend in (self.active, self.pending):
            if backend:
                backend.closed = True
        self.active = self.pending = None
        self._stop()


def get_resident_service():
    app = QCoreApplication.instance()
    if app is None:
        raise RuntimeError("A Qt application is required")
    service = getattr(app, "_supermenu_resident_speech", None)
    if service is None:
        service = ResidentSpeechService(app)
        app._supermenu_resident_speech = service
        app.aboutToQuit.connect(service.close)
    return service
