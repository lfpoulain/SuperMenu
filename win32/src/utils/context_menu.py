#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtCore import QObject, Qt, QEvent, QTimer, QPoint
import os
import tempfile
import base64
import time
import logging
import uuid
import win32gui
import win32process
import win32api
import win32con
from pynput.keyboard import Controller, Key

from supermenu_core.api.openai_client import clear_capabilities_cache
from supermenu_core.config.feature_modes import (
    advanced_enabled,
    effective_model_target,
    experimental_enabled,
)
from supermenu_core.config.model_target import ModelTargetSettings, settings_for_prompt
from supermenu_core.ui.controls import Menu as QMenu, populate_prompt_menu, menu_contains_global_point
from src.api.openai_client import OpenAIClient
from supermenu_core.ui.safe_dialogs import SafeDialogs
from src.ui.response_window import ResponseWindow
from src.ui.prompt_dialog import PromptDialog
from src.ui.screen_capture import capture_screen
from supermenu_core.audio.session import DictationSession
from supermenu_core.audio.settings import speech_options
from supermenu_core.config.voice_prompts import compose_voice_prompt
from supermenu_core.ui.voice_menu import populate_voice_menu
from src.audio.speech_backend import create_speech_backend
from src.utils.text_inserter import TextInserter, VK_C
from src.utils.logger import log
from src.utils.clipboard_manager import ClipboardManager
from supermenu_core.ui.loading_indicator import SimpleLoadingIndicator
from src.utils.window_target import PasteTarget
from src.utils.clipboard_config import CLIPBOARD_COPY_DELAY, CLIPBOARD_RESTORE_DELAY

# Shift, Ctrl, Alt and both Windows keys. Global hotkeys fire on key down: a
# copy synthesized while one of them is still held reaches the foreground
# application as another shortcut (Ctrl+Alt+C, Ctrl+Shift+C).
HOTKEY_MODIFIER_KEYS = (0x10, 0x11, 0x12, 0x5B, 0x5C)
# Only Shift, Alt and the Windows keys change the synthesized Ctrl+C or
# Ctrl+Insert. A held Ctrl does not, so the menu and the custom mode (default
# Ctrl+²) still open on the key press instead of waiting for Ctrl.
COPY_ALTERING_MODIFIER_KEYS = (0x10, 0x12, 0x5B, 0x5C)
MODIFIER_RELEASE_TIMEOUT = 2.0
MODIFIER_RELEASE_POLL_MS = 20

# Console hosts copy with Ctrl+Insert; Ctrl+C would interrupt the running
# program when nothing is selected.
CONSOLE_WINDOW_CLASSES = frozenset({"ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"})
# Standalone terminals where Ctrl+C reaches the program as an interrupt and
# whose documented copy shortcut is Ctrl+Insert: mintty/Git Bash, PuTTY 0.71+
# (and its fork KiTTY) and WezTerm. Only Ctrl+Insert is sent to them. ConEmu
# and Cmder are left out: they copy a selection on Ctrl+C and do not bind
# Ctrl+Insert to copy.
TERMINAL_WINDOW_CLASSES = frozenset(
    {"mintty", "PuTTY", "KiTTY", "org.wezfurlong.wezterm"}
)


def _copy_shortcuts_for(window_class):
    """Copy shortcuts to try in order for the foreground window class."""
    if window_class in CONSOLE_WINDOW_CLASSES:
        return ((Key.ctrl, Key.insert), (Key.ctrl, Key.shift, VK_C))
    if window_class in TERMINAL_WINDOW_CLASSES:
        return ((Key.ctrl, Key.insert),)
    return ((Key.ctrl, VK_C),)


