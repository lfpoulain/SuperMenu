"""Text and voice prompt orchestration for the macOS menu-bar application."""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication


from supermenu_core.config.feature_modes import (
    advanced_enabled,
    experimental_enabled,
)
from supermenu_core.config.model_target import settings_for_prompt
from supermenu_core.ui.controls import Menu as QMenu, populate_prompt_menu
from supermenu_core.ui.voice_menu import populate_voice_menu
from supermenu_core.config.voice_prompts import compose_voice_prompt
from src.api.openai_client import OpenAIClient
from src.ui.prompt_dialog import PromptDialog
from src.ui.response_window import ResponseWindow
from supermenu_core.ui.loading_indicator import SimpleLoadingIndicator
from src.utils.logger import log, logger
from supermenu_core.ui.request_coordinator import PromptRequestCoordinator, RequestFeedback
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


def _application_level(target):
    """The target without its window-level check, when it has one.

    « Insérer le texte » is an explicit click: the user may well have opened
    the reply or document the answer is meant for in the meantime. Only the
    insertions nobody confirms keep the window-level check.
    """
    application_only = getattr(target, "application_only", None)
    if not callable(application_only):
        return target
    try:
        return application_only()
    except Exception:
        return target


class ContextMenuManager(PromptRequestCoordinator):
    """Coordinate selection, prompt choice, API calls and response insertion."""

    REQUEST_FEEDBACK = RequestFeedback(
        direct_pending="Réponse en attente…",
        response_error="Erreur : {error}",
        send_error="{error}",
    )

    def __init__(self, settings, selection_reader=None):
        super().__init__(settings, ResponseWindow)
        self.selection_reader = selection_reader or SelectionReader()
        self._menu_open = False
        self._selection_pending = False
        self._active_inserters = []
        self._active_menu = None
        self._prompt_dialog = None
        self._dictation = None

    def _create_api_client(self, settings=None):
        settings = settings or self.settings
        if settings.get_ai_provider() not in {"openai", "custom", "apple"}:
            raise ValueError("Le moteur choisi pour ce prompt est indisponible sur cet ordinateur.")
        if settings.get_ai_provider() == "apple":
            from src.api.apple_foundation_client import AppleFoundationClient

            return AppleFoundationClient()
        return OpenAIClient(
            settings=settings,
            api_key=settings.get_api_key(),
        )

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
        # Voice prompts and dictation belong to the experimental features.
        if experimental_enabled(self.settings):
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
            # A prompt that pastes its answer directly opens no window. Hand
            # the foreground back to the target right away, as for a cancel,
            # instead of leaving SuperMenu active and windowless for the
            # whole model call; the insertion re-checks the target anyway.
            action_dispatched = bool(data) and not self._prompt_inserts_directly(
                data
            )
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
        # Read at use time: the status menu, the voice menu, the « Dicter »
        # button and instant dictation all end here.
        if self._closed or not experimental_enabled(self.settings):
            return
        from supermenu_core.audio.dictation_flow import PlainDictationSession
        from supermenu_core.audio.settings import speech_options
        from src.audio.speech_backend import create_speech_backend
        target = target or PasteTarget.capture(fall_back_to_last_known=from_ui)
        if self._dictation is not None:
            self._dictation.cleanup()
            self._dictation.deleteLater()

        def insert(text, finished, active):
            inserter = TextInserter()
            self._active_inserters.append(inserter)

            def done(success, reason):
                if inserter in self._active_inserters:
                    self._active_inserters.remove(inserter)
                finished(success, reason)

            inserter.insert_text_async(text, target, done, is_cancelled=lambda: not active())

        try:
            self._dictation = PlainDictationSession(
                lambda options: create_speech_backend(self.settings, options),
                speech_options(self.settings), insert_text=insert,
                correction_factory=lambda: self._create_api_client(settings_for_prompt(self.settings, "corriger")),
                # Read at insertion time, like the model of the « Corriger » prompt.
                correction_reasoning_mode=lambda: (self.settings.get_prompt("corriger") or {}).get("reasoning_mode", "default"),
                auto_insert=self.settings.get_dictation_auto_insert(),
                correct_before_insert=self.settings.get_dictation_correct_before_insert(),
                parent=self,
            )
            activate_current_application()
            self._dictation.start_voice_recognition()
        except ValueError as exc:
            SafeDialogs.show_information("Réglages de dictée", str(exc))

    def start_instant_dictation(self):
        # Checked before touching _instant_session: finishing must never stop
        # a session this call did not start.
        if not experimental_enabled(self.settings):
            return
        self._instant_session = None
        session = self._dictation
        if session and (session.is_recording or session.is_processing or getattr(session, "_delivery_busy", False)):
            return
        self.start_dictation()
        self._instant_session = self._dictation

    def finish_instant_dictation(self):
        session = getattr(self, "_instant_session", None)
        self._instant_session = None
        if session is not None and session is self._dictation:
            session.stop_listening()

    def _start_voice_session(self, callback):
        from src.audio.speech_backend import create_speech_backend
        from supermenu_core.audio.session import DictationSession
        from supermenu_core.audio.settings import speech_options

        # Also covers a selection captured before the experimental features
        # were turned off.
        if self._closed or not experimental_enabled(self.settings):
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
        if (
            self._closed
            or self._selection_pending
            or not experimental_enabled(self.settings)
        ):
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
            request_id = self._send_request(
                request, "", insert_directly=direct, target=target,
                include_reasoning=False if direct else None,
                direct_status=f"Envoyé — {status}",
                reasoning_mode=prompt.get("reasoning_mode", "default"),
                model_target=prompt.get("model_target"),
            )
            restore = getattr(target, "request_activation", None)
            if direct and callable(restore) and request_id in self._pending_requests:
                # The recording window closes right after this callback and no
                # other window opens: give the foreground back to the target
                # for the model call, as the menu does for a direct prompt.
                # The insertion re-checks the target before pasting anyway.
                QTimer.singleShot(0, restore)

        self._start_voice_session(process_transcription)

    def show_custom_mode(self) -> None:
        if self._closed or self._selection_pending:
            return
        self._capture_selection(self._handle_custom)

    def run_prompt_hotkey(self, prompt_id: str) -> None:
        # A shortcut queued before the advanced features were turned off.
        if (
            self._closed
            or self._selection_pending
            or not advanced_enabled(self.settings)
        ):
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

    def _prompt_inserts_directly(self, action_data) -> bool:
        """Whether a menu entry is a text prompt that opens no window."""
        try:
            action_kind, prompt_id = action_data
            if action_kind != "prompt":
                return False
            prompt = self.settings.get_prompt(prompt_id)
            return bool(prompt and prompt.get("insert_directly", False))
        except Exception:
            return False

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
            reasoning_mode=prompt.get("reasoning_mode", "default"),
            model_target=prompt.get("model_target"),
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

    def _response_window_target(self, target):
        return _application_level(target)

    def _insert_directly(self, response, target, indicator, client, request=None) -> None:
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
                # The indicator now stays alive until closed: do not leave it
                # on screen while the application quits.
                if indicator is not None:
                    indicator.close()
                return
            if indicator is not None:
                indicator.set_message(
                    "Réponse insérée" if success else "Insertion annulée"
                )
                indicator.move_near_cursor()
                QTimer.singleShot(1600, indicator.close)
            if not success:
                log(f"Insertion directe abandonnée : {reason}", logging.WARNING)
                kept_in = self._keep_refused_direct_response(
                    request or {}, response, target
                )
                outcome = {
                    "window": " Elle est affichée dans la fenêtre de réponse.",
                    "clipboard": " Elle a été copiée dans le presse-papiers.",
                }.get(kept_in, "")
                SafeDialogs.show_information(
                    "Insertion annulée",
                    (
                        "Une autre fenêtre de l'application cible est devenue "
                        "active : la réponse n'a pas été collée."
                        if reason == "window_changed"
                        else "L'application cible a changé ou n'est plus disponible."
                    )
                    + outcome,
                )
            self._release_retired_client_if_idle(client)

        inserter.insert_text_async(response, target, finished)

    def _keep_refused_direct_response(self, request, response, target):
        """Never discard an answer whose direct insertion was refused.

        Returns "window" when the answer is shown in the response window,
        "clipboard" when it was copied because the window still awaits another
        answer, or None when it could not be kept.
        """
        if self._closed or not response:
            return None
        active_id = self._active_response_request_id
        if active_id is not None and active_id in self._pending_requests:
            # Never replace an answer the response window is still waiting for.
            return "clipboard" if self._copy_answer(response) else None
        try:
            self.response_window.last_reasoning_mode = request.get(
                "reasoning_mode", "default"
            )
            self.response_window.last_model_target = dict(
                request.get("model_target") or {}
            )
            # Keeps « Réessayer », including the transcript of a voice prompt.
            self._prepare_response_window(
                "Insertion annulée — réponse conservée",
                request.get("prompt"),
                request.get("content") or "",
                target,
            )
            self.response_window.set_response(response)
            self.response_window.set_loading(False)
            return "window"
        except Exception:
            logger.exception("Affichage de la réponse non insérée impossible")
            return "clipboard" if self._copy_answer(response) else None

    @staticmethod
    def _copy_answer(text) -> bool:
        """Copy a kept answer the way the « Copier » button does."""
        try:
            QApplication.clipboard().setText(text)
            return True
        except Exception:
            logger.exception("Copie de la réponse non insérée impossible")
            return False

    def _report_direct_failure(self, request, error) -> None:
        indicator = request.get("indicator")
        if indicator is not None:
            indicator.set_message("Échec du traitement")
            QTimer.singleShot(1800, indicator.close)
        target = request.get("target")
        if target is not None and not self._user_moved_elsewhere(target):
            # The box activates SuperMenu: give the foreground back to the
            # user's application once the error has been read.
            SafeDialogs.show_critical(
                "Erreur de traitement",
                str(error),
                on_closed=target.request_activation,
            )
        else:
            SafeDialogs.show_critical("Erreur de traitement", str(error))

    @staticmethod
    def _user_moved_elsewhere(target) -> bool:
        """True only when a third application is known to be in front.

        Neither the target nor SuperMenu: the user went on working elsewhere
        during the model call, and closing the box must leave them there.
        """
        is_current = getattr(target, "is_current", None)
        if not callable(is_current):
            return False
        try:
            return not is_current() and not current_application_is_active()
        except Exception:
            return False

    def _release_platform_resources(self) -> None:
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
