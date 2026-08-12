"""Text prompt orchestration for the macOS menu-bar application."""

from __future__ import annotations

import logging
import time
import uuid

from pynput.keyboard import Controller, Key
from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu

from src.api.openai_client import OpenAIClient
from src.ui.prompt_dialog import PromptDialog
from src.ui.response_window import ResponseWindow
from src.utils.clipboard_manager import ClipboardManager
from src.utils.loading_indicator import SimpleLoadingIndicator
from src.utils.logger import log
from src.utils.safe_dialogs import SafeDialogs
from src.utils.text_inserter import TextInserter
from src.utils.window_target import PasteTarget


COPY_DELAY = 0.18
RESTORE_DELAY = 0.10


class ContextMenuManager(QObject):
    """Coordinate selection, prompt choice, API calls and response insertion."""

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.keyboard = Controller()
        self.api_client = self._create_api_client()
        self.response_window = ResponseWindow()
        self.response_window.retry_requested.connect(self.on_retry_requested)
        self._pending_requests = {}
        self._active_response_request_id = None
        self._retired_clients = []
        self._menu_open = False
        self._active_menu = None
        self._prompt_dialog = None
        self._closed = False
        self._connect_api_client(self.api_client)

    def _create_api_client(self):
        return OpenAIClient(
            settings=self.settings,
            api_key=self.settings.get_api_key(),
        )

    def _connect_api_client(self, client) -> None:
        client.request_started_scoped.connect(self.on_request_started_scoped)
        client.request_finished_scoped.connect(self.on_request_finished_scoped)
        client.request_error_scoped.connect(self.on_request_error_scoped)

    def _disconnect_api_client(self, client) -> None:
        try:
            client.request_started_scoped.disconnect(self.on_request_started_scoped)
            client.request_finished_scoped.disconnect(self.on_request_finished_scoped)
            client.request_error_scoped.disconnect(self.on_request_error_scoped)
        except (TypeError, RuntimeError):
            pass

    def _press_keyboard_shortcut(self, *keys) -> None:
        pressed = []
        try:
            for key in keys:
                self.keyboard.press(key)
                pressed.append(key)
        finally:
            for key in reversed(pressed):
                try:
                    self.keyboard.release(key)
                except Exception:
                    pass

    def _try_get_selected_text(self, target=None) -> str:
        if target is None:
            target = PasteTarget.capture()
        if target is None:
            return ""

        snapshot = ClipboardManager.capture_snapshot()
        sentinel = f"__SUPERMENU_EMPTY_SELECTION_{time.monotonic_ns()}__"
        selected_text = ""
        clipboard_changed = False
        try:
            if not ClipboardManager.set_clipboard_text_safe(sentinel):
                return ""
            clipboard_changed = True
            if not target.activate_and_verify():
                return ""
            self._press_keyboard_shortcut(Key.cmd, "c")
            time.sleep(COPY_DELAY)
            selected_text = ClipboardManager.get_clipboard_text_safe()
            if not selected_text or selected_text == sentinel:
                return ""
            return selected_text
        except Exception as exc:
            log(f"Lecture de la sélection impossible : {exc}", logging.WARNING)
            return ""
        finally:
            if clipboard_changed:
                time.sleep(RESTORE_DELAY)
                expected = selected_text if selected_text else sentinel
                ClipboardManager.restore_if_unchanged(snapshot, expected)

    def show_menu(self) -> None:
        if self._closed or self._menu_open:
            return
        target = PasteTarget.capture()
        selected_text = self._try_get_selected_text(target)
        menu = QMenu()
        self._menu_open = True
        self._active_menu = menu
        for prompt_id, prompt in sorted(
            self.settings.get_prompts().items(),
            key=lambda item: item[1].get("position", 999),
        ):
            action = menu.addAction(prompt["name"])
            action.setEnabled(bool(selected_text))
            action.setData(("prompt", prompt_id))
        menu.addSeparator()
        custom_action = menu.addAction("Mode personnalisé")
        custom_action.setData(("custom", None))

        def cleanup_menu():
            if self._active_menu is not menu:
                return
            self._active_menu = None
            self._menu_open = False
            menu.deleteLater()

        def handle_action(chosen):
            data = chosen.data()
            cleanup_menu()
            if self._closed or not data:
                return
            action_kind, prompt_id = data
            if action_kind == "prompt":
                self._handle_prompt(prompt_id, selected_text, target)
            else:
                self._handle_custom(selected_text, target)

        menu.triggered.connect(handle_action)
        menu.aboutToHide.connect(lambda: QTimer.singleShot(0, cleanup_menu))
        menu.popup(QCursor.pos())

    def show_custom_mode(self) -> None:
        target = PasteTarget.capture()
        selected_text = self._try_get_selected_text(target)
        self._handle_custom(selected_text, target)

    def run_prompt_hotkey(self, prompt_id: str) -> None:
        target = PasteTarget.capture()
        selected_text = self._try_get_selected_text(target)
        if not selected_text:
            SimpleLoadingIndicator.show_near_cursor(
                "Aucun texte sélectionné",
                duration_ms=1800,
            )
            return
        self._handle_prompt(prompt_id, selected_text, target)

    def _handle_prompt(self, prompt_id: str, text: str, target) -> None:
        prompt = self.settings.get_prompt(prompt_id)
        if not prompt or not text:
            return
        insert_directly = bool(prompt.get("insert_directly", False))
        if not insert_directly:
            self._prepare_response_window(
                prompt["status"],
                prompt["prompt"],
                text,
                target,
            )
        self._send_request(
            prompt["prompt"],
            text,
            insert_directly=insert_directly,
            target=target,
            direct_status=f"Envoyé — {prompt['status']}",
        )

    def _handle_custom(self, selected_text: str, target) -> None:
        if self._closed:
            return
        if self._prompt_dialog is not None:
            self._prompt_dialog.raise_()
            self._prompt_dialog.activateWindow()
            return
        dialog = PromptDialog(selected_text or "", None)
        self._prompt_dialog = dialog

        def finish_prompt(result):
            prompt = dialog.get_prompt()
            self._prompt_dialog = None
            dialog.deleteLater()
            if (
                self._closed
                or result != PromptDialog.DialogCode.Accepted
                or not prompt
            ):
                return
            content = selected_text or ""
            self._prepare_response_window(
                "Traitement en cours…",
                prompt,
                content,
                target,
            )
            self._send_request(prompt, content, target=target)

        dialog.finished.connect(finish_prompt)
        dialog.open()

    def _prepare_response_window(
        self,
        status: str,
        prompt: str,
        content: str,
        target,
    ) -> None:
        self.response_window.set_status(status)
        self.response_window.set_trigger_position(QCursor.pos())
        self.response_window.set_paste_target(target)
        self.response_window.store_request(prompt, content)
        self.response_window.present()

    def show_response_window(self) -> None:
        self.response_window.set_trigger_position(None)
        self.response_window.present()

    def _send_request(
        self,
        prompt,
        content,
        insert_directly=False,
        *,
        target=None,
        include_reasoning=None,
        direct_status=None,
    ) -> str:
        request_id = uuid.uuid4().hex
        if self._closed:
            return request_id
        client = self.api_client
        indicator = None
        if insert_directly:
            indicator = SimpleLoadingIndicator.show_near_cursor(
                direct_status or "Réponse en attente…"
            )
        self._pending_requests[request_id] = {
            "client": client,
            "insert_directly": bool(insert_directly),
            "target": target,
            "indicator": indicator,
        }
        if not insert_directly:
            self._active_response_request_id = request_id
        try:
            client.send_request(
                prompt,
                content,
                insert_directly=insert_directly,
                include_reasoning=include_reasoning,
                request_id=request_id,
                target=target,
            )
        except Exception as exc:
            self.on_request_error_scoped(request_id, str(exc))
        return request_id

    def on_request_started_scoped(self, request_id, insert_directly) -> None:
        if self._closed:
            return
        if not insert_directly and request_id == self._active_response_request_id:
            self.response_window.set_loading(True)

    def on_request_finished_scoped(
        self,
        request_id,
        response,
        insert_directly,
        target,
    ) -> None:
        if self._closed:
            return
        request = self._pending_requests.pop(request_id, None)
        if request is None:
            return
        client = request["client"]
        if request["insert_directly"] or insert_directly:
            safe_target = request.get("target") or target
            inserted = TextInserter().insert_text(response, target=safe_target)
            indicator = request.get("indicator")
            if indicator is not None:
                indicator.set_message(
                    "Réponse insérée" if inserted else "Insertion annulée"
                )
                indicator.move_near_cursor()
                QTimer.singleShot(1600, indicator.close)
            if not inserted:
                SafeDialogs.show_information(
                    "Insertion annulée",
                    "L'application cible a changé ou n'est plus disponible.",
                )
            self._release_retired_client_if_idle(client)
            return
        if request_id == self._active_response_request_id:
            self.response_window.set_response(response)
            self.response_window.set_loading(False)
        self._release_retired_client_if_idle(client)

    def on_request_error_scoped(self, request_id, error) -> None:
        if self._closed:
            return
        request = self._pending_requests.pop(request_id, None)
        if request is None:
            return
        if (
            not request["insert_directly"]
            and request_id == self._active_response_request_id
        ):
            self.response_window.set_response(f"Erreur : {error}")
            self.response_window.set_loading(False)
        else:
            indicator = request.get("indicator")
            if indicator is not None:
                indicator.set_message("Échec du traitement")
                QTimer.singleShot(1800, indicator.close)
            SafeDialogs.show_critical("Erreur de traitement", str(error))
        self._release_retired_client_if_idle(request["client"])

    def on_retry_requested(self) -> None:
        if self._closed:
            return
        prompt, content = self.response_window.get_last_request()
        if prompt is not None:
            self._send_request(prompt, content or "")

    def _release_retired_client_if_idle(self, client) -> None:
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

    def update_client_config(self) -> None:
        self.settings.sync()
        previous = self.api_client
        self._retired_clients.append(previous)
        self.api_client = self._create_api_client()
        self._connect_api_client(self.api_client)
        self._release_retired_client_if_idle(previous)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._active_menu is not None:
            active_menu = self._active_menu
            self._active_menu = None
            active_menu.close()
            active_menu.deleteLater()
        if self._prompt_dialog is not None:
            self._prompt_dialog.reject()
            self._prompt_dialog = None
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
