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
from src.utils.logger import log, logger
from src.utils.safe_dialogs import SafeDialogs
from src.utils.text_inserter import TextInserter
from src.utils.window_target import (
    PasteTarget,
    activate_current_application,
    current_application_is_active,
)


COPY_DELAY = 0.18
RESTORE_DELAY = 0.10
MENU_ACTIVATION_POLL_MS = 25
MENU_ACTIVATION_MAX_POLLS = 6
MENU_FORCED_ACTIVATION_DELAY_MS = 50
MENU_VISIBILITY_CHECK_DELAY_MS = 350


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
            log("Lecture de la sélection ignorée : aucune application cible")
            return ""

        snapshot = ClipboardManager.capture_snapshot()
        sentinel = f"__SUPERMENU_EMPTY_SELECTION_{time.monotonic_ns()}__"
        selected_text = ""
        clipboard_changed = False
        try:
            if not ClipboardManager.set_clipboard_text_safe(sentinel):
                log("Lecture de la sélection impossible : presse-papiers indisponible")
                return ""
            clipboard_changed = True
            if not target.activate_and_verify():
                log(
                    "Lecture de la sélection impossible : application cible "
                    "non réactivée",
                    logging.WARNING,
                )
                return ""
            self._press_keyboard_shortcut(Key.cmd, "c")
            time.sleep(COPY_DELAY)
            selected_text = ClipboardManager.get_clipboard_text_safe()
            if not selected_text or selected_text == sentinel:
                log("Lecture de la sélection terminée : aucun texte sélectionné")
                return ""
            log(
                "Lecture de la sélection terminée : "
                f"{len(selected_text)} caractère(s) détecté(s)"
            )
            return selected_text
        except Exception:
            logger.exception("Lecture de la sélection impossible")
            return ""
        finally:
            if clipboard_changed:
                time.sleep(RESTORE_DELAY)
                expected = selected_text if selected_text else sentinel
                ClipboardManager.restore_if_unchanged(snapshot, expected)

    def show_menu(self) -> None:
        if self._closed:
            log("Ouverture du menu ignorée : service fermé", logging.WARNING)
            return
        if self._menu_open:
            log("Ouverture du menu ignorée : un menu est déjà ouvert")
            return
        log("Préparation du menu contextuel")
        target = PasteTarget.capture()
        log(
            "Application cible capturée"
            if target is not None
            else "Aucune application cible capturée",
            logging.INFO if target is not None else logging.WARNING,
        )
        selected_text = self._try_get_selected_text(target)
        menu = QMenu()
        self._menu_open = True
        self._active_menu = menu
        action_dispatched = False
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
            log("Menu contextuel fermé")
            if not action_dispatched and target is not None:
                QTimer.singleShot(0, restore_target_after_cancel)

        def restore_target_after_cancel():
            restored = target.activate_and_verify()
            log(
                "Application cible réactivée après fermeture du menu"
                if restored
                else "Application cible non réactivée après fermeture du menu",
                logging.INFO if restored else logging.WARNING,
            )

        def handle_action(chosen):
            nonlocal action_dispatched
            data = chosen.data()
            action_dispatched = bool(data)
            cleanup_menu()
            if self._closed or not data:
                return
            action_kind, prompt_id = data
            log(f"Action du menu déclenchée : {action_kind}")
            if action_kind == "prompt":
                self._handle_prompt(prompt_id, selected_text, target)
            else:
                self._handle_custom(selected_text, target)

        def popup_menu():
            if self._closed or self._active_menu is not menu:
                return
            try:
                menu.popup(QCursor.pos())
                menu.activateWindow()
                menu.raise_()
                window_handle = menu.windowHandle()
                if window_handle is not None:
                    window_handle.requestActivate()
                log("Affichage du menu contextuel demandé à Qt")
                QTimer.singleShot(
                    MENU_VISIBILITY_CHECK_DELAY_MS,
                    verify_menu_visibility,
                )
            except Exception:
                logger.exception("Affichage Qt du menu contextuel impossible")
                cleanup_menu()

        def verify_menu_visibility():
            if self._active_menu is not menu:
                return
            if menu.isVisible():
                log("Menu contextuel visible")
                return
            log(
                "Le menu contextuel n’est pas devenu visible",
                logging.ERROR,
            )
            cleanup_menu()

        def popup_when_application_is_active(poll_number=0):
            if self._closed or self._active_menu is not menu:
                return
            if current_application_is_active():
                log("SuperMenu est active : présentation du menu")
                popup_menu()
                return
            if poll_number < MENU_ACTIVATION_MAX_POLLS:
                QTimer.singleShot(
                    MENU_ACTIVATION_POLL_MS,
                    lambda: popup_when_application_is_active(poll_number + 1),
                )
                return

            forced = activate_current_application(force=True)
            log(
                "Activation de compatibilité demandée à macOS"
                if forced
                else "Activation de compatibilité refusée par macOS",
                logging.WARNING,
            )
            QTimer.singleShot(MENU_FORCED_ACTIVATION_DELAY_MS, popup_menu)

        menu.triggered.connect(handle_action)
        menu.aboutToShow.connect(lambda: log("Signal Qt : menu prêt à apparaître"))
        menu.aboutToHide.connect(lambda: QTimer.singleShot(0, cleanup_menu))
        activation_requested = activate_current_application()
        log(
            "Demande d’activation moderne envoyée à macOS"
            if activation_requested
            else "Demande d’activation macOS indisponible",
            logging.INFO if activation_requested else logging.WARNING,
        )
        QTimer.singleShot(0, popup_when_application_is_active)

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

        def raise_prompt_dialog():
            if self._prompt_dialog is not dialog or not dialog.isVisible():
                return
            dialog.raise_()
            dialog.activateWindow()

        dialog.finished.connect(finish_prompt)
        activate_current_application()
        dialog.open()
        QTimer.singleShot(60, raise_prompt_dialog)

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
