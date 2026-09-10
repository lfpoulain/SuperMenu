"""Qt bridge to the embedded Foundry process, shared by settings and text actions."""

from collections import deque
import json
from pathlib import Path
import sys
import uuid

from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    QProcess,
    QProcessEnvironment,
    QTimer,
    Signal,
)

from src.api.foundry_worker import platform_error
from src.config.foundry_models import MAX_INPUT_CHARS


def worker_command():
    if getattr(sys, "frozen", False):
        return sys.executable, ["--foundry-worker"]
    # pythonw uses the same inherited-pipe path as the released windowed exe.
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = str(pythonw) if pythonw.exists() else sys.executable
    return executable, [
        str(Path(__file__).resolve().parents[2] / "run.py"),
        "--foundry-worker",
    ]


class FoundryService(QObject):
    completed = Signal(str, object)
    failed = Signal(str, str)
    progress = Signal(str, object)

    def __init__(self, parent=None, command=None):
        super().__init__(parent)
        self._command = command or worker_command()
        self._queue = deque()
        self._active = None
        self._buffer = b""
        self._closed = False
        self._process = QProcess(self)
        self._process.setStandardErrorFile(QProcess.nullDevice())
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONIOENCODING", "utf-8")
        if getattr(sys, "frozen", False):
            # Reuse the running onefile extraction for this private child.
            environment.remove("PYINSTALLER_RESET_ENVIRONMENT")
        self._process.setProcessEnvironment(environment)
        self._process.started.connect(self._write_active)
        self._process.readyReadStandardOutput.connect(self._read)
        self._process.finished.connect(self._exited)
        self._process.errorOccurred.connect(self._process_error)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._timeout)
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(300000)
        self._idle_timer.timeout.connect(self._stop)

    def submit(self, operation, *, request_id=None, **payload):
        request_id = request_id or uuid.uuid4().hex
        if self._closed:
            return request_id
        self._queue.append({"id": request_id, "operation": operation, **payload})
        QTimer.singleShot(0, self._next)
        return request_id

    def _next(self):
        if self._closed or self._active or not self._queue:
            return
        self._idle_timer.stop()
        self._active = self._queue.popleft()
        timeout = {"download": 1800000, "generate": 600000, "probe": 1800000}
        self._timer.start(timeout.get(self._active["operation"], 90000))
        if self._process.state() == QProcess.NotRunning:
            self._buffer = b""
            program, args = self._command
            self._process.start(program, args)
        else:
            self._write_active()

    def _write_active(self):
        if self._active:
            payload = (
                json.dumps(self._active, ensure_ascii=False).encode("utf-8") + b"\n"
            )
            self._process.write(payload)

    def _read(self):
        self._buffer += bytes(self._process.readAllStandardOutput())
        if len(self._buffer) > 1024 * 1024:
            self._abort("Réponse locale invalide. Réessayez.")
            return
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    continue
            except (ValueError, UnicodeError):
                continue  # Native libraries may write diagnostics to stdout.
            if not self._active or message.get("id") != self._active["id"]:
                continue
            request_id = self._active["id"]
            if "progress" in message:
                self.progress.emit(request_id, message["progress"])
                continue
            self._active = None
            self._timer.stop()
            if "error" in message:
                self.failed.emit(request_id, str(message["error"]))
            elif isinstance(message.get("result"), dict):
                self.completed.emit(request_id, message["result"])
            else:
                self.failed.emit(request_id, "Réponse locale invalide.")
            self._idle_timer.start()
            QTimer.singleShot(0, self._next)

    def _stop(self):
        if self._process.state() != QProcess.NotRunning:
            self._process.kill()
            self._process.waitForFinished(1000)
        self._buffer = b""

    def _abort(self, message):
        active, self._active = self._active, None
        self._timer.stop()
        self._stop()
        if active and not self._closed:
            self.failed.emit(active["id"], message)
        QTimer.singleShot(0, self._next)

    def _timeout(self):
        self._abort(
            "Foundry Local a dépassé le délai. Essayez le modèle 4B ou un texte plus court."
        )

    def _exited(self, *_args):
        if self._active:
            self._abort(
                "Le moteur local s'est arrêté. Vérifiez la mémoire et les pilotes, puis réessayez."
            )

    def _process_error(self, error):
        if error == QProcess.FailedToStart:
            self._abort(
                "Impossible de démarrer le moteur Foundry embarqué. Réinstallez la bêta."
            )

    def cancel(self, request_id):
        self._queue = deque(r for r in self._queue if r["id"] != request_id)
        if self._active and self._active["id"] == request_id:
            self._abort("Opération locale annulée.")

    def close(self):
        self._closed = True
        self._active = None
        self._queue.clear()
        self._timer.stop()
        self._idle_timer.stop()
        self._stop()


def get_foundry_service():
    app = QCoreApplication.instance()
    if app is None:
        raise RuntimeError("A Qt application is required")
    service = getattr(app, "_supermenu_foundry_service", None)
    if service is None:
        service = FoundryService(app)
        app._supermenu_foundry_service = service
        app.aboutToQuit.connect(service.close)
    return service


class FoundryClient(QObject):
    request_started_scoped = Signal(str, bool)
    request_finished_scoped = Signal(str, str, bool, object)
    request_error_scoped = Signal(str, str)

    def __init__(self, settings, service=None):
        super().__init__()
        self.model = settings.get_foundry_model()
        self.device = settings.get_foundry_device()
        self._service = service or get_foundry_service()
        self._pending = {}
        self._closed = False
        self._service.completed.connect(self._completed)
        self._service.failed.connect(self._failed)

    def send_request(
        self,
        prompt,
        content,
        insert_directly=False,
        include_reasoning=None,
        request_id=None,
        target=None,
    ):
        request_id = request_id or uuid.uuid4().hex
        if self._closed:
            return request_id
        self._pending[request_id] = (bool(insert_directly), target)
        self.request_started_scoped.emit(request_id, bool(insert_directly))
        error = platform_error()
        if not isinstance(prompt, str) or not isinstance(content, str):
            error = "Cette bêta locale accepte uniquement du texte."
        elif content.startswith("data:image/"):
            error = "La capture d'écran n'est pas encore prise en charge par cette bêta locale."
        elif len(prompt) + len(content) > MAX_INPUT_CHARS:
            error = "Le texte dépasse la limite locale de 16 000 caractères. Réduisez la sélection."
        if error:
            self._failed(request_id, error)
        else:
            self._service.submit(
                "generate",
                request_id=request_id,
                model=self.model,
                device=self.device,
                prompt=prompt,
                content=content,
            )
        return request_id

    def _completed(self, request_id, result):
        if request_id not in self._pending or self._closed:
            return
        insert, target = self._pending.pop(request_id)
        self.request_finished_scoped.emit(request_id, result["text"], insert, target)

    def _failed(self, request_id, message):
        if request_id in self._pending and not self._closed:
            self._pending.pop(request_id)
            self.request_error_scoped.emit(request_id, message)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._service.completed.disconnect(self._completed)
        self._service.failed.disconnect(self._failed)
        for request_id in list(self._pending):
            self._service.cancel(request_id)
        self._pending.clear()
