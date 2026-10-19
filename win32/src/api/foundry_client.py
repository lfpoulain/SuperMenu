"""Qt bridge to the embedded Foundry process, shared by settings and text actions."""

from collections import deque
import json
import logging
from pathlib import Path
import sys
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

from src.api.foundry_worker import platform_error
from src.config.foundry_models import MAX_INPUT_CHARS
from supermenu_core.config.model_memory import MODEL_IDLE_CHOICES

# Silence budgets: every progress message of the active request re-arms its
# budget, so a download that keeps progressing is never killed.
OPERATION_TIMEOUTS_MS = {"download": 1800000, "generate": 600000, "probe": 1800000}
DEFAULT_TIMEOUT_MS = 90000
# Reasoning allows 8192 output tokens instead of 2048: same throughput budget.
REASONING_GENERATION_TIMEOUT_MS = 4 * OPERATION_TIMEOUTS_MS["generate"]
# A killed worker may need a few seconds to release native (CUDA) memory.
RETIRE_GRACE_MS = 15000
TIMEOUT_MESSAGES = {
    "download": (
        "Le téléchargement du modèle ne progresse plus. "
        "Vérifiez la connexion, puis relancez le téléchargement."
    ),
    "probe": (
        "La vérification de Foundry Local n'a pas abouti à temps. "
        "Vérifiez la connexion et le pilote GPU, puis réessayez."
    ),
    "generate": "Foundry Local a dépassé le délai. Essayez le modèle 4B ou un texte plus court.",
}
REASONING_TIMEOUT_MESSAGE = (
    "Foundry Local a dépassé le délai. Essayez sans raisonnement, "
    "avec le modèle 4B ou avec un texte plus court."
)
DEFAULT_TIMEOUT_MESSAGE = "Le moteur local n'a pas répondu à temps. Réessayez."
# The worker runs one native operation at a time.
WAIT_MESSAGES = {
    "download": "En attente de la fin du téléchargement d'un modèle local…",
    "probe": "En attente de la fin de la vérification de Foundry Local…",
}
# Replace a wait notice once that download or probe is over.
QUEUE_MESSAGE = "En attente de la fin d'une autre requête locale…"
START_MESSAGE = "Démarrage du traitement local…"


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
    state_changed = Signal()

    def __init__(self, parent=None, command=None):
        super().__init__(parent)
        self._command = command or worker_command()
        self._queue = deque()
        self._active = None
        self._buffer = b""
        self._closed = False
        self.loaded = False
        self.idle_seconds = 300
        self._idle_since = None
        # One QProcess per worker launch; a killed worker still exiting is
        # "retiring" and its late signals are ignored.
        self._process = None
        self._retiring = None
        # Request id -> wait notice last shown to that queued request.
        self._wait_notices = {}
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONIOENCODING", "utf-8")
        if getattr(sys, "frozen", False):
            # Reuse the running onefile extraction for this private child.
            environment.remove("PYINSTALLER_RESET_ENVIRONMENT")
        self._environment = environment
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._timeout)
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self.unload_idle)
        self._retire_timer = QTimer(self)
        self._retire_timer.setSingleShot(True)
        self._retire_timer.timeout.connect(self._retire_expired)

    @property
    def busy(self):
        return bool(self._active or self._queue)

    def set_idle_seconds(self, value):
        value = int(value)
        if value not in MODEL_IDLE_CHOICES:
            raise ValueError("Délai de déchargement inconnu")
        self.idle_seconds = value
        self._idle_timer.stop()
        if self.busy or not self.loaded or self._idle_since is None or value < 0:
            return
        remaining = value - (time.monotonic() - self._idle_since)
        if remaining <= 0:
            self.unload_idle()
        else:
            self._idle_timer.start(max(1, round(remaining * 1000)))

    def unload_idle(self):
        if self.busy:
            return False
        self._idle_timer.stop()
        self._idle_since = None
        if self.loaded and self._running():
            self.submit("unload")
        return True

    def _running(self):
        return (
            self._process is not None
            and self._process.state() != QProcess.NotRunning
        )

    def submit(self, operation, *, request_id=None, **payload):
        request_id = request_id or uuid.uuid4().hex
        if self._closed:
            return request_id
        self._queue.append({"id": request_id, "operation": operation, **payload})
        self._idle_timer.stop()
        self.state_changed.emit()
        QTimer.singleShot(0, self._next)
        return request_id

    def _next(self):
        if self._closed or not self._queue:
            return
        if self._active:
            self._announce_wait()
            return
        if self._retiring is not None:
            self._announce_wait()  # A cancelled download no longer blocks.
            return  # Resumed once the killed worker has really exited.
        self._idle_timer.stop()
        self._idle_since = None
        self._active = self._queue.popleft()
        self.state_changed.emit()
        self._timer.start(self._timeout_ms(self._active))
        if not self._running():
            self._launch()
        else:
            self._write_active()
        self._announce_wait()

    def _launch(self):
        previous = self._process
        if previous is not None and previous.state() == QProcess.NotRunning:
            previous.deleteLater()
        process = self._process = QProcess(self)
        process.setStandardErrorFile(QProcess.nullDevice())
        process.setProcessEnvironment(self._environment)
        process.started.connect(
            lambda: self._write_active() if self._process is process else None
        )
        process.readyReadStandardOutput.connect(
            lambda: self._read() if self._process is process else None
        )
        process.finished.connect(
            lambda *_args: self._exited() if self._process is process else None
        )
        process.errorOccurred.connect(
            lambda error: self._process_error(error) if self._process is process else None
        )
        self._buffer = b""
        program, args = self._command
        process.start(program, args)

    @staticmethod
    def _timeout_ms(request, details=None):
        operation = request.get("operation")
        if (
            operation == "generate"
            and request.get("reasoning_mode") == "on"
            and isinstance(details, dict)
            and details.get("phase") == "generate"
        ):
            return REASONING_GENERATION_TIMEOUT_MS
        return OPERATION_TIMEOUTS_MS.get(operation, DEFAULT_TIMEOUT_MS)

    def _announce_wait(self):
        # Explain why text actions queued behind a long download do not start,
        # and replace that notice as soon as it no longer applies.
        stage = WAIT_MESSAGES.get(self._active["operation"]) if self._active else None
        notices, self._wait_notices = self._wait_notices, {}
        if self._active and self._active["id"] in notices:
            self.progress.emit(
                self._active["id"], {"phase": "start", "stage": START_MESSAGE}
            )
        for request in list(self._queue):
            notice = stage or (QUEUE_MESSAGE if request["id"] in notices else None)
            if notice:
                self._wait_notices[request["id"]] = notice
                if notices.get(request["id"]) != notice:
                    self.progress.emit(
                        request["id"], {"phase": "queue", "stage": notice}
                    )

    def _write_active(self):
        if self._active and self._process is not None:
            payload = (
                json.dumps(self._active, ensure_ascii=False).encode("utf-8") + b"\n"
            )
            self._process.write(payload)

    def _read(self):
        if self._process is None:
            return
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
                details = message["progress"]
                if isinstance(details, dict) and "elapsed_seconds" in details:
                    logging.getLogger("SuperMenu.Foundry").info("Foundry phase=%s duration=%.3fs", details.get("phase"), details["elapsed_seconds"])
                # The worker is alive and progressing: re-arm its silence budget.
                self._timer.start(self._timeout_ms(self._active, details))
                self.progress.emit(request_id, details)
                continue
            operation = self._active["operation"]
            self.loaded = bool(message.get("loaded_model", self.loaded or (operation == "generate" and "result" in message)))
            self._active = None
            self._timer.stop()
            if "error" in message:
                if operation == "unload":
                    self._stop()
                self.failed.emit(request_id, str(message["error"]))
            elif isinstance(message.get("result"), dict):
                if operation != "unload":
                    self.completed.emit(request_id, message["result"])
            else:
                self.failed.emit(request_id, "Réponse locale invalide.")
            self._idle_since = time.monotonic()
            self.set_idle_seconds(self.idle_seconds)
            self.state_changed.emit()
            QTimer.singleShot(0, self._next)

    def _stop(self):
        self._idle_timer.stop()
        self._idle_since = None
        self.loaded = False
        process, self._process = self._process, None
        if process is not None:
            if process.state() != QProcess.NotRunning:
                process.kill()
                if not process.waitForFinished(1000):
                    # Releasing native memory can outlast the wait: never write
                    # the next request to this dying worker.
                    self._retire(process)
                    process = None
            if process is not None:
                process.deleteLater()
        self._buffer = b""
        self.state_changed.emit()

    def _retire(self, process):
        self._retiring = process
        process.finished.connect(lambda *_args: self._retired(process))
        self._retire_timer.start(RETIRE_GRACE_MS)

    def _retired(self, process):
        process.deleteLater()
        if self._retiring is process:
            self._retiring = None
            self._retire_timer.stop()
            QTimer.singleShot(0, self._next)

    def _retire_expired(self):
        # Never block the queue forever on a worker that cannot exit.
        if self._retiring is not None:
            self._retiring = None
            QTimer.singleShot(0, self._next)

    def _abort(self, message):
        active, self._active = self._active, None
        self._timer.stop()
        self._stop()
        if active and not self._closed:
            self.failed.emit(active["id"], message)
        QTimer.singleShot(0, self._next)

    def _timeout(self):
        active = self._active or {}
        operation = active.get("operation")
        if operation == "generate" and active.get("reasoning_mode") == "on":
            message = REASONING_TIMEOUT_MESSAGE
        else:
            message = TIMEOUT_MESSAGES.get(operation, DEFAULT_TIMEOUT_MESSAGE)
        self._abort(message)

    def _exited(self, *_args):
        if self._active:
            self._abort(
                "Le moteur local s'est arrêté. Vérifiez la mémoire et les pilotes, puis réessayez."
            )
        else:
            self.loaded = False
            self._idle_since = None
            self._idle_timer.stop()
            self._buffer = b""
            self.state_changed.emit()

    def _process_error(self, error):
        if error == QProcess.FailedToStart:
            self._abort(
                "Impossible de démarrer le moteur Foundry embarqué. Réinstallez SuperMenu."
            )

    def cancel(self, request_id):
        self._queue = deque(r for r in self._queue if r["id"] != request_id)
        if self._active and self._active["id"] == request_id:
            self._abort("Opération locale annulée.")
        elif not self.busy:
            self.set_idle_seconds(self.idle_seconds)
            self.state_changed.emit()

    def close(self):
        self._closed = True
        self._active = None
        self._queue.clear()
        self._timer.stop()
        self._idle_timer.stop()
        self._retire_timer.stop()
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
    request_progress_scoped = Signal(str, object)
    request_started_scoped = Signal(str, bool)
    request_finished_scoped = Signal(str, str, bool, object)
    request_error_scoped = Signal(str, str)

    def __init__(self, settings, service=None):
        super().__init__()
        self.model = settings.get_foundry_model()
        self.device = settings.get_foundry_device()
        self._service = service or get_foundry_service()
        if hasattr(self._service, "set_idle_seconds"):
            self._service.set_idle_seconds(settings.get_text_idle_seconds())
        self._pending = {}
        self._closed = False
        self._service.completed.connect(self._completed)
        self._service.failed.connect(self._failed)
        self._service.progress.connect(self._progress)

    def send_request(
        self,
        prompt,
        content,
        insert_directly=False,
        include_reasoning=None,
        request_id=None,
        target=None,
        reasoning_mode="default",
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
                reasoning_mode=reasoning_mode,
            )
        return request_id

    def _progress(self, request_id, details):
        if request_id in self._pending and not self._closed:
            self.request_progress_scoped.emit(request_id, details)

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
        self._service.progress.disconnect(self._progress)
        for request_id in list(self._pending):
            self._service.cancel(request_id)
        self._pending.clear()
