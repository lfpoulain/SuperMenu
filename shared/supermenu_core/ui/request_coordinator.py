"""Scoped AI request lifecycle shared by the Windows and macOS context menus."""

import logging
import uuid
from dataclasses import dataclass

from PySide6.QtCore import QObject
from PySide6.QtGui import QCursor

from supermenu_core.api.openai_client import clear_capabilities_cache
from supermenu_core.config.feature_modes import effective_model_target
from supermenu_core.config.model_target import ModelTargetSettings
from supermenu_core.ui.loading_indicator import SimpleLoadingIndicator

logger = logging.getLogger("SuperMenu.core.requests")


@dataclass(frozen=True)
class RequestFeedback:
    """Wording each platform shows around a request.

    ``response_error`` and ``send_error`` are format strings receiving
    ``error``: the first is shown in the response window, the second is the
    error reported when a client refuses a request before sending it.
    """

    direct_pending: str
    response_error: str
    send_error: str


class PromptRequestCoordinator(QObject):
    """Track every AI request by id from submission to its outcome.

    Each request remembers the client serving it, whether its answer is pasted
    directly or shown in the response window, its paste target and its loading
    indicator; a direct request also keeps its prompt so that a refused
    insertion can still show and retry the answer. Only the latest
    response-window request may update the window: the late result or failure
    of a request it replaced is dropped. A prompt bound to its own model gets
    a dedicated client, closed once no request uses it; the default client is
    replaced the same way when the configuration changes.

    Platforms provide the client factory, the direct insertion (native paste,
    feedback and what to do with a refused answer), the report of a failed
    direct request, the wording in ``REQUEST_FEEDBACK`` and the release of
    their own menus, dialogs and dictation.
    """

    REQUEST_FEEDBACK: RequestFeedback

    def __init__(self, settings, response_window_factory):
        super().__init__()
        self.settings = settings
        self.api_client = self._create_api_client()
        self.response_window = response_window_factory()
        self.response_window.retry_requested.connect(self.on_retry_requested)
        self._pending_requests = {}
        self._active_response_request_id = None
        self._retired_clients = []
        self._closed = False
        self._connect_api_client(self.api_client)

    # Platform hooks -------------------------------------------------------

    def _create_api_client(self, settings=None):
        """Return a client exposing the scoped request signals."""
        raise NotImplementedError

    def _insert_directly(self, response, target, indicator, client, request=None):
        """Paste a direct answer, report it, then release ``client`` if idle."""
        raise NotImplementedError

    def _report_direct_failure(self, request, error):
        """Tell the user that a direct request failed."""
        raise NotImplementedError

    def _retry_refused(self, prompt, content):
        """Return True, after informing the user, when a retry must not run."""
        return False

    def _response_window_target(self, target):
        """The paste target the response window keeps for « Insérer le texte »."""
        return target

    def _release_platform_resources(self):
        """Close menus, dialogs and dictation before the requests are dropped."""

    # Clients --------------------------------------------------------------

    def _connect_api_client(self, client):
        client.request_started_scoped.connect(self.on_request_started_scoped)
        client.request_finished_scoped.connect(self.on_request_finished_scoped)
        client.request_error_scoped.connect(self.on_request_error_scoped)
        if hasattr(client, "request_progress_scoped"):
            client.request_progress_scoped.connect(self.on_request_progress_scoped)

    def _disconnect_api_client(self, client):
        try:
            client.request_started_scoped.disconnect(self.on_request_started_scoped)
            client.request_finished_scoped.disconnect(self.on_request_finished_scoped)
            client.request_error_scoped.disconnect(self.on_request_error_scoped)
            if hasattr(client, "request_progress_scoped"):
                client.request_progress_scoped.disconnect(self.on_request_progress_scoped)
        except (TypeError, RuntimeError):
            pass

    def _release_retired_client_if_idle(self, client):
        if client is self.api_client:
            return
        if any(
            request.get("client") is client
            for request in self._pending_requests.values()
        ):
            return
        self._disconnect_api_client(client)
        client.close()
        try:
            self._retired_clients.remove(client)
        except ValueError:
            pass

    def update_client_config(self):
        """Replace the default client; in-flight requests keep their own."""
        if self._closed:
            return
        self.settings.sync()
        # Another server may now answer at the same address: probe it again.
        clear_capabilities_cache()
        previous = self.api_client
        if previous is not None:
            self._retired_clients.append(previous)
        self.api_client = self._create_api_client()
        self._connect_api_client(self.api_client)
        if previous is not None:
            self._release_retired_client_if_idle(previous)

    # Response window ------------------------------------------------------

    def _present_response_window(self):
        if self._closed:
            return
        self.response_window.present()

    def show_response_window(self):
        """Open the response window from the application's own interface."""
        if self._closed:
            return
        self.response_window.set_trigger_position(None)
        self._present_response_window()

    def _prepare_response_window(self, status, prompt, content, target, position=None):
        """Show the pending request near the cursor and keep it for a retry."""
        self.response_window.set_status(status)
        self.response_window.set_trigger_position(
            QCursor.pos() if position is None else position
        )
        self.response_window.set_paste_target(self._response_window_target(target))
        self.response_window.store_request(prompt, content)
        self._present_response_window()

    def on_request_finished(self, response):
        """Show an answer in the response window."""
        if self._closed:
            return
        self.response_window.set_response(response)
        self.response_window.set_loading(False)

    def on_request_error(self, error):
        """Show an error in the response window, where it is never inserted."""
        if self._closed:
            return
        self.response_window.set_error(
            self.REQUEST_FEEDBACK.response_error.format(error=error)
        )
        self.response_window.set_loading(False)

    # Requests -------------------------------------------------------------

    def _send_request(
        self,
        prompt,
        content,
        insert_directly=False,
        *,
        target=None,
        include_reasoning=None,
        direct_status=None,
        reasoning_mode="default",
        model_target=None,
    ):
        """Register request state before the client can emit synchronously."""
        if self._closed:
            return None
        # Without the advanced features every prompt uses the text settings;
        # the prompt keeps its stored model for when they are turned back on.
        # Covers retries and kept answers too.
        model_target = effective_model_target(self.settings, model_target)

        request_id = uuid.uuid4().hex
        client = self.api_client
        indicator = None
        if insert_directly:
            indicator = SimpleLoadingIndicator.show_near_cursor(
                direct_status or self.REQUEST_FEEDBACK.direct_pending
            )
        self._pending_requests[request_id] = {
            "client": client,
            "insert_directly": bool(insert_directly),
            "target": target,
            "indicator": indicator,
        }
        if insert_directly:
            # Kept so that a refused insertion can still show and retry it.
            self._pending_requests[request_id].update(
                prompt=prompt,
                content=content,
                reasoning_mode=reasoning_mode,
                model_target=model_target,
            )
        else:
            self._active_response_request_id = request_id
            self.response_window.last_reasoning_mode = reasoning_mode
            self.response_window.last_model_target = dict(model_target or {})
        try:
            if model_target:
                client = self._create_api_client(
                    ModelTargetSettings(self.settings, model_target)
                )
                self._retired_clients.append(client)
                self._connect_api_client(client)
                self._pending_requests[request_id]["client"] = client
            client.send_request(
                prompt,
                content,
                insert_directly=insert_directly,
                include_reasoning=include_reasoning,
                request_id=request_id,
                target=target,
                **({"reasoning_mode": reasoning_mode} if reasoning_mode != "default" else {}),
            )
        except Exception as exc:
            self.on_request_error_scoped(
                request_id,
                self.REQUEST_FEEDBACK.send_error.format(error=exc),
            )
        return request_id

    def on_retry_requested(self):
        if self._closed:
            return
        prompt, content = self.response_window.get_last_request()
        if prompt is None or self._retry_refused(prompt, content):
            return
        logger.info("Retry de la dernière requête...")
        self._send_request(
            prompt,
            content or "",
            reasoning_mode=getattr(self.response_window, "last_reasoning_mode", "default"),
            model_target=getattr(self.response_window, "last_model_target", None),
        )

    def on_request_started_scoped(self, request_id, insert_directly):
        if self._closed:
            return
        if not insert_directly and request_id == self._active_response_request_id:
            self.response_window.set_loading(True)

    def on_request_progress_scoped(self, request_id, details):
        request = self._pending_requests.get(request_id)
        if self._closed or request is None or not isinstance(details, dict):
            return
        stage = details.get("stage")
        if not stage or "elapsed_seconds" in details:
            return
        indicator = request.get("indicator")
        if indicator is not None:
            indicator.set_message(stage)
        elif request_id == self._active_response_request_id:
            self.response_window.set_status(stage)

    def on_request_finished_scoped(self, request_id, response, insert_directly, target):
        if self._closed:
            return
        request = self._pending_requests.pop(request_id, None)
        if request is None:
            return
        client = request["client"]
        if request["insert_directly"] or insert_directly:
            self._insert_directly(
                response,
                request.get("target") or target,
                request.get("indicator"),
                client,
                request=request,
            )
            return
        if request_id == self._active_response_request_id:
            self.on_request_finished(response)
        self._release_retired_client_if_idle(client)

    def on_request_error_scoped(self, request_id, error):
        if self._closed:
            return
        request = self._pending_requests.pop(request_id, None)
        if request is None:
            return
        if (
            not request["insert_directly"]
            and request_id == self._active_response_request_id
        ):
            self.on_request_error(error)
        elif request["insert_directly"]:
            self._report_direct_failure(request, error)
        else:
            # A newer prompt already owns the response window: the late
            # failure of the request it replaced concerns nothing on screen.
            logger.info("Erreur ignorée : la requête a été remplacée par une plus récente")
        self._release_retired_client_if_idle(request["client"])

    # Shutdown -------------------------------------------------------------

    def close(self):
        """Stop native/UI resources and reject late API completions."""
        if self._closed:
            return
        self._closed = True
        self._release_platform_resources()
        clients = {self.api_client, *self._retired_clients}
        for request in self._pending_requests.values():
            indicator = request.get("indicator")
            if indicator is not None:
                indicator.close()
            clients.add(request.get("client"))
        self._pending_requests.clear()
        self._retired_clients.clear()
        for client in clients:
            if client is None:
                continue
            self._disconnect_api_client(client)
            client.close()
        self.response_window.close()
