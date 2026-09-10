"""Text and voice prompt orchestration for the macOS menu-bar application."""

from __future__ import annotations

import logging
import uuid

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QCursor


from supermenu_core.ui.controls import Menu as QMenu, populate_prompt_menu
from supermenu_core.ui.voice_menu import populate_voice_menu
from supermenu_core.config.voice_prompts import compose_voice_prompt
from src.api.openai_client import OpenAIClient
from src.ui.prompt_dialog import PromptDialog
from src.ui.response_window import ResponseWindow
from supermenu_core.ui.loading_indicator import SimpleLoadingIndicator
from src.utils.logger import log, logger
from supermenu_core.ui.safe_dialogs import SafeDialogs
from src.utils.selection import SelectionReader
from src.utils.text_inserter import TextInserter
from src.utils.window_target import (
    PasteTarget,
    activate_current_application,
    current_application_is_active,
)


MENU_ACTIVATION_POLL_MS = 25
MENU_ACTIVATION_MAX_POLLS = 6
MENU_FORCED_ACTIVATION_DELAY_MS = 50
MENU_VISIBILITY_CHECK_DELAY_MS = 350


class ContextMenuManager(QObject):
    """Coordinate selection, prompt choice, API calls and response insertion."""

    def __init__(self, settings, selection_reader=None):
        super().__init__()
        self.settings = settings
        self.selection_reader = selection_reader or SelectionReader()
        self.api_client = self._create_api_client()
        self.response_window = ResponseWindow()
        self.response_window.retry_requested.connect(self.on_retry_requested)
        self._pending_requests = {}
        self._active_response_request_id = None
        self._retired_clients = []
        self._menu_open = False
        self._selection_pending = False
        self._active_inserters = []
        self._active_menu = None
        self._prompt_dialog = None
        self._closed = False
        self._dictation = None
        self._connect_api_client(self.api_client)

    def _create_api_client(self):
        if self.settings.get_ai_provider() == "apple":
            from src.api.apple_foundation_client import AppleFoundationClient

            return AppleFoundationClient()
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

    def _capture_selection(self, on_ready, *, from_ui: bool = False) -> None:
        """Capture the frontmost app, then read its selection asynchronously."""
        target = PasteTarget.capture(fall_back_to_last_known=from_ui)
        log(
            "Application cible capturée"
            if target is not None
            else "Aucune application cible capturée",
            logging.INFO if target is not None else logging.WARNING,
        )

        def deliver(selected_text):
            self._selection_pending = False
            if self._closed:
                return
            try:
                on_ready(selected_text, target)
            except Exception:
                logger.exception("Traitement de la sélection impossible")

        self._selection_pending = True
        try:
            self.selection_reader.read_async(target, deliver)
        except Exception:
            self._selection_pending = False
            logger.exception("Lecture de la sélection impossible")

    def show_menu(self, *, from_ui: bool = False) -> None:
        """Present the prompt menu.

        ``from_ui`` marks the paths triggered from SuperMenu's own interface,
        where the frontmost application is already SuperMenu. Those fall back
        to the application the user came from, so the diagnostic entry points
        can exercise a real prompt instead of only ever showing a greyed menu.
        """
        if self._closed:
            log("Ouverture du menu ignorée : service fermé", logging.WARNING)
            return
        if self._menu_open or self._selection_pending:
            log("Ouverture du menu ignorée : un menu est déjà ouvert")
            return
        log("Préparation du menu contextuel")
        self._capture_selection(self._present_menu, from_ui=from_ui)

    def _present_menu(self, selected_text, target) -> None:
        if self._menu_open:
            log("Ouverture du menu ignorée : un menu est déjà ouvert")
            return
        menu = QMenu()
        self._menu_open = True
        self._active_menu = menu
        action_dispatched = False
        populate_prompt_menu(
            menu, self.settings.get_prompts(),
            lambda prompt_id: ("prompt", prompt_id), enabled=bool(selected_text),
        )
        menu.addSeparator()
        custom_action = menu.addAction("Mode personnalisé…")
        custom_action.setData(("custom", None))
        voice_menu = menu.addMenu("Voix")
        populate_voice_menu(voice_menu, self.settings.get_voice_prompts(), lambda kind, key: (kind, key))

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
            # Fire and forget: verifying would mean sleeping on the run loop
            # that has to deliver the workspace notification in the first place.
            restored = target.request_activation()
            log(
                "Réactivation de l’application cible demandée après fermeture "
                "du menu"
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
            elif action_kind == "voice":
                self.start_dictation(target=target)
            elif action_kind == "voice_prompt":
                prompt = self.settings.get_voice_prompt(prompt_id)
                if prompt:
                    self._start_voice_prompt(prompt, selected_text, target)
            elif action_kind == "voice_godmode":
                self._handle_custom("", target, voice=True)
            else:
                self._handle_custom(selected_text, target)

        def popup_menu():
            if self._closed or self._active_menu is not menu:
                return
            try:
                # popup() installs the mouse and keyboard grab that makes a
                # click outside dismiss the menu. Making the popup window key
                # afterwards -- activateWindow(), requestActivate() -- cancels
                # that grab, leaving a menu that can only be closed by picking
                # an entry. The application itself is already frontmost here,
                # which is what the menu actually needed.
                menu.popup(QCursor.pos())
                menu.raise_()
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

    def start_dictation(self, *, from_ui=False, target=None):
        if self._closed:
            return
        target = target or PasteTarget.capture(fall_back_to_last_known=from_ui)

        def show_result(text):
            if self._closed:
                return
            self.response_window.set_paste_target(target)
            self.response_window.set_trigger_position(QCursor.pos())
            self.response_window.set_standalone_response(text, "SuperMenu — Dictée")
            self.response_window.present()

        self._start_voice_session(show_result)

    def _start_voice_session(self, callback):
        from src.audio.speech_backend import create_speech_backend
        from supermenu_core.audio.session import DictationSession
        from supermenu_core.audio.settings import speech_options

        if self._closed:
            return
        if self._dictation is not None:
            self._dictation.cleanup()
            self._dictation.deleteLater()
            self._dictation = None
        try:
            self._dictation = DictationSession(
                lambda options: create_speech_backend(self.settings, options),
                speech_options(self.settings), callback, self,
            )
            activate_current_application()
            self._dictation.start_voice_recognition()
        except ValueError as exc:
            SafeDialogs.show_information("Réglages de dictée", str(exc))

    def run_voice_prompt(self, prompt_id, *, from_ui=False):
        if self._closed or self._selection_pending:
            return
        prompt = self.settings.get_voice_prompt(prompt_id)
        if not prompt:
            return
        if prompt.get("include_selected_text", False):
            self._capture_selection(
                lambda selection, target: self._start_voice_prompt(prompt, selection, target),
                from_ui=from_ui,
            )
        else:
            target = PasteTarget.capture(fall_back_to_last_known=from_ui)
            self._start_voice_prompt(prompt, "", target)

    def _start_voice_prompt(self, prompt, selected_text, target):
        prompt = dict(prompt)

        def process_transcription(text):
            if self._closed or not text.strip():
                return
            request = compose_voice_prompt(prompt, text, selected_text)
            direct = bool(prompt.get("insert_directly", True))
            status = prompt.get("status") or "Traitement en cours…"
            if not direct:
                self._prepare_response_window(status, request, "", target)
            self._send_request(
                request, "", insert_directly=direct, target=target,
                include_reasoning=False if direct else None,
                direct_status=f"Envoyé — {status}",
            )

        self._start_voice_session(process_transcription)

    def show_custom_mode(self) -> None:
        if self._closed or self._selection_pending:
            return
        self._capture_selection(self._handle_custom)

    def run_prompt_hotkey(self, prompt_id: str) -> None:
        if self._closed or self._selection_pending:
            return

        def run(selected_text, target):
            if not selected_text:
                SimpleLoadingIndicator.show_near_cursor(
                    "Aucun texte sélectionné",
                    duration_ms=1800,
                )
                return
            self._handle_prompt(prompt_id, selected_text, target)

        self._capture_selection(run)

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

    def _handle_custom(self, selected_text: str, target, *, voice=False) -> None:
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
            if voice:
                self._start_voice_prompt({
                    "prompt": prompt, "status": "Traitement du prompt vocal…",
                    "insert_directly": False,
                }, "", target)
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
            self._insert_directly(
                response,
                request.get("target") or target,
                request.get("indicator"),
                client,
            )
            return
        if request_id == self._active_response_request_id:
            self.response_window.set_response(response)
            self.response_window.set_loading(False)
        self._release_retired_client_if_idle(client)

    def _insert_directly(self, response, target, indicator, client) -> None:
        """Paste the answer without blocking the run loop that drives focus.

        The synchronous helper slept through activation and the clipboard
        round trip on the Qt thread, which froze the UI for about half a
        second and suppressed the AppKit updates it was polling for.
        """
        inserter = TextInserter()
        self._active_inserters.append(inserter)

        def finished(success, reason):
            try:
                self._active_inserters.remove(inserter)
            except ValueError:
                pass
            if self._closed:
                return
            if indicator is not None:
                indicator.set_message(
                    "Réponse insérée" if success else "Insertion annulée"
                )
                indicator.move_near_cursor()
                QTimer.singleShot(1600, indicator.close)
            if not success:
                log(f"Insertion directe abandonnée : {reason}", logging.WARNING)
                SafeDialogs.show_information(
                    "Insertion annulée",
                    "L'application cible a changé ou n'est plus disponible.",
                )
            self._release_retired_client_if_idle(client)

        inserter.insert_text_async(response, target, finished)

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
        if self._dictation is not None:
            self._dictation.cleanup()
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