class ContextMenuManager(QObject):
    """Manage the context menu for text operations"""

    MENU_STALE_SECONDS = 20
    
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        # Initialiser le client API avec les paramètres
        # Ne pas passer le modèle ici, OpenAIClient le déterminera selon le type d'endpoint
        self.api_client = self._create_api_client()
        self.response_window = ResponseWindow()
        self.voice_recognition = None
        self._pending_requests = {}
        self._active_response_request_id = None
        self._retired_clients = []
        self._closed = False
        
        # Créer un contrôleur de clavier réutilisable pour éviter les conflits
        self.keyboard = Controller()

        self._is_menu_open = False
        self._active_menu = None
        self._menu_owner_pid = None
        self._last_lbutton_down = False
        self._menu_opened_at = None
        self._menu_watchdog = QTimer(self)
        self._menu_watchdog.setInterval(200)
        self._menu_watchdog.timeout.connect(self._menu_watchdog_tick)

        try:
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)

            gui_app = QGuiApplication.instance()
            if gui_app is not None:
                gui_app.applicationStateChanged.connect(self._on_application_state_changed)
        except Exception:
            pass
        
        self._connect_api_client(self.api_client)
        
        # Connecter le signal de retry
        self.response_window.retry_requested.connect(self.on_retry_requested)

    def _create_api_client(self, settings=None):
        settings = settings or self.settings
        if settings.get_ai_provider() not in {"openai", "custom", "foundry"}:
            raise ValueError("Le moteur choisi pour ce prompt est indisponible sur cet ordinateur.")
        if settings.get_ai_provider() == "foundry":
            from src.api.foundry_client import FoundryClient
            return FoundryClient(settings)
        return OpenAIClient(settings=settings, api_key=settings.get_api_key())

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
        # Without the advanced features every prompt uses the Text settings;
        # the prompt keeps its stored model for when they are turned back on.
        model_target = effective_model_target(self.settings, model_target)

        request_id = uuid.uuid4().hex
        client = self.api_client
        direct_indicator = None
        if insert_directly:
            direct_indicator = SimpleLoadingIndicator.show_near_cursor(
                direct_status or "✅ Envoyé à l'IA — réponse en attente…"
            )

        self._pending_requests[request_id] = {
            "client": client,
            "insert_directly": bool(insert_directly),
            "target": target,
            "indicator": direct_indicator,
        }
        if insert_directly:
            # Kept so that a refused insertion can still show and retry it.
            self._pending_requests[request_id].update(
                prompt=prompt,
                content=content,
                reasoning_mode=reasoning_mode,
                model_target=model_target,
            )
        if not insert_directly:
            self._active_response_request_id = request_id
            self.response_window.last_reasoning_mode = reasoning_mode
            self.response_window.last_model_target = dict(model_target or {})
        try:
            if model_target:
                client = self._create_api_client(ModelTargetSettings(self.settings, model_target))
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
        except Exception as e:
            self.on_request_error_scoped(request_id, f"Erreur: {e}")
        return request_id

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

    def _present_response_window(self, force=False):
        """Afficher la fenêtre avec la stratégie hybride Qt/Win32 unique."""
        if self._closed:
            return
        self.response_window.present()

    def show_response_window(self):
        """Ouvrir manuellement la fenêtre de correction depuis l'interface."""
        if self._closed:
            return
        self.response_window.set_trigger_position(None)
        self._present_response_window(force=True)

    def _get_foreground_pid(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return pid
        except Exception:
            return None

    def _guess_menu_owner_pid(self):
        try:
            x, y = win32gui.GetCursorPos()
            hwnd = win32gui.WindowFromPoint((int(x), int(y)))
            if not hwnd:
                return self._get_foreground_pid()
            _, under_cursor_pid = win32process.GetWindowThreadProcessId(hwnd)
            our_pid = os.getpid()
            if under_cursor_pid and under_cursor_pid != our_pid:
                return under_cursor_pid
        except Exception:
            pass

        return self._get_foreground_pid()

    def _menu_watchdog_tick(self):
        try:
            menu = self._active_menu
            if menu is None or not menu.isVisible():
                self._finish_menu_session(menu)
                return

            try:
                opened_at = self._menu_opened_at
                if opened_at is not None and (time.monotonic() - opened_at) < 0.25:
                    try:
                        self._last_lbutton_down = (win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000) != 0
                    except Exception:
                        self._last_lbutton_down = False
                    return
            except Exception:
                pass

            pid = self._get_foreground_pid()
            if pid is None:
                return

            if self._menu_owner_pid is None:
                if pid != os.getpid():
                    self._menu_owner_pid = pid
                return

            current_pid = pid
            our_pid = os.getpid()
            owner_pid = self._menu_owner_pid

            if current_pid not in (owner_pid, our_pid):
                menu.close()
                return

            try:
                lbutton_down = (win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000) != 0
            except Exception:
                lbutton_down = False

            if lbutton_down and not self._last_lbutton_down:
                try:
                    x, y = win32gui.GetCursorPos()
                    pos = QPoint(int(x), int(y))
                except Exception:
                    pos = None

                if pos is not None and not menu_contains_global_point(menu, pos):
                    menu.close()

            self._last_lbutton_down = lbutton_down
        except RuntimeError:
            self._finish_menu_session()
        except Exception as e:
            log(f"Erreur watchdog menu: {e}", logging.DEBUG)

    def _on_application_state_changed(self, state):
        return

    def eventFilter(self, obj, event):
        try:
            menu = self._active_menu
            if menu is not None and menu.isVisible():
                et = event.type()
                if et == QEvent.MouseButtonPress:
                    try:
                        pos = event.globalPosition().toPoint()
                    except Exception:
                        try:
                            pos = event.globalPos()
                        except Exception:
                            pos = None

                    if pos is not None and not menu_contains_global_point(menu, pos):
                        menu.close()
        except Exception:
            pass

        return super().eventFilter(obj, event)

    def _recover_stale_menu_state(self):
        """Clear a stale menu lock left by a failed or externally deleted menu."""
        if not self._is_menu_open:
            return

        menu = self._active_menu
        try:
            if menu is None or not menu.isVisible():
                log("Reinitialisation d'un verrou de menu inactif", logging.WARNING)
                self._finish_menu_session(menu)
                return
        except RuntimeError:
            log("Reinitialisation d'un menu Qt deja detruit", logging.WARNING)
            self._finish_menu_session()
            return

        opened_at = self._menu_opened_at
        if opened_at is not None and (time.monotonic() - opened_at) > self.MENU_STALE_SECONDS:
            log("Fermeture d'un menu reste ouvert trop longtemps", logging.WARNING)
            self._finish_menu_session(menu, close_visible=True)

    def _begin_menu_session(self, owner_pid=None):
        if self._closed:
            return None
        self._recover_stale_menu_state()
        if self._is_menu_open:
            log("Demande de menu ignoree: un menu est deja ouvert", logging.DEBUG)
            return None

        self._is_menu_open = True
        try:
            menu = QMenu()
            self._active_menu = menu
            self._menu_owner_pid = owner_pid
            self._menu_opened_at = time.monotonic()
            try:
                self._last_lbutton_down = (win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000) != 0
            except Exception:
                self._last_lbutton_down = False

            menu.setAttribute(Qt.WA_DeleteOnClose)
            return menu
        except Exception:
            self._finish_menu_session()
            raise

    def _exec_menu(self, menu):
        if not self._menu_watchdog.isActive():
            self._menu_watchdog.start()
        try:
            return menu.exec(QCursor.pos())
        finally:
            self._finish_menu_session(menu)

    def _finish_menu_session(self, menu=None, close_visible=False):
        try:
            if self._menu_watchdog.isActive():
                self._menu_watchdog.stop()
        except Exception:
            pass

        if close_visible and menu is not None:
            try:
                if menu.isVisible():
                    menu.close()
            except RuntimeError:
                pass
            except Exception as e:
                log(f"Erreur fermeture menu: {e}", logging.DEBUG)

        self._is_menu_open = False
        self._active_menu = None
        self._menu_owner_pid = None
        self._last_lbutton_down = False
        self._menu_opened_at = None
    
    def _create_voice_recognition(self, *, callback=None):
        """Créer une dictée avec le contrôleur commun aux deux plateformes."""
        return DictationSession(
            lambda options: create_speech_backend(self.settings, options),
            speech_options(self.settings),
            callback,
        )
    
    def _modifiers_held(self, keys=HOTKEY_MODIFIER_KEYS):
        try:
            return any(
                win32api.GetAsyncKeyState(key) & 0x8000
                for key in keys
            )
        except Exception:
            return False

    def _when_hotkey_released(self, target, on_ready, keys=HOTKEY_MODIFIER_KEYS):
        """Call ``on_ready()`` once the hotkey modifiers in ``keys`` are up.

        Copying while Alt/Shift is still held sends a different shortcut to
        the foreground application, so the copy waits for the user's fingers
        without blocking the Qt loop. A newer hotkey supersedes a pending one.
        Without any held modifier, ``on_ready()`` runs immediately.
        """
        serial = getattr(self, "_hotkey_capture_serial", 0) + 1
        self._hotkey_capture_serial = serial
        deadline = time.monotonic() + MODIFIER_RELEASE_TIMEOUT

        def attempt(waited=False):
            if self._closed or self._hotkey_capture_serial != serial:
                return
            if self._modifiers_held(keys):
                if time.monotonic() < deadline:
                    QTimer.singleShot(MODIFIER_RELEASE_POLL_MS, lambda: attempt(True))
                else:
                    SimpleLoadingIndicator.show_near_cursor("Relâchez les touches puis réessayez", duration_ms=1800)
                return
            if waited and PasteTarget.capture() != target:
                # Never read from an application focused during the wait.
                log("Raccourci ignoré: la fenêtre active a changé", logging.DEBUG)
                SimpleLoadingIndicator.show_near_cursor(
                    "Raccourci ignoré : la fenêtre active a changé", duration_ms=1800
                )
                return
            try:
                on_ready()
            except Exception as e:
                log(f"Erreur après le raccourci: {e}", logging.ERROR)

        attempt()

    def show_menu(self):
        """Show the context menu at the current cursor position"""
        if self._closed:
            return
        self._recover_stale_menu_state()
        if self._is_menu_open:
            log("Demande de menu ignoree: un menu est deja ouvert", logging.DEBUG)
            return
        paste_target = PasteTarget.capture()
        self._when_hotkey_released(
            paste_target,
            lambda: self._open_prompt_menu(paste_target),
            keys=COPY_ALTERING_MODIFIER_KEYS,
        )

    def _open_prompt_menu(self, paste_target):
        if self._closed:
            return
        owner_pid = paste_target.process_id if paste_target else self._get_foreground_pid()
        menu = self._begin_menu_session(owner_pid=owner_pid)
        if menu is None:
            return

        chosen_action = None
        try:
            # Tenter de récupérer le texte sélectionné sans bloquer
            selected_text = self._try_get_selected_text()

            populate_prompt_menu(
                menu, self.settings.get_prompts(),
                lambda prompt_id: ("prompt", prompt_id, selected_text, paste_target),
                enabled=bool(selected_text),
            )

            # Ajouter un séparateur
            menu.addSeparator()

            # Ajouter l'option GodMode (toujours disponible)
            godmode_action = menu.addAction("Mode personnalisé…")
            godmode_action.setData(
                ("godmode", selected_text if selected_text else "", paste_target)
            )

            # Afficher le menu à la position du curseur
            # Utiliser exec_ pour les hotkeys car il est bloquant et assure que le menu reste visible
            # jusqu'à ce qu'une action soit sélectionnée ou que l'utilisateur clique ailleurs
            chosen_action = self._exec_menu(menu)
        except Exception as e:
            self._finish_menu_session(menu, close_visible=True)
            log(f"Erreur lors de la preparation du menu contextuel: {e}", logging.ERROR)
            return

        if chosen_action is None:
            return

        action_data = chosen_action.data()
        if not action_data:
            return

        action_kind = action_data[0]
        if action_kind == "prompt":
            _, prompt_id, action_text, target = action_data
            self._handle_menu_action(prompt_id, action_text, target=target)
        elif action_kind == "godmode":
            _, action_text, target = action_data
            self._handle_godmode_action(action_text, target=target)

    def show_custom_mode(self):
        """Ouvrir directement le mode personnalisé depuis un raccourci."""
        if self._closed:
            return
        self._recover_stale_menu_state()
        if self._is_menu_open:
            log("Mode personnalise ignore: un menu est deja ouvert", logging.DEBUG)
            return

        paste_target = PasteTarget.capture()
        self._when_hotkey_released(
            paste_target,
            lambda: self._open_custom_mode(paste_target),
            keys=COPY_ALTERING_MODIFIER_KEYS,
        )

    def _open_custom_mode(self, paste_target):
        if self._closed:
            return
        self._recover_stale_menu_state()
        if self._is_menu_open:
            log("Mode personnalise ignore: un menu est deja ouvert", logging.DEBUG)
            return
        selected_text = self._try_get_selected_text()
        self._handle_godmode_action(selected_text, target=paste_target)

    def _choose_screenshot_mode_menu(self):
        menu = self._begin_menu_session(owner_pid=self._get_foreground_pid())
        if menu is None:
            return None

        try:
            fullscreen_action = menu.addAction("Plein écran")
            region_action = menu.addAction("Sélection de zone")
            menu.addSeparator()
            cancel_action = menu.addAction("Annuler")

            chosen_action = self._exec_menu(menu)
            if chosen_action is None or chosen_action == cancel_action:
                return None
            if chosen_action == fullscreen_action:
                return "fullscreen"
            if chosen_action == region_action:
                return "region"
            return None
        except Exception as e:
            self._finish_menu_session(menu, close_visible=True)
            log(f"Erreur lors du choix du mode de capture: {e}", logging.ERROR)
            return None
    
    def show_voice_menu(self):
        """Show only the voice interaction menu at the current cursor position"""
        if self._closed or not experimental_enabled(self.settings):
            return
        paste_target = PasteTarget.capture()
        owner_pid = (
            paste_target.process_id if paste_target else self._guess_menu_owner_pid()
        )
        menu = self._begin_menu_session(owner_pid=owner_pid)
        if menu is None:
            return

        chosen_action = None
        try:
            populate_voice_menu(
                menu, self.settings.get_voice_prompts(),
                lambda kind, prompt_id: (kind, prompt_id, paste_target)
                if kind == "voice_prompt" else (kind, paste_target),
            )

            # Afficher le menu à la position du curseur
            chosen_action = self._exec_menu(menu)
        except Exception as e:
            self._finish_menu_session(menu, close_visible=True)
            log(f"Erreur lors de la preparation du menu vocal: {e}", logging.ERROR)
            return

        if chosen_action is None:
            return

        action_data = chosen_action.data()
        if not action_data:
            return

        action_kind = action_data[0]
        if action_kind == "voice":
            _, target = action_data
            self._handle_voice_action(target=target)
        elif action_kind == "voice_prompt":
            _, prompt_id, target = action_data
            self._handle_voice_prompt_action(prompt_id, target=target)
        elif action_kind == "voice_godmode":
            _, target = action_data
            self._handle_voice_godmode_action(target=target)

    def _press_keyboard_shortcut(self, *keys):
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
    
    def _try_get_selected_text(self):
        """
        Tente de récupérer le texte sélectionné sans bloquer l'interface utilisateur.
        Utilise plusieurs méthodes pour maximiser les chances de succès.
        
        Returns:
            str: Le texte sélectionné ou une chaîne vide si aucun texte n'est sélectionné
        """
        selected_text = ""
        old_clipboard = None
        clipboard_needs_restore = False
        sentinel = f"__SUPERMENU_EMPTY_SELECTION_{time.monotonic_ns()}__"

        # Aucune sélection externe ne peut être lue quand SuperMenu est au
        # premier plan : ne pas toucher au presse-papiers dans ce cas.
        if self._get_foreground_pid() == os.getpid():
            return ""

        try:
            # Sauvegarder le contenu actuel du presse-papiers avec ClipboardManager
            old_clipboard = ClipboardManager.capture_snapshot()

            # Placer un marqueur permet de distinguer "rien n'a ete copie" d'un ancien clipboard.
            if not ClipboardManager.set_clipboard_text_safe(sentinel, transient=True):
                log("Impossible de preparer le presse-papiers pour la lecture de selection", logging.WARNING)
                return ""
            clipboard_needs_restore = True
            time.sleep(0.05)  # Petit délai pour s'assurer que le clipboard est préparé

            # Méthode 1: Utiliser pynput pour copier le texte sélectionné
            copy_shortcuts = _copy_shortcuts_for("")
            try:
                try:
                    hwnd = win32gui.GetForegroundWindow()
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid == os.getpid():
                        return ""
                    copy_shortcuts = _copy_shortcuts_for(win32gui.GetClassName(hwnd))
                except Exception:
                    pass

                self._press_keyboard_shortcut(*copy_shortcuts[0])

                time.sleep(CLIPBOARD_COPY_DELAY)
            except KeyboardInterrupt:
                return ""
            except Exception as e:
                log(f"Erreur pynput: {e}", logging.DEBUG)

            # Méthode 2: Récupérer le texte avec ClipboardManager
            selected_text = ClipboardManager.get_clipboard_text_safe()

            # Console : second raccourci seulement si le presse-papiers est illisible.
            for shortcut in copy_shortcuts[1:]:
                if selected_text:
                    break
                try:
                    self._press_keyboard_shortcut(*shortcut)
                    time.sleep(CLIPBOARD_COPY_DELAY)
                    selected_text = ClipboardManager.get_clipboard_text_safe()
                except Exception:
                    pass

            # Si le clipboard est toujours vide, aucun texte n'était sélectionné
            if not selected_text or selected_text == sentinel:
                log("Aucun texte détecté après Ctrl+C", logging.DEBUG)
                return ""

            # Journaliser la taille seulement, jamais le contenu de la sélection
            log(f"Texte copié avec succès ({len(selected_text)} caractères)", logging.DEBUG)

            # Attendre avant de restaurer pour éviter les interférences
            time.sleep(CLIPBOARD_RESTORE_DELAY)

        except Exception as e:
            log(
                f"Erreur générale lors de la récupération du texte sélectionné: {e}",
                logging.DEBUG,
            )
            selected_text = ""
        except KeyboardInterrupt:
            return ""
        finally:
            if clipboard_needs_restore:
                expected_text = selected_text if selected_text else sentinel
                ClipboardManager.restore_if_unchanged(
                    old_clipboard, expected_text
                )

        # Retourner le texte récupéré ou une chaîne vide si rien n'est sélectionné
        if not selected_text:
            return ""

        return selected_text
    
    def _get_selected_text(self):
        """Get the selected text from the clipboard and show error message if none"""
        selected_text = self._try_get_selected_text()
        
        if not selected_text:
            log("Aucun texte sélectionné", logging.DEBUG)
            SafeDialogs.show_information(
                "Information",
                "Aucun texte sélectionné. Veuillez sélectionner du texte avant d'utiliser le raccourci."
            )
            return ""
            
        return selected_text
    
    def run_prompt_hotkey(self, prompt_id):
        """Run one prompt without opening the menu, honoring its display mode."""
        # A shortcut already queued when the advanced features were turned off.
        if self._closed or not advanced_enabled(self.settings):
            return
        target = PasteTarget.capture()

        def run_with_selection():
            selected_text = self._try_get_selected_text()
            if not selected_text:
                SimpleLoadingIndicator.show_near_cursor("⚠️ Aucun texte sélectionné", duration_ms=1800)
                return
            self._handle_menu_action(prompt_id, selected_text=selected_text, target=target)

        self._when_hotkey_released(target, run_with_selection)

    def _handle_menu_action(
        self,
        prompt_id,
        selected_text=None,
        target=None,
    ):
        """Handle a menu action"""
        if self._closed:
            return
        # Get the selected text
        if selected_text is None:
            selected_text = self._get_selected_text()
        if not selected_text:
            return
        
        # Get the prompt data
        prompt_data = self.settings.get_prompt(prompt_id)
        if not prompt_data:
            return
        
        # Journaliser la taille de la sélection, jamais son contenu
        log(f"Texte sélectionné: {len(selected_text)} caractères", logging.DEBUG)
        
        # Vérifier si le résultat doit être inséré directement
        insert_directly = bool(prompt_data.get("insert_directly", False))
        
        if not insert_directly:
            # Préparer la fenêtre de réponse en avance
            self.response_window.set_status(prompt_data["status"])
            # Définir la position de déclenchement à la position actuelle du curseur
            self.response_window.set_trigger_position(QCursor.pos())
            self.response_window.set_paste_target(target)
            self._present_response_window()
        
        # Stocker la requête pour permettre un retry
        if not insert_directly:
            self.response_window.store_request(prompt_data["prompt"], selected_text)
        
        # Lancer la requête API en arrière-plan
        self._send_request(
            prompt_data["prompt"],
            selected_text,
            insert_directly,
            target=target,
            reasoning_mode=prompt_data.get("reasoning_mode", "default"),
            model_target=prompt_data.get("model_target"),
            direct_status=(
                f"✅ Envoyé à l'IA — {prompt_data['status']}"
                if insert_directly
                else None
            ),
        )
    
    def _handle_godmode_action(self, selected_text, target=None):
        """Gérer l'action GodMode"""
        if self._closed:
            return
        if not selected_text:
            # Ouvrir directement le dialogue de prompt personnalisé sans texte
            custom_prompt = PromptDialog.show_prompt_dialog("")
            
            if custom_prompt:
                # Préparer la fenêtre de réponse
                self.response_window.set_status("Traitement en cours...")
                # Définir la position de déclenchement à la position actuelle du curseur
                self.response_window.set_trigger_position(QCursor.pos())
                self.response_window.set_paste_target(target)
                self._present_response_window()
                
                # Stocker la requête pour permettre un retry
                self.response_window.store_request(custom_prompt, "")
                
                # Lancer la requête API en arrière-plan avec un texte vide
                self._send_request(custom_prompt, "")
            return
            
        # Afficher le dialogue de prompt personnalisé
        custom_prompt = PromptDialog.show_prompt_dialog(selected_text)
        
        if custom_prompt:
            # Préparer la fenêtre de réponse
            self.response_window.set_status("Traitement en cours...")
            # Définir la position de déclenchement à la position actuelle du curseur
            self.response_window.set_trigger_position(QCursor.pos())
            self.response_window.set_paste_target(target)
            self._present_response_window()
            
            # Stocker la requête pour permettre un retry
            self.response_window.store_request(custom_prompt, selected_text)
            
            # Lancer la requête API en arrière-plan
            self._send_request(custom_prompt, selected_text)
    
    def _handle_screenshot_action(self):
        """Gérer l'action de capture d'écran"""
        if self._closed or not experimental_enabled(self.settings):
            return
        log("Démarrage de la capture d'écran...", logging.DEBUG)
        paste_target = PasteTarget.capture()
        
        # Cacher temporairement le menu contextuel
        QApplication.processEvents()
        
        # Capturer l'écran
        capture_mode = "fullscreen"
        try:
            capture_mode = self.settings.get_screenshot_capture_mode()
        except Exception:
            capture_mode = "fullscreen"

        if capture_mode == "ask":
            chosen = self._choose_screenshot_mode_menu()
            if not chosen:
                return
            capture_mode = chosen

        screenshot_path = capture_screen(capture_mode)
        
        log(f"Résultat de la capture: {screenshot_path}", logging.DEBUG)
        
        # Si nous avons un chemin d'image valide
        if screenshot_path:
            try:
                # Sauvegarder la position actuelle du curseur
                cursor_pos = QCursor.pos()
                
                # Ouvrir directement le dialogue GodMode
                from src.ui.prompt_dialog import PromptDialog
                prompt_dialog = PromptDialog("", None)
                prompt_dialog.set_image_path(screenshot_path)
                
                if prompt_dialog.exec():
                    # Utiliser la méthode d'instance get_prompt() sans argument
                    prompt = prompt_dialog.get_prompt()
                    log(f"Prompt saisi ({len(prompt or '')} caractères)", logging.DEBUG)
                    
                    content = screenshot_path
                    try:
                        with open(screenshot_path, "rb") as image_file:
                            base64_image = base64.b64encode(image_file.read()).decode("utf-8")
                        ext = os.path.splitext(screenshot_path)[1].lower()
                        mime = "image/png" if ext == ".png" else "image/jpeg"
                        content = f"data:{mime};base64,{base64_image}"
                        self._cleanup_screenshot(screenshot_path)
                    except Exception as e:
                        log(f"Erreur lors de la préparation de l'image: {e}", logging.ERROR)
                    
                    # Préparer la fenêtre de réponse
                    self.response_window.set_status("Traitement de la capture d'écran...")
                    # Définir la position de déclenchement à la position du curseur
                    self.response_window.set_trigger_position(cursor_pos)
                    self.response_window.set_paste_target(paste_target)
                    self._present_response_window()
                    
                    # Stocker la requête pour permettre un retry
                    self.response_window.store_request(prompt, content)
                    
                    # Lancer la requête API en arrière-plan
                    self._send_request(prompt, content)
                else:
                    # Si l'utilisateur annule, supprimer l'image
                    self._cleanup_screenshot(screenshot_path)
            except Exception as e:
                log(f"Erreur lors du traitement de la capture: {e}", logging.ERROR)
                self._cleanup_screenshot(screenshot_path)
    
    def _handle_voice_action(self, target=None):
        """Keep ordinary dictation and its delivery actions in one window."""
        if self._closed or not experimental_enabled(self.settings):
            return
        from supermenu_core.audio.dictation_flow import PlainDictationSession
        self.stop_voice_recognition()
        target = target or PasteTarget.capture()

        def insert(text, finished, active):
            deadline = time.monotonic() + 4

            def paste_when_released():
                if not active():
                    return
                held = any(win32api.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12, 0x5B, 0x5C))
                if held and time.monotonic() < deadline:
                    QTimer.singleShot(20, paste_when_released)
                    return
                success = bool(target) and not held and TextInserter().insert_text(text, target=target)
                finished(success)

            paste_when_released()

        try:
            self.voice_recognition = PlainDictationSession(
                lambda options: create_speech_backend(self.settings, options),
                speech_options(self.settings), insert_text=insert,
                correction_factory=lambda: self._create_api_client(settings_for_prompt(self.settings, "corriger")),
                # Read at insertion time, like the model of the « Corriger » prompt.
                correction_reasoning_mode=lambda: (self.settings.get_prompt("corriger") or {}).get("reasoning_mode", "default"),
                auto_insert=self.settings.get_dictation_auto_insert(),
                correct_before_insert=self.settings.get_dictation_correct_before_insert(),
                parent=self,
            )
            self.voice_recognition.start_voice_recognition()
        except ValueError as exc:
            SafeDialogs.show_information("Réglages de dictée", str(exc))

    def start_instant_dictation(self):
        # Checked first: an older session must never become the instant one.
        if not experimental_enabled(self.settings):
            return
        self._instant_session = None
        session = self.voice_recognition
        if session and (session.is_recording or session.is_processing or getattr(session, "_delivery_busy", False)):
            return
        self._handle_voice_action(target=PasteTarget.capture())
        self._instant_session = self.voice_recognition

    def finish_instant_dictation(self):
        session = getattr(self, "_instant_session", None)
        self._instant_session = None
        if session is not None and session is self.voice_recognition:
            session.stop_listening()

    def _handle_voice_prompt_action(self, prompt_id, target=None):
        """Gérer l'action d'un prompt vocal spécifique"""
        if self._closed or not experimental_enabled(self.settings):
            return
        try:
            # Récupérer les données du prompt vocal
            prompt_data = self.settings.get_voice_prompt(prompt_id)
            if not prompt_data:
                log(f"Prompt vocal non trouvé: {prompt_id}", logging.WARNING)
                return
                
            status = prompt_data["status"]
            insert_directly = prompt_data.get("insert_directly", True)
            include_selected_text = prompt_data.get("include_selected_text", False)
            
            log(f"Exécution du prompt vocal: {prompt_data['name']}", logging.DEBUG)
            
            # Si l'option d'inclusion du texte sélectionné est activée, récupérer le texte
            selected_text = ""
            if include_selected_text:
                selected_text = self._try_get_selected_text()
                if selected_text:
                    log(f"Texte sélectionné inclus ({len(selected_text)} caractères)", logging.DEBUG)
            
            # Fonction de rappel pour traiter le texte transcrit
            def process_transcription(text):
                if self._closed:
                    return
                if text:
                    log(f"Transcription vocale reçue ({len(text)} caractères)", logging.DEBUG)
                    
                    full_prompt = compose_voice_prompt(prompt_data, text, selected_text)

                    if insert_directly:
                        self._send_request(
                            full_prompt,
                            "",
                            True,
                            target=target,
                            include_reasoning=False,
                            reasoning_mode=prompt_data.get("reasoning_mode", "default"),
                            model_target=prompt_data.get("model_target"),
                            direct_status=f"✅ Envoyé à l'IA — {status}",
                        )
                    else:
                        # Préparer la fenêtre de réponse
                        self.response_window.set_status(status)
                        # Définir la position de déclenchement à la position actuelle du curseur
                        self.response_window.set_trigger_position(QCursor.pos())
                        self.response_window.set_paste_target(target)
                        self._present_response_window()
                        
                        # Stocker la requête pour permettre un retry
                        self.response_window.store_request(full_prompt, "")
                        
                        # Lancer la requête API en arrière-plan
                        self._send_request(full_prompt, "", reasoning_mode=prompt_data.get("reasoning_mode", "default"), model_target=prompt_data.get("model_target"))
            
            # Arrêter toute reconnaissance vocale en cours
            self.stop_voice_recognition()

            self.voice_recognition = self._create_voice_recognition(
                callback=process_transcription,
            )

            # Démarrer la reconnaissance vocale sans insérer le texte (car nous allons le traiter avec la fonction de rappel)
            self.voice_recognition.start_voice_recognition()
            
        except Exception as e:
            SafeDialogs.show_critical("Erreur de prompt vocal", 
                                f"Une erreur s'est produite lors de l'exécution du prompt vocal : {str(e)}")
    
    def _handle_voice_godmode_action(self, target=None):
        """Gérer l'action de prompt vocal personnalisé (GodMode vocal)"""
        if self._closed or not experimental_enabled(self.settings):
            return
        try:
            # Afficher une boîte de dialogue pour saisir le prompt personnalisé
            from src.ui.prompt_dialog import PromptDialog
            custom_prompt = PromptDialog.show_prompt_dialog("")
            
            if not custom_prompt:
                return  # L'utilisateur a annulé

            # Fonction de rappel pour traiter le texte transcrit
            def process_transcription(text):
                if self._closed:
                    return
                if text:
                    log(
                        f"Transcription vocale reçue pour prompt personnalisé ({len(text)} caractères)",
                        logging.DEBUG,
                    )
                    
                    # Construire le prompt complet avec le texte transcrit
                    full_prompt = compose_voice_prompt({"prompt": custom_prompt}, text)
                    
                    # Préparer la fenêtre de réponse
                    self.response_window.set_status("Traitement du prompt personnalisé...")
                    # Définir la position de déclenchement à la position actuelle du curseur
                    self.response_window.set_trigger_position(QCursor.pos())
                    self.response_window.set_paste_target(target)
                    self._present_response_window()
                    
                    # Stocker la requête pour permettre un retry
                    self.response_window.store_request(full_prompt, "")
                    
                    # Lancer la requête API en arrière-plan
                    self._send_request(full_prompt, "")
            
            # Arrêter toute reconnaissance vocale en cours
            self.stop_voice_recognition()

            self.voice_recognition = self._create_voice_recognition(
                callback=process_transcription,
            )

            # Démarrer la reconnaissance vocale sans insérer le texte (car nous allons le traiter avec la fonction de rappel)
            self.voice_recognition.start_voice_recognition()

        except Exception as e:
            SafeDialogs.show_critical("Erreur de prompt personnalisé",
                                f"Une erreur s'est produite lors du traitement du prompt personnalisé : {str(e)}")

    def stop_voice_recognition(self):
        """Arrête proprement la reconnaissance vocale en cours"""
        if self.voice_recognition:
            try:
                self.voice_recognition.cleanup()
            except Exception as e:
                log(f"Erreur lors de l'arrêt de la reconnaissance vocale: {e}", logging.ERROR)
            finally:
                self.voice_recognition = None

    def _cleanup_screenshot(self, screenshot_path):
        """Nettoyer l'image temporaire"""
        try:
            if not screenshot_path or not os.path.exists(screenshot_path):
                return
 
            basename = os.path.basename(screenshot_path)
            if "supermenu_screenshot_" not in basename:
                return
 
            temp_dir = os.path.abspath(tempfile.gettempdir())
            image_dir = os.path.abspath(os.path.dirname(screenshot_path))
            if image_dir != temp_dir:
                return
 
            os.remove(screenshot_path)
            log(f"Image temporaire supprimée: {screenshot_path}", logging.DEBUG)
        except Exception as e:
            log(f"Erreur lors de la suppression de l'image: {e}", logging.ERROR)
    
    def on_request_started(self):
        """Handle request started signal"""
        if self._closed:
            return
        self.response_window.set_loading(True)

    def on_request_started_scoped(self, request_id, insert_directly):
        if self._closed:
            return
        if (
            not insert_directly
            and request_id == self._active_response_request_id
        ):
            self.response_window.set_loading(True)
    
    def on_request_finished(self, response):
        """Handle request finished signal"""
        if self._closed:
            return
        self.response_window.set_response(response)
        self.response_window.set_loading(False)

    def on_request_finished_scoped(
        self, request_id, response, insert_directly, target
    ):
        if self._closed:
            return
        request = self._pending_requests.pop(request_id, None)
        if request is None:
            return

        client = request["client"]
        if request["insert_directly"] or insert_directly:
            safe_target = request.get("target") or target
            # Sans cible capturée au lancement, coller viserait la fenêtre au
            # premier plan à l'arrivée de la réponse, parfois bien plus tard.
            inserted = safe_target is not None and TextInserter().insert_text(
                response, target=safe_target
            )
            indicator = request.get("indicator")
            if not inserted:
                kept_in = self._keep_refused_direct_response(
                    request, response, safe_target
                )
                if indicator is not None:
                    indicator.set_message("⚠️ Insertion annulée")
                    indicator.move_near_cursor()
                    QTimer.singleShot(2200, indicator.close)
                # Shown in the response window, the answer carries its own
                # warning there: a box would end up below that topmost window.
                if kept_in != "window":
                    reason = (
                        "La fenêtre ou le champ cible a changé."
                        if safe_target is not None
                        else "Aucune fenêtre cible n'était disponible au lancement."
                    )
                    outcome = (
                        " Elle a été copiée dans le presse-papiers."
                        if kept_in == "clipboard"
                        else ""
                    )
                    SafeDialogs.show_information(
                        "Insertion annulée",
                        f"{reason} La réponse n'a pas été collée pour éviter une "
                        f"insertion au mauvais endroit.{outcome}",
                    )
            elif indicator is not None:
                indicator.set_message("✅ Réponse reçue et insérée")
                indicator.move_near_cursor()
                QTimer.singleShot(1200, indicator.close)
            self._release_retired_client_if_idle(client)
            return

        if request_id != self._active_response_request_id:
            self._release_retired_client_if_idle(client)
            return

        self.on_request_finished(response)
        self._release_retired_client_if_idle(client)

    def _keep_refused_direct_response(self, request, response, target):
        """Never discard an answer whose direct insertion was refused.

        Returns "window" when the answer is shown in the response window,
        "clipboard" when it was copied because the window still awaits or
        shows another answer, or None when it could not be kept.
        """
        if self._closed or not response:
            return None
        active_id = self._active_response_request_id
        awaiting_answer = active_id is not None and active_id in self._pending_requests
        if awaiting_answer or self._response_window_shows_answer():
            # Ne pas remplacer une réponse attendue ou en cours de lecture.
            if ClipboardManager.set_clipboard_text_safe(response):
                return "clipboard"
            return None
        try:
            self.response_window.last_reasoning_mode = request.get("reasoning_mode", "default")
            self.response_window.last_model_target = dict(request.get("model_target") or {})
            if request.get("prompt") is not None:
                # Permet « Réessayer », y compris la transcription d'un prompt vocal.
                self.response_window.store_request(request["prompt"], request.get("content") or "")
            self.response_window.set_status("Insertion annulée — réponse conservée")
            self.response_window.set_trigger_position(QCursor.pos())
            self.response_window.set_paste_target(target)
            self._present_response_window()
            self.on_request_finished(response)
        except Exception as e:
            log(f"Affichage de la réponse non insérée impossible: {e}", logging.ERROR)
            if ClipboardManager.set_clipboard_text_safe(response):
                return "clipboard"
            return None
        try:
            # set_response annonce « Terminé » : rappeler que rien n'a été collé.
            self.response_window.status_label.setText("⚠️ Insertion annulée — réponse conservée")
            self.response_window._set_status("warning")
        except Exception as e:
            log(f"Statut d'insertion annulée non affiché: {e}", logging.DEBUG)
        return "window"

    def _response_window_shows_answer(self):
        """Whether the visible response window holds a finished answer."""
        try:
            window = self.response_window
            return bool(window.isVisible() and getattr(window, "final_response", None))
        except RuntimeError:
            return False

    def on_request_error(self, error):
        """Handle request error signal"""
        if self._closed:
            return
        # An error is shown as such and can be copied, never inserted.
        self.response_window.set_error(f"Erreur: {error}")
        self.response_window.set_loading(False)

    def on_request_error_scoped(self, request_id, error):
        if self._closed:
            return
        request = self._pending_requests.pop(request_id, None)
        if request is None:
            return

        client = request["client"]
        if (
            not request["insert_directly"]
            and request_id == self._active_response_request_id
        ):
            self.on_request_error(error)
        elif request["insert_directly"]:
            indicator = request.get("indicator")
            if indicator is not None:
                indicator.set_message("❌ Échec du traitement")
                indicator.move_near_cursor()
                QTimer.singleShot(2200, indicator.close)
            SafeDialogs.show_critical("Erreur de traitement", error)

        self._release_retired_client_if_idle(client)
    
    def on_retry_requested(self):
        """Handle retry request from response window"""
        if self._closed:
            return
        prompt, content = self.response_window.get_last_request()
        if (
            prompt is not None
            and str(content or "").startswith("data:image/")
            and not experimental_enabled(self.settings)
        ):
            # Une capture d'écran n'est plus analysée une fois la fonction coupée.
            self.on_request_error(
                "la capture et l’analyse d’écran sont désactivées "
                "(Réglages > Application > Fonctions expérimentales)"
            )
            return
        if prompt is not None:
            log("Retry de la dernière requête...", logging.INFO)
            self._send_request(prompt, content if content else "", reasoning_mode=getattr(self.response_window, "last_reasoning_mode", "default"), model_target=getattr(self.response_window, "last_model_target", None))

    def update_client_config(self):
        """Met à jour la configuration du client API avec les paramètres actuels."""
        if self._closed:
            return
        self.settings.sync()
        # Another server may now answer at the same address: probe it again.
        clear_capabilities_cache()
        old_client = self.api_client
        if old_client is not None:
            self._retired_clients.append(old_client)
        
        # Recréer le client avec les nouveaux paramètres
        # Le modèle sera automatiquement déterminé selon le type d'endpoint
        self.api_client = self._create_api_client()
        
        self._connect_api_client(self.api_client)
        self._release_retired_client_if_idle(old_client)
            
        provider = self.settings.get_ai_provider()
        endpoint_info = self.settings.get_custom_endpoint() if provider == "custom" else provider
        model_info = (self.settings.get_foundry_model() if provider == "foundry" else
                      self.settings.get_custom_model() if provider == "custom" else self.settings.get_model())
        
        log(
            f"ContextMenuManager: Configuration du client API mise à jour. Endpoint: {endpoint_info}, Modèle: {model_info}",
            logging.INFO,
        )

    def close(self):
        """Stop native/UI resources and reject late API completions."""
        if self._closed:
            return
        self._closed = True
        self._menu_watchdog.stop()

        if self._active_menu is not None:
            active_menu = self._active_menu
            self._active_menu = None
            active_menu.close()
            active_menu.deleteLater()

        self.stop_voice_recognition()

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

        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.response_window.close()
