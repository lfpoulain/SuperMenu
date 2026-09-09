"""Local Apple Foundation Models provider, isolated from the HTTP clients."""

from __future__ import annotations

import json
import platform
import sys
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from src.utils.paths import resource_path


ERROR_MESSAGES = {
    "os_unsupported": "Apple Intelligence nécessite macOS 26 ou une version ultérieure.",
    "device_not_eligible": "Apple Intelligence nécessite un Mac Apple Silicon compatible.",
    "intelligence_disabled": (
        "Activez Apple Intelligence dans Réglages Système > Apple Intelligence et Siri."
    ),
    "model_not_ready": (
        "Le modèle Apple n’est pas encore prêt. Vérifiez Apple Intelligence dans "
        "Réglages Système et laissez le téléchargement se terminer, puis actualisez."
    ),
    "helper_missing": (
        "Le composant Apple manque dans cette installation. Réinstallez la bêta macOS."
    ),
    "unavailable": "Apple Intelligence n’est pas disponible sur ce Mac actuellement.",
    "context_exceeded": (
        "Le texte et la consigne dépassent la capacité du modèle Apple. "
        "Sélectionnez un passage plus court ou choisissez un autre fournisseur."
    ),
    "guardrail": "Apple Intelligence a refusé de traiter ce contenu selon ses règles de sécurité.",
    "refusal": "Le modèle Apple a refusé cette demande. Essayez de reformuler la consigne.",
    "unsupported_language": "Cette langue n’est pas prise en charge par le modèle Apple.",
    "empty_response": "Le modèle Apple a renvoyé une réponse vide. Réessayez.",
    "invalid_request": "La demande Apple est invalide. Vérifiez la consigne du prompt.",
    "generation_failed": "La génération Apple a échoué. Réessayez ou vérifiez Apple Intelligence.",
    "timeout": "Apple Intelligence n’a pas répondu à temps. Réessayez avec un texte plus court.",
    "helper_failed": "Le composant Apple n’a pas pu terminer la demande. Relancez SuperMenu.",
}


def helper_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(resource_path("native", "SuperMenuFoundationModels"))
    return Path(resource_path("build", "native", "SuperMenuFoundationModels"))


def preflight_error() -> str | None:
    if sys.platform != "darwin":
        return "os_unsupported"
    try:
        if int(platform.mac_ver()[0].split(".")[0]) < 26:
            return "os_unsupported"
    except (ValueError, IndexError):
        return "os_unsupported"
    if platform.machine().lower() not in {"arm64", "aarch64"}:
        return "device_not_eligible"
    if not helper_path().is_file():
        return "helper_missing"
    return None


class FoundationModelsRequest(QObject):
    """Run a bundled helper asynchronously using private stdin/stdout pipes."""

    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._done = False
        self._process = QProcess(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: self._fail("timeout"))
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(lambda _error: self._fail("helper_failed"))
        # Framework diagnostics may contain user data: discard, never log them.
        self._process.readyReadStandardError.connect(self._process.readAllStandardError)

    def start(self, payload: dict, *, timeout_ms=120_000):
        error = preflight_error()
        if error:
            QTimer.singleShot(0, lambda: self._fail(error))
            return
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        def write_input():
            self._process.write(data)
            self._process.closeWriteChannel()

        self._process.started.connect(write_input)
        self._timer.start(timeout_ms)
        self._process.start(str(helper_path()), [])

    def _finished(self, exit_code, exit_status):
        if self._done:
            return
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self._fail("helper_failed")
            return
        try:
            reply = json.loads(bytes(self._process.readAllStandardOutput()))
        except (ValueError, UnicodeError):
            self._fail("helper_failed")
            return
        if not isinstance(reply, dict) or reply.get("ok") is not True:
            code = reply.get("code") if isinstance(reply, dict) else None
            self._fail(
                code if isinstance(code, str) and code in ERROR_MESSAGES else "helper_failed"
            )
            return
        self._done = True
        self._timer.stop()
        self.succeeded.emit(reply)

    def _fail(self, code):
        if self._done:
            return
        self.cancel()
        self.failed.emit(ERROR_MESSAGES[code])

    def cancel(self):
        self._done = True
        self._timer.stop()
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(1000)


class AppleFoundationClient(QObject):
    """Implement the scoped request interface used by the macOS context menu."""

    request_started_scoped = Signal(str, bool)
    request_finished_scoped = Signal(str, str, bool, object)
    request_error_scoped = Signal(str, str)

    def __init__(self):
        super().__init__()
        self._requests = {}
        self._closed = False

    def send_request(
        self, prompt, content, insert_directly=False, include_reasoning=None,
        request_id=None, target=None,
    ):
        request_id = request_id or uuid.uuid4().hex
        if self._closed:
            return request_id
        request = FoundationModelsRequest(self)
        self._requests[request_id] = request

        def release():
            self._requests.pop(request_id, None)
            request.deleteLater()

        def failed(message):
            release()
            if not self._closed:
                self.request_error_scoped.emit(request_id, message)

        def finished(reply):
            text = reply.get("content")
            if not isinstance(text, str) or not text.strip():
                failed(ERROR_MESSAGES["empty_response"])
                return
            release()
            if not self._closed:
                self.request_finished_scoped.emit(request_id, text, insert_directly, target)

        request.succeeded.connect(finished)
        request.failed.connect(failed)
        self.request_started_scoped.emit(request_id, insert_directly)
        request.start({"action": "generate", "prompt": prompt, "content": content})
        return request_id

    def close(self):
        self._closed = True
        for request in self._requests.values():
            request.cancel()
            request.deleteLater()
        self._requests.clear()
