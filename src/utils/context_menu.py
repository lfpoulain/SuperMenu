#!/usr/bin/env python
# -*- coding: utf-8 -*-

import win32clipboard
from PySide6.QtWidgets import QMenu, QApplication, QDialog
from PySide6.QtGui import QCursor
from PySide6.QtCore import QObject, Signal, Qt
import os
import tempfile
import time
import tkinter as tk
import pyautogui
import logging

from src.api.openai_client import OpenAIClient
from utils.safe_dialogs import SafeDialogs
from src.ui.response_window import ResponseWindow
from src.ui.prompt_dialog import PromptDialog
from src.ui.screen_capture import capture_screen
from src.audio.voice_recognition import VoiceRecognition
from audio.text_inserter import TextInserter
from utils.logger import log

class ContextMenuManager(QObject):
    """Manage the context menu for text operations"""
    
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        # Initialiser le client API avec les paramètres
        self.api_client = OpenAIClient(
            settings=settings,
            api_key=settings.get_api_key(),
            model=settings.get_model()
        )
        self.response_window = ResponseWindow()
        self.voice_recognition = None
        
        # Connect signals
        self.api_client.request_started.connect(self.on_request_started)
        self.api_client.request_finished.connect(self.on_request_finished)
        self.api_client.request_error.connect(self.on_request_error)
    
    def _create_temp_api_client(self):
        """
        Crée un client OpenAI temporaire avec les paramètres actuels.
        Utilisé pour les requêtes vocales où on ne veut pas interférer avec le client principal.
        
        Returns:
            OpenAIClient: Un nouveau client API configuré
        """
        temp_client = OpenAIClient(
            settings=self.settings,
            api_key=self.settings.get_api_key(),
            model=self.settings.get_model()
        )
        
        # Définir le modèle actuel (seulement si on n'utilise pas d'endpoint personnalisé)
        if not self.settings.get_use_custom_endpoint():
            temp_client.set_model(self.settings.get_model())
        
        return temp_client
    
    def show_menu(self):
        """Show the context menu at the current cursor position"""
        # Créer le menu
        menu = QMenu()
        menu.setAttribute(Qt.WA_DeleteOnClose)  # S'assurer que le menu est supprimé après fermeture
        
        # Tenter de récupérer le texte sélectionné sans bloquer
        selected_text = self._try_get_selected_text()
        
        # Ajouter les éléments de menu basés sur les prompts configurés
        prompts = self.settings.get_prompts()
        
        # Trier les prompts par position
        sorted_prompts = sorted(prompts.items(), key=lambda x: x[1].get("position", 999))
        
        # Ajouter tous les prompts au menu
        for prompt_id, prompt_data in sorted_prompts:
            # Créer une fonction de rappel spécifique pour ce prompt
            def create_callback(p_id):
                return lambda: self._handle_menu_action(p_id)
                
            callback = create_callback(prompt_id)
            
            action = menu.addAction(prompt_data["name"])
            if selected_text:
                action.triggered.connect(callback)
            else:
                # Désactiver l'action si aucun texte n'est sélectionné
                action.setEnabled(False)
        
        # Ajouter un séparateur
        menu.addSeparator()
        
        # Ajouter l'option GodMode (toujours disponible)
        godmode_action = menu.addAction("🔮 Mode Personnalisé")
        if selected_text:
            godmode_action.triggered.connect(lambda: self._handle_godmode_action(selected_text))
        else:
            godmode_action.triggered.connect(lambda: self._handle_godmode_action(""))
        
        # Afficher le menu à la position du curseur
        # Utiliser exec_ pour les hotkeys car il est bloquant et assure que le menu reste visible
        # jusqu'à ce qu'une action soit sélectionnée ou que l'utilisateur clique ailleurs
        menu.exec_(QCursor.pos())  # Utiliser exec_ au lieu de popup()
    
    def show_voice_menu(self):
        """Show only the voice interaction menu at the current cursor position"""
        # Créer le menu
        menu = QMenu()
        menu.setAttribute(Qt.WA_DeleteOnClose)  # S'assurer que le menu est supprimé après fermeture
        
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
        menu.exec_(QCursor.pos())  # Utiliser exec_ au lieu de popup()
    
    def _try_get_selected_text(self):
        """
        Tente de récupérer le texte sélectionné sans bloquer l'interface utilisateur.
        Utilise plusieurs méthodes pour maximiser les chances de succès.
        
        Returns:
            str: Le texte sélectionné ou une chaîne vide si aucun texte n'est sélectionné
        """
        selected_text = ""
        
        try:
            # Sauvegarder le contenu actuel du presse-papiers
            try:
                win32clipboard.OpenClipboard()
                try:
                    old_clipboard = (
                        win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                        if win32clipboard.IsClipboardFormatAvailable(
                            win32clipboard.CF_UNICODETEXT
                        )
                        else ""
                    )
                finally:
                    win32clipboard.CloseClipboard()
            except Exception as e:
                # Utiliser log pour les erreurs non bloquantes
                log(
                    f"Erreur lors de la sauvegarde du presse-papiers: {e}",
                    logging.DEBUG,
                )
                old_clipboard = ""
            
            # Méthode 1: Utiliser pyautogui pour copier le texte sélectionné
            old_pause = pyautogui.PAUSE
            try:
                # Désactiver la pause pour éviter les erreurs de _handlePause
                pyautogui.PAUSE = 0
                # Utiliser directement les fonctions de touche au lieu de hotkey
                pyautogui.keyDown("ctrl")
                pyautogui.press("c")
                time.sleep(0.1)  # Réduire le délai pour améliorer la réactivité
            except Exception as e:
                log(f"Erreur pyautogui: {e}", logging.DEBUG)
            finally:
                try:
                    pyautogui.keyUp("ctrl")
                except Exception as e_keyup:
                    log(
                        f"Erreur spécifique lors de pyautogui.keyUp('ctrl'): {e_keyup}",
                        logging.ERROR,
                    )
                pyautogui.PAUSE = old_pause
            
            # Méthode 2: Récupérer le texte avec win32clipboard
            try:
                win32clipboard.OpenClipboard()
                try:
                    if win32clipboard.IsClipboardFormatAvailable(
                        win32clipboard.CF_UNICODETEXT
                    ):
                        selected_text = win32clipboard.GetClipboardData(
                            win32clipboard.CF_UNICODETEXT
                        )
                finally:
                    win32clipboard.CloseClipboard()
            except Exception as e:
                log(f"Erreur win32clipboard: {e}", logging.DEBUG)
                # Si la méthode 2 échoue, essayer une autre approche
                try:
                    # Méthode alternative avec tkinter
                    root = tk.Tk()
                    root.withdraw()
                    selected_text = root.clipboard_get()
                    root.destroy()
                except Exception as e:
                    log(f"Erreur tkinter: {e}", logging.DEBUG)
                    selected_text = ""
            
            # Restaurer l'ancien contenu du presse-papiers
            try:
                if old_clipboard:
                    win32clipboard.OpenClipboard()
                    try:
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardText(
                            old_clipboard, win32clipboard.CF_UNICODETEXT
                        )
                    finally:
                        win32clipboard.CloseClipboard()
            except Exception as e:
                log(
                    f"Erreur lors de la restauration du presse-papiers: {e}",
                    logging.DEBUG,
                )
        
        except Exception as e:
            log(
                f"Erreur générale lors de la récupération du texte sélectionné: {e}",
                logging.DEBUG,
            )
            selected_text = ""
        
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
    
    def _handle_menu_action(self, prompt_id):
        """Handle a menu action"""
        # Get the selected text
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
            self.response_window.show()
        
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
                self.response_window.show()
                
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
            self.response_window.show()
            
            # Lancer la requête API en arrière-plan
            self.api_client.send_request(custom_prompt, selected_text)
    
    def _handle_screenshot_action(self):
        """Gérer l'action de capture d'écran"""
        log("Démarrage de la capture d'écran...", logging.DEBUG)
        
        # Cacher temporairement le menu contextuel
        QApplication.processEvents()
        
        # Capturer l'écran
        screenshot_path = capture_screen()
        
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
                    
                    # Préparer la fenêtre de réponse
                    self.response_window.set_status("Traitement de la capture d'écran...")
                    # Définir la position de déclenchement à la position du curseur
                    self.response_window.set_trigger_position(cursor_pos)
                    self.response_window.show()
                    
                    # Lancer la requête API en arrière-plan
                    self.api_client.send_request(prompt, screenshot_path)
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
                    
                    # Afficher un message d'attente
                    QApplication.setOverrideCursor(Qt.WaitCursor)
                    
                    try:
                        # Effectuer la requête de manière synchrone
                        response = temp_client.send_request_sync(full_prompt, "")
                        
                        # Coller directement la réponse
                        text_inserter = TextInserter()
                        text_inserter.insert_text(response)
                        
                        log("Réponse insérée avec succès", logging.INFO)
                    except Exception as e:
                        log(f"Erreur lors de la requête API: {e}", logging.ERROR)
                        SafeDialogs.show_critical(
                            "Erreur de traitement",
                            f"Une erreur s'est produite lors du traitement de la réponse : {str(e)}"
                        )
                    finally:
                        # Restaurer le curseur
                        QApplication.restoreOverrideCursor()
            
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
                        # Afficher un message d'attente
                        QApplication.setOverrideCursor(Qt.WaitCursor)
                        
                        try:
                            # Effectuer la requête de manière synchrone
                            response = temp_client.send_request_sync(full_prompt, "")
                            
                            # Coller directement la réponse
                            text_inserter = TextInserter()
                            text_inserter.insert_text(response)

                            log("Réponse insérée avec succès", logging.INFO)
                        except Exception as e:
                            log(f"Erreur lors de la requête API: {e}", logging.ERROR)
                            SafeDialogs.show_critical(
                                "Erreur de traitement",
                                f"Une erreur s'est produite lors du traitement de la réponse : {str(e)}"
                            )
                        finally:
                            # Restaurer le curseur
                            QApplication.restoreOverrideCursor()
                    else:
                        # Préparer la fenêtre de réponse
                        self.response_window.set_status(status)
                        # Définir la position de déclenchement à la position actuelle du curseur
                        self.response_window.set_trigger_position(QCursor.pos())
                        self.response_window.show()
                        
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
                    self.response_window.show()
                    
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
            if screenshot_path and os.path.exists(screenshot_path):
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

    def _handle_settings_action(self):
        """Gérer l'action de paramètres"""
        # Ouvrir la fenêtre de paramètres
        from src.ui.settings_window import SettingsWindow
        settings_window = SettingsWindow(self.settings)
        settings_window.show()

    def update_client_config(self):
        """Met à jour la configuration du client API avec les paramètres actuels."""
        if self.api_client:
            # Recréer le client avec les nouveaux paramètres
            self.api_client = OpenAIClient(
                settings=self.settings,
                api_key=self.settings.get_api_key(),
                model=self.settings.get_model()
            )
            
            # Reconnecter les signaux
            self.api_client.request_started.connect(self.on_request_started)
            self.api_client.request_finished.connect(self.on_request_finished)
            self.api_client.request_error.connect(self.on_request_error)
            
            # Définir le modèle actuel (seulement si on n'utilise pas d'endpoint personnalisé)
            if not self.settings.get_use_custom_endpoint():
                self.api_client.set_model(self.settings.get_model())
                
            endpoint_info = self.settings.get_custom_endpoint() if self.settings.get_use_custom_endpoint() else "OpenAI"
            model_info = self.settings.get_custom_model() if self.settings.get_use_custom_endpoint() else self.settings.get_model()
            
            log(
                f"ContextMenuManager: Configuration du client API mise à jour. Endpoint: {endpoint_info}, Modèle: {model_info}",
                logging.INFO,
            )
