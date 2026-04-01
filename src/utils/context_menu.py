#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QMenu, QApplication, QDialog
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtCore import QObject, Signal, Qt, QEvent, QTimer, QPoint
import os
import tempfile
import base64
import time
import logging
import win32gui
import win32process
import win32api
import win32con
from pynput.keyboard import Controller, Key

from src.api.openai_client import OpenAIClient
from src.utils.safe_dialogs import SafeDialogs
from src.ui.response_window import ResponseWindow
from src.ui.prompt_dialog import PromptDialog
from src.ui.screen_capture import capture_screen
from src.audio.voice_recognition import VoiceRecognition
from src.utils.text_inserter import TextInserter
from src.utils.logger import log
from src.utils.clipboard_manager import ClipboardManager
from src.audio.audio_config import CLIPBOARD_COPY_DELAY, CLIPBOARD_RESTORE_DELAY

class ContextMenuManager(QObject):
    """Manage the context menu for text operations"""
    
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        # Initialiser le client API avec les paramètres
        # Ne pas passer le modèle ici, OpenAIClient le déterminera selon le type d'endpoint
        self.api_client = OpenAIClient(
            settings=settings,
            api_key=settings.get_api_key()
        )
        self.response_window = ResponseWindow()
        self.voice_recognition = None
        
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
        
        # Connect signals
        self.api_client.request_started.connect(self.on_request_started)
        self.api_client.request_finished.connect(self.on_request_finished)
        self.api_client.request_error.connect(self.on_request_error)
        
        # Connecter le signal de retry
        self.response_window.retry_requested.connect(self.on_retry_requested)

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
                if self._menu_watchdog.isActive():
                    self._menu_watchdog.stop()
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

                if pos is not None and not menu.geometry().contains(pos):
                    menu.close()

            self._last_lbutton_down = lbutton_down
        except Exception:
            pass

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

                    if pos is not None and not menu.geometry().contains(pos):
                        menu.close()
        except Exception:
            pass

        return super().eventFilter(obj, event)
    
    def _create_temp_api_client(self):
        """
        Crée un client OpenAI temporaire avec les paramètres actuels.
        Utilisé pour les requêtes vocales où on ne veut pas interférer avec le client principal.
        
        Returns:
            OpenAIClient: Un nouveau client API configuré
        """
        # Créer un client temporaire qui déterminera automatiquement le bon modèle
        temp_client = OpenAIClient(
            settings=self.settings,
            api_key=self.settings.get_api_key()
        )
        
        return temp_client
    
    def show_menu(self):
        """Show the context menu at the current cursor position"""
        if self._is_menu_open:
            return

        self._is_menu_open = True
        # Créer le menu
        menu = QMenu()
        self._active_menu = menu
        self._menu_owner_pid = self._get_foreground_pid()
        self._menu_opened_at = time.monotonic()
        try:
            self._last_lbutton_down = (win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000) != 0
        except Exception:
            self._last_lbutton_down = False
        menu.setAttribute(Qt.WA_DeleteOnClose)  # S'assurer que le menu est supprimé après fermeture
        menu.setWindowFlags(menu.windowFlags() | Qt.Popup | Qt.FramelessWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        
        # Fermer le menu si on clique en dehors ou si on perd le focus
        menu.aboutToHide.connect(menu.close)
        
        # Tenter de récupérer le texte sélectionné sans bloquer
        selected_text = self._try_get_selected_text()
        
        # Ajouter les éléments de menu basés sur les prompts configurés
        prompts = self.settings.get_prompts()
        
        # Trier les prompts par position
        sorted_prompts = sorted(prompts.items(), key=lambda x: x[1].get("position", 999))
        
        # Ajouter tous les prompts au menu
        for prompt_id, prompt_data in sorted_prompts:
            action = menu.addAction(prompt_data["name"])
            action.setData(("prompt", prompt_id, selected_text))
            if selected_text:
                action.setEnabled(True)
            else:
                # Désactiver l'action si aucun texte n'est sélectionné
                action.setEnabled(False)
        
        # Ajouter un séparateur
        menu.addSeparator()
        
        # Ajouter l'option GodMode (toujours disponible)
        godmode_action = menu.addAction("🔮 Mode Personnalisé")
        godmode_action.setData(("godmode", selected_text if selected_text else ""))
        
        # Afficher le menu à la position du curseur
        # Utiliser exec_ pour les hotkeys car il est bloquant et assure que le menu reste visible
        # jusqu'à ce qu'une action soit sélectionnée ou que l'utilisateur clique ailleurs
        chosen_action = None
        try:
            if not self._menu_watchdog.isActive():
                self._menu_watchdog.start()
            chosen_action = menu.exec_(QCursor.pos())  # Utiliser exec_ au lieu de popup()
        finally:
            if self._menu_watchdog.isActive():
                self._menu_watchdog.stop()
            self._is_menu_open = False
            self._active_menu = None
            self._menu_owner_pid = None
            self._last_lbutton_down = False
            self._menu_opened_at = None

        if chosen_action is None:
            return

        action_data = chosen_action.data()
        if not action_data:
            return

        action_kind = action_data[0]
        if action_kind == "prompt":
            _, prompt_id, action_text = action_data
            self._handle_menu_action(prompt_id, action_text)
        elif action_kind == "godmode":
            _, action_text = action_data
            self._handle_godmode_action(action_text)

    def show_custom_mode(self):
        """Ouvrir directement le mode personnalisé depuis un raccourci."""
        selected_text = self._try_get_selected_text()
        self._handle_godmode_action(selected_text)

    def _choose_screenshot_mode_menu(self):
        if self._is_menu_open:
            return None

        self._is_menu_open = True
        menu = QMenu()
        self._active_menu = menu
        self._menu_owner_pid = self._get_foreground_pid()
        self._menu_opened_at = time.monotonic()
        try:
            self._last_lbutton_down = (win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000) != 0
        except Exception:
            self._last_lbutton_down = False

        menu.setAttribute(Qt.WA_DeleteOnClose)
        menu.setWindowFlags(menu.windowFlags() | Qt.Popup | Qt.FramelessWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        menu.aboutToHide.connect(menu.close)

        fullscreen_action = menu.addAction("Plein écran")
        region_action = menu.addAction("Sélection de zone")
        menu.addSeparator()
        cancel_action = menu.addAction("Annuler")

        try:
            if not self._menu_watchdog.isActive():
                self._menu_watchdog.start()
            chosen_action = menu.exec_(QCursor.pos())
            if chosen_action is None or chosen_action == cancel_action:
                return None
            if chosen_action == fullscreen_action:
                return "fullscreen"
            if chosen_action == region_action:
                return "region"
            return None
        finally:
            if self._menu_watchdog.isActive():
                self._menu_watchdog.stop()
            self._is_menu_open = False
            self._active_menu = None
            self._menu_owner_pid = None
            self._last_lbutton_down = False
            self._menu_opened_at = None
    
    def show_voice_menu(self):
        """Show only the voice interaction menu at the current cursor position"""
        if self._is_menu_open:
            return

        self._is_menu_open = True
        # Créer le menu
        menu = QMenu()
        self._active_menu = menu
        self._menu_owner_pid = self._guess_menu_owner_pid()
        self._menu_opened_at = time.monotonic()
        try:
            self._last_lbutton_down = (win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000) != 0
        except Exception:
            self._last_lbutton_down = False
        menu.setAttribute(Qt.WA_DeleteOnClose)  # S'assurer que le menu est supprimé après fermeture
        menu.setWindowFlags(menu.windowFlags() | Qt.Popup | Qt.FramelessWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        
        # Fermer le menu si on clique en dehors ou si on perd le focus
        menu.aboutToHide.connect(menu.close)
        
        # Ajouter l'option de reconnaissance vocale
        voice_action = menu.addAction("Écrire à la voix")
        voice_action.triggered.connect(self._handle_voice_action)
        
        # Ajouter un séparateur
        menu.addSeparator()
        
        # Récupérer et ajouter tous les prompts vocaux configurés
        voice_prompts = self.settings.get_voice_prompts()
        
        # Trier les prompts vocaux par position
        sorted_voice_prompts = sorted(voice_prompts.items(), key=lambda x: x[1].get("position", 999))
        
        for prompt_id, prompt_data in sorted_voice_prompts:
            # Créer une fonction de rappel spécifique pour ce prompt
            def create_callback(p_id):
                return lambda: self._handle_voice_prompt_action(p_id)
                
            callback = create_callback(prompt_id)
            
            action = menu.addAction(prompt_data["name"])
            action.triggered.connect(callback)
        
        # Ajouter un séparateur
        menu.addSeparator()
        
        # Ajouter l'option GodMode vocal (personnalisation à la volée)
        godmode_action = menu.addAction("🔮 Prompt vocal personnalisé")
        godmode_action.triggered.connect(self._handle_voice_godmode_action)
        
        # Afficher le menu à la position du curseur
        try:
            if not self._menu_watchdog.isActive():
                self._menu_watchdog.start()
            menu.exec_(QCursor.pos())  # Utiliser exec_ au lieu de popup()
        finally:
            if self._menu_watchdog.isActive():
                self._menu_watchdog.stop()
            self._is_menu_open = False
            self._active_menu = None
            self._menu_owner_pid = None
            self._last_lbutton_down = False
            self._menu_opened_at = None
    
    def _try_get_selected_text(self):
        """
        Tente de récupérer le texte sélectionné sans bloquer l'interface utilisateur.
        Utilise plusieurs méthodes pour maximiser les chances de succès.
        
        Returns:
            str: Le texte sélectionné ou une chaîne vide si aucun texte n'est sélectionné
        """
        selected_text = ""
        
        try:
            # Sauvegarder le contenu actuel du presse-papiers avec ClipboardManager
            old_clipboard = ClipboardManager.get_clipboard_text_safe()
            
            # IMPORTANT: Vider le clipboard avant de copier pour détecter si quelque chose a été copié
            ClipboardManager.set_clipboard_text_safe("")
            time.sleep(0.05)  # Petit délai pour s'assurer que le clipboard est vidé
            
            # Méthode 1: Utiliser pynput pour copier le texte sélectionné
            try:
                try:
                    hwnd = win32gui.GetForegroundWindow()
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid == os.getpid():
                        return ""
                    is_console = win32gui.GetClassName(hwnd) in (
                        "ConsoleWindowClass",
                        "CASCADIA_HOSTING_WINDOW_CLASS",
                    )
                except Exception:
                    is_console = False
                    pass

                if is_console:
                    self.keyboard.press(Key.ctrl)
                    self.keyboard.press(Key.insert)
                    self.keyboard.release(Key.insert)
                    self.keyboard.release(Key.ctrl)
                else:
                    self.keyboard.press(Key.ctrl)
                    self.keyboard.press('c')
                    self.keyboard.release('c')
                    self.keyboard.release(Key.ctrl)

                time.sleep(CLIPBOARD_COPY_DELAY)
            except KeyboardInterrupt:
                return ""
            except Exception as e:
                log(f"Erreur pynput: {e}", logging.DEBUG)
            
            # Méthode 2: Récupérer le texte avec ClipboardManager
            selected_text = ClipboardManager.get_clipboard_text_safe()

            if (not selected_text or selected_text == "") and 'is_console' in locals() and is_console:
                try:
                    self.keyboard.press(Key.ctrl)
                    self.keyboard.press(Key.shift)
                    self.keyboard.press('c')
                    self.keyboard.release('c')
                    self.keyboard.release(Key.shift)
                    self.keyboard.release(Key.ctrl)
                    time.sleep(CLIPBOARD_COPY_DELAY)
                    selected_text = ClipboardManager.get_clipboard_text_safe()
                except Exception:
                    pass
            
            # Si le clipboard est toujours vide, aucun texte n'était sélectionné
            if not selected_text or selected_text == "":
                log("Aucun texte détecté après Ctrl+C", logging.DEBUG)
                # Restaurer immédiatement l'ancien clipboard
                if old_clipboard:
                    ClipboardManager.set_clipboard_text_safe(old_clipboard)
                return ""
            
            # Log pour déboguer
            log(f"Texte copié avec succès: {selected_text[:50]}{'...' if len(selected_text) > 50 else ''}", logging.DEBUG)
            
            # Attendre avant de restaurer pour éviter les interférences
            time.sleep(CLIPBOARD_RESTORE_DELAY)
            
            # Restaurer l'ancien contenu du presse-papiers
            if old_clipboard:
                ClipboardManager.set_clipboard_text_safe(old_clipboard)
        
        except Exception as e:
            log(
                f"Erreur générale lors de la récupération du texte sélectionné: {e}",
                logging.DEBUG,
            )
            selected_text = ""
        except KeyboardInterrupt:
            return ""
        
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
            
        # Ne pas afficher le texte sélectionné dans les logs pour éviter la duplication
        # print(f"Texte sélectionné: {selected_text[:30]}...")
        return selected_text
    
    def _handle_menu_action(self, prompt_id, selected_text=None):
        """Handle a menu action"""
        # Get the selected text
        if selected_text is None:
            selected_text = self._get_selected_text()
        if not selected_text:
            return
        
        # Get the prompt data
        prompt_data = self.settings.get_prompt(prompt_id)
        if not prompt_data:
            return
        
        # Afficher un log avec le texte sélectionné (une seule fois)
        log(f"Texte sélectionné: {selected_text[:30]}...", logging.DEBUG)
        
        # Vérifier si le résultat doit être inséré directement
        insert_directly = prompt_data.get("insert_directly", False)
        
        if not insert_directly:
            # Préparer la fenêtre de réponse en avance
            self.response_window.set_status(prompt_data["status"])
            # Définir la position de déclenchement à la position actuelle du curseur
            self.response_window.set_trigger_position(QCursor.pos())
            self.response_window.present()
        
        # Stocker la requête pour permettre un retry
        if not insert_directly:
            self.response_window.store_request(prompt_data["prompt"], selected_text)
        
        # Lancer la requête API en arrière-plan
        self.api_client.send_request(prompt_data["prompt"], selected_text, insert_directly)
    
    def _handle_godmode_action(self, selected_text):
        """Gérer l'action GodMode"""
        if not selected_text:
            # Ouvrir directement le dialogue de prompt personnalisé sans texte
            custom_prompt = PromptDialog.show_prompt_dialog("")
            
            if custom_prompt:
                # Préparer la fenêtre de réponse
                self.response_window.set_status("Traitement en cours...")
                # Définir la position de déclenchement à la position actuelle du curseur
                self.response_window.set_trigger_position(QCursor.pos())
                self.response_window.present()
                
                # Stocker la requête pour permettre un retry
                self.response_window.store_request(custom_prompt, "")
                
                # Lancer la requête API en arrière-plan avec un texte vide
                self.api_client.send_request(custom_prompt, "")
            return
            
        # Afficher le dialogue de prompt personnalisé
        custom_prompt = PromptDialog.show_prompt_dialog(selected_text)
        
        if custom_prompt:
            # Préparer la fenêtre de réponse
            self.response_window.set_status("Traitement en cours...")
            # Définir la position de déclenchement à la position actuelle du curseur
            self.response_window.set_trigger_position(QCursor.pos())
            self.response_window.present()
            
            # Stocker la requête pour permettre un retry
            self.response_window.store_request(custom_prompt, selected_text)
            
            # Lancer la requête API en arrière-plan
            self.api_client.send_request(custom_prompt, selected_text)
    
    def _handle_screenshot_action(self):
        """Gérer l'action de capture d'écran"""
        log("Démarrage de la capture d'écran...", logging.DEBUG)
        
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
                    log(f"Prompt saisi: {prompt}", logging.DEBUG)
                    
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
                    self.response_window.present()
                    
                    # Stocker la requête pour permettre un retry
                    self.response_window.store_request(prompt, content)
                    
                    # Lancer la requête API en arrière-plan
                    self.api_client.send_request(prompt, content)
                else:
                    # Si l'utilisateur annule, supprimer l'image
                    self._cleanup_screenshot(screenshot_path)
            except Exception as e:
                log(f"Erreur lors du traitement de la capture: {e}", logging.ERROR)
                self._cleanup_screenshot(screenshot_path)
    
    def _handle_voice_action(self):
        """Gérer l'action de reconnaissance vocale"""
        try:
            # Récupérer l'index du microphone depuis les paramètres
            microphone_index = self.settings.get_microphone_index()

            # Arrêter toute reconnaissance vocale en cours
            self.stop_voice_recognition()

            # Créer une instance de VoiceRecognition avec la clé API OpenAI et l'index du microphone
            self.voice_recognition = VoiceRecognition(
                api_key=self.settings.get_api_key(),
                microphone_index=microphone_index
            )

            # Afficher un message de débogage sur le microphone utilisé
            if microphone_index is not None:
                log(f"Utilisation du microphone avec l'index: {microphone_index}", logging.DEBUG)
            else:
                log("Utilisation du microphone par défaut du système", logging.DEBUG)

            # Démarrer la reconnaissance vocale
            self.voice_recognition.start_voice_recognition()
        except Exception as e:
            SafeDialogs.show_critical("Erreur de reconnaissance vocale",
                                f"Une erreur s'est produite lors de la reconnaissance vocale : {str(e)}")

    
    def _handle_describe_response_action(self):
        """Gérer l'action de description de réponse vocale"""
        try:
            # Récupérer l'index du microphone depuis les paramètres
            microphone_index = self.settings.get_microphone_index()
            
            # Récupérer le prompt de description de réponse depuis les paramètres
            describe_prompt = self.settings.get_describe_response_prompt()
            
            # Fonction de rappel pour traiter le texte transcrit
            def process_transcription(text):
                if text:
                    log("Traitement de la transcription vocale...", logging.DEBUG)
                    
                    # Construire le prompt complet avec le texte transcrit
                    full_prompt = f"{describe_prompt}\n\n{text}"
                    
                    # Créer un client OpenAI temporaire pour cette requête spécifique
                    temp_client = self._create_temp_api_client()

                    # Afficher un indicateur d'attente (non bloquant)
                    QApplication.setOverrideCursor(Qt.WaitCursor)

                    def _on_finished(response_text: str):
                        try:
                            try:
                                temp_client.request_finished.disconnect(_on_finished)
                                temp_client.request_error.disconnect(_on_error)
                            except (TypeError, RuntimeError):
                                pass
                            text_inserter = TextInserter()
                            text_inserter.insert_text(response_text)
                            log("Réponse insérée avec succès", logging.INFO)
                        finally:
                            QApplication.restoreOverrideCursor()

                    def _on_error(error_message: str):
                        try:
                            try:
                                temp_client.request_finished.disconnect(_on_finished)
                                temp_client.request_error.disconnect(_on_error)
                            except (TypeError, RuntimeError):
                                pass
                            log(f"Erreur lors de la requête API: {error_message}", logging.ERROR)
                            SafeDialogs.show_critical(
                                "Erreur de traitement",
                                f"Une erreur s'est produite lors du traitement de la réponse : {error_message}",
                            )
                        finally:
                            QApplication.restoreOverrideCursor()

                    # Connexions temporaires (une seule fois)
                    temp_client.request_finished.connect(_on_finished)
                    temp_client.request_error.connect(_on_error)

                    # Lancer la requête en arrière-plan
                    temp_client.send_request(full_prompt, "", insert_directly=False)
            
            # Arrêter toute reconnaissance vocale en cours
            self.stop_voice_recognition()

            # Créer une instance de VoiceRecognition avec la clé API OpenAI, l'index du microphone et la fonction de rappel
            self.voice_recognition = VoiceRecognition(
                api_key=self.settings.get_api_key(),
                microphone_index=microphone_index,
                callback=process_transcription
            )

            # Afficher un message de débogage sur le microphone utilisé
            if microphone_index is not None:
                log(f"Utilisation du microphone avec l'index: {microphone_index}", logging.DEBUG)
            else:
                log("Utilisation du microphone par défaut du système", logging.DEBUG)

            # Démarrer la reconnaissance vocale sans insérer le texte (car nous allons le traiter avec la fonction de rappel)
            self.voice_recognition.start_voice_recognition(insert_text=False)
            
        except Exception as e:
            SafeDialogs.show_critical("Erreur de description de réponse", 
                                f"Une erreur s'est produite lors de la description de réponse : {str(e)}")

    def _handle_voice_prompt_action(self, prompt_id):
        """Gérer l'action d'un prompt vocal spécifique"""
        try:
            # Récupérer l'index du microphone depuis les paramètres
            microphone_index = self.settings.get_microphone_index()
            
            # Récupérer les données du prompt vocal
            prompt_data = self.settings.get_voice_prompt(prompt_id)
            if not prompt_data:
                log(f"Prompt vocal non trouvé: {prompt_id}", logging.WARNING)
                return
                
            prompt_text = prompt_data["prompt"]
            status = prompt_data["status"]
            insert_directly = prompt_data.get("insert_directly", True)
            include_selected_text = prompt_data.get("include_selected_text", False)
            prompt_order = prompt_data.get("prompt_order", "prompt_transcription_selected")
            
            log(f"Exécution du prompt vocal: {prompt_data['name']}", logging.DEBUG)
            
            # Si l'option d'inclusion du texte sélectionné est activée, récupérer le texte
            selected_text = ""
            if include_selected_text:
                selected_text = self._try_get_selected_text()
                if selected_text:
                    log(f"Texte sélectionné inclus: {selected_text[:50]}...", logging.DEBUG)
            
            # Fonction de rappel pour traiter le texte transcrit
            def process_transcription(text):
                if text:
                    log(f"Transcription vocale reçue: {text[:50]}...", logging.DEBUG)
                    
                    # Construire le prompt complet selon l'ordre spécifié
                    if include_selected_text and selected_text:
                        # Construire le prompt selon l'ordre spécifié
                        if prompt_order == "prompt_transcription_selected":
                            full_prompt = f"{prompt_text}\n\nTexte transcrit: {text}\n\nTexte sélectionné: {selected_text}"
                        elif prompt_order == "prompt_selected_transcription":
                            full_prompt = f"{prompt_text}\n\nTexte sélectionné: {selected_text}\n\nTexte transcrit: {text}"
                        elif prompt_order == "selected_prompt_transcription":
                            full_prompt = f"Texte sélectionné: {selected_text}\n\n{prompt_text}\n\nTexte transcrit: {text}"
                        elif prompt_order == "transcription_prompt_selected":
                            full_prompt = f"Texte transcrit: {text}\n\n{prompt_text}\n\nTexte sélectionné: {selected_text}"
                        elif prompt_order == "transcription_selected_prompt":
                            full_prompt = f"Texte transcrit: {text}\n\nTexte sélectionné: {selected_text}\n\n{prompt_text}"
                        elif prompt_order == "selected_transcription_prompt":
                            full_prompt = f"Texte sélectionné: {selected_text}\n\nTexte transcrit: {text}\n\n{prompt_text}"
                        else:
                            # Ordre par défaut
                            full_prompt = f"{prompt_text}\n\nTexte transcrit: {text}\n\nTexte sélectionné: {selected_text}"
                    else:
                        # Pas de texte sélectionné, simplement prompt + transcription
                        full_prompt = f"{prompt_text}\n\n{text}"
                    
                    # Créer un client OpenAI temporaire pour cette requête spécifique
                    temp_client = self._create_temp_api_client()

                    if insert_directly:
                        QApplication.setOverrideCursor(Qt.WaitCursor)

                        def _on_finished(response_text: str):
                            try:
                                try:
                                    temp_client.request_finished.disconnect(_on_finished)
                                    temp_client.request_error.disconnect(_on_error)
                                except (TypeError, RuntimeError):
                                    pass
                                text_inserter = TextInserter()
                                text_inserter.insert_text(response_text)
                                log("Réponse insérée avec succès", logging.INFO)
                            finally:
                                QApplication.restoreOverrideCursor()

                        def _on_error(error_message: str):
                            try:
                                try:
                                    temp_client.request_finished.disconnect(_on_finished)
                                    temp_client.request_error.disconnect(_on_error)
                                except (TypeError, RuntimeError):
                                    pass
                                log(f"Erreur lors de la requête API: {error_message}", logging.ERROR)
                                SafeDialogs.show_critical(
                                    "Erreur de traitement",
                                    f"Une erreur s'est produite lors du traitement de la réponse : {error_message}",
                                )
                            finally:
                                QApplication.restoreOverrideCursor()

                        temp_client.request_finished.connect(_on_finished)
                        temp_client.request_error.connect(_on_error)
                        temp_client.send_request(full_prompt, "", insert_directly=False)
                    else:
                        # Préparer la fenêtre de réponse
                        self.response_window.set_status(status)
                        # Définir la position de déclenchement à la position actuelle du curseur
                        self.response_window.set_trigger_position(QCursor.pos())
                        self.response_window.present()
                        
                        # Stocker la requête pour permettre un retry
                        self.response_window.store_request(full_prompt, "")
                        
                        # Lancer la requête API en arrière-plan
                        self.api_client.send_request(full_prompt, "")
            
            # Arrêter toute reconnaissance vocale en cours
            self.stop_voice_recognition()

            # Créer une instance de VoiceRecognition avec la clé API OpenAI, l'index du microphone et la fonction de rappel
            self.voice_recognition = VoiceRecognition(
                api_key=self.settings.get_api_key(),
                microphone_index=microphone_index,
                callback=process_transcription
            )

            # Afficher un message de débogage sur le microphone utilisé
            if microphone_index is not None:
                log(f"Utilisation du microphone avec l'index: {microphone_index}", logging.DEBUG)
            else:
                log("Utilisation du microphone par défaut du système", logging.DEBUG)

            # Démarrer la reconnaissance vocale sans insérer le texte (car nous allons le traiter avec la fonction de rappel)
            self.voice_recognition.start_voice_recognition(insert_text=False)
            
        except Exception as e:
            SafeDialogs.show_critical("Erreur de prompt vocal", 
                                f"Une erreur s'est produite lors de l'exécution du prompt vocal : {str(e)}")
    
    def _handle_voice_godmode_action(self):
        """Gérer l'action de prompt vocal personnalisé (GodMode vocal)"""
        try:
            # Afficher une boîte de dialogue pour saisir le prompt personnalisé
            from src.ui.prompt_dialog import PromptDialog
            custom_prompt = PromptDialog.show_prompt_dialog("")
            
            if not custom_prompt:
                return  # L'utilisateur a annulé
                
            # Récupérer l'index du microphone depuis les paramètres
            microphone_index = self.settings.get_microphone_index()
            
            # Fonction de rappel pour traiter le texte transcrit
            def process_transcription(text):
                if text:
                    log(
                        f"Transcription vocale reçue pour prompt personnalisé: {text[:50]}...",
                        logging.DEBUG,
                    )
                    
                    # Construire le prompt complet avec le texte transcrit
                    full_prompt = f"{custom_prompt}\n\n{text}"
                    
                    # Préparer la fenêtre de réponse
                    self.response_window.set_status("Traitement du prompt personnalisé...")
                    # Définir la position de déclenchement à la position actuelle du curseur
                    self.response_window.set_trigger_position(QCursor.pos())
                    self.response_window.present()
                    
                    # Stocker la requête pour permettre un retry
                    self.response_window.store_request(full_prompt, "")
                    
                    # Lancer la requête API en arrière-plan
                    self.api_client.send_request(full_prompt, "")
            
            # Arrêter toute reconnaissance vocale en cours
            self.stop_voice_recognition()

            # Créer une instance de VoiceRecognition avec la clé API OpenAI, l'index du microphone et la fonction de rappel
            self.voice_recognition = VoiceRecognition(
                api_key=self.settings.get_api_key(),
                microphone_index=microphone_index,
                callback=process_transcription
            )

            # Afficher un message de débogage sur le microphone utilisé
            if microphone_index is not None:
                log(f"Utilisation du microphone avec l'index: {microphone_index}", logging.DEBUG)
            else:
                log("Utilisation du microphone par défaut du système", logging.DEBUG)

            # Démarrer la reconnaissance vocale sans insérer le texte (car nous allons le traiter avec la fonction de rappel)
            self.voice_recognition.start_voice_recognition(insert_text=False)

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
        self.response_window.set_loading(True)
    
    def on_request_finished(self, response):
        """Handle request finished signal"""
        self.response_window.set_response(response)
        self.response_window.set_loading(False)
    
    def on_request_error(self, error):
        """Handle request error signal"""
        self.response_window.set_response(f"Erreur: {error}")
        self.response_window.set_loading(False)
    
    def on_retry_requested(self):
        """Handle retry request from response window"""
        prompt, content = self.response_window.get_last_request()
        if prompt is not None:
            log("Retry de la dernière requête...", logging.INFO)
            self.api_client.send_request(prompt, content if content else "")

    def _handle_settings_action(self):
        """Gérer l'action de paramètres"""
        # Ouvrir la fenêtre de paramètres
        from src.ui.settings_window import SettingsWindow
        settings_window = SettingsWindow(self.settings)
        settings_window.show()

    def update_client_config(self):
        """Met à jour la configuration du client API avec les paramètres actuels."""
        # Déconnecter les anciens signaux pour éviter les fuites mémoire
        if self.api_client:
            try:
                self.api_client.request_started.disconnect(self.on_request_started)
                self.api_client.request_finished.disconnect(self.on_request_finished)
                self.api_client.request_error.disconnect(self.on_request_error)
            except (TypeError, RuntimeError) as e:
                # Les signaux peuvent ne pas être connectés
                log(f"Note: Déconnexion des signaux: {e}", logging.DEBUG)
        
        # Recréer le client avec les nouveaux paramètres
        # Le modèle sera automatiquement déterminé selon le type d'endpoint
        self.api_client = OpenAIClient(
            settings=self.settings,
            api_key=self.settings.get_api_key()
        )
        
        # Reconnecter les signaux
        self.api_client.request_started.connect(self.on_request_started)
        self.api_client.request_finished.connect(self.on_request_finished)
        self.api_client.request_error.connect(self.on_request_error)
            
        endpoint_info = self.settings.get_custom_endpoint() if self.settings.get_use_custom_endpoint() else "OpenAI"
        model_info = self.settings.get_custom_model() if self.settings.get_use_custom_endpoint() else self.settings.get_model()
        
        log(
            f"ContextMenuManager: Configuration du client API mise à jour. Endpoint: {endpoint_info}, Modèle: {model_info}",
            logging.INFO,
        )
