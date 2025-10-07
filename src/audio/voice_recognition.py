#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module principal pour la reconnaissance vocale dans SuperMenu.
"""
import os
import threading
import time
import logging
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QTimer, Signal
from utils.logger import log
from utils.safe_dialogs import SafeDialogs
from audio.audio_recorder import AudioRecorder
from audio.transcription import Transcriber
from audio.text_inserter import TextInserter
from audio.audio_config import (
    VOICE_RECOGNITION_DIALOG_WIDTH,
    VOICE_RECOGNITION_DIALOG_TITLE,
    VOICE_RECOGNITION_DIALOG_MESSAGE,
    VOICE_RECOGNITION_STOP_BUTTON_TEXT
)

class RecordingDialog(QDialog):
    """Dialogue non-bloquant pour l'enregistrement vocal."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(VOICE_RECOGNITION_DIALOG_TITLE)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Window)
        self.setMinimumWidth(VOICE_RECOGNITION_DIALOG_WIDTH)
        self.setModal(False)  # Non-bloquant
        
        # Layout
        layout = QVBoxLayout()
        
        # Message
        self.message = QLabel(VOICE_RECOGNITION_DIALOG_MESSAGE)
        self.message.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message)
        
        # Bouton stop
        stop_button = QPushButton(VOICE_RECOGNITION_STOP_BUTTON_TEXT)
        stop_button.clicked.connect(self.accept)
        layout.addWidget(stop_button)
        
        self.setLayout(layout)
        
        # Timer de sécurité (30 secondes max)
        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self._on_timeout)
    
    def showEvent(self, event):
        """Démarre le timer de timeout."""
        super().showEvent(event)
        self.timeout_timer.start(30000)  # 30 secondes
    
    def _on_timeout(self):
        """Timeout de l'enregistrement."""
        log("Recording dialog timeout after 30 seconds", logging.WARNING)
        self.reject()
    
    def closeEvent(self, event):
        """Arrête le timer."""
        self.timeout_timer.stop()
        super().closeEvent(event)


class VoiceRecognition:
    """Classe principale pour la reconnaissance vocale."""
    
    def __init__(self, api_key=None, microphone_index=None, callback=None):
        """
        Initialise le module de reconnaissance vocale.
        
        Args:
            api_key (str, optional): Clé API OpenAI à utiliser
            microphone_index (int, optional): Index du microphone à utiliser
            callback (function, optional): Fonction de rappel à appeler avec le texte transcrit
        """
        self.api_key = api_key
        self.microphone_index = microphone_index
        self.callback = callback
        self.recorder = AudioRecorder(input_device_index=microphone_index)
        self.transcriber = Transcriber(api_key=api_key)
        self.text_inserter = TextInserter()
        self.is_recording = False
        self.recording_file = None
        
        log("Module de reconnaissance vocale initialisé")
        
    @staticmethod
    def list_microphones():
        """
        Liste tous les microphones disponibles.
        
        Returns:
            list: Liste de tuples (index, nom) pour chaque microphone
        """
        return AudioRecorder.list_microphones()
    
    def start_voice_recognition(self, insert_text=True):
        """
        Démarre le processus de reconnaissance vocale.
        
        Args:
            insert_text (bool): Si True, insère le texte transcrit, sinon retourne le texte
            
        Returns:
            bool or str: True si le processus a démarré avec succès (et insert_text=True), 
                         le texte transcrit si insert_text=False, False en cas d'erreur
        """
        if self.is_recording:
            log("Une session d'enregistrement est déjà en cours")
            return False
        
        try:
            # Afficher un message indiquant que l'enregistrement a commencé
            QApplication.instance().beep()
            log("Début de l'enregistrement vocal...")
            
            # Démarrer l'enregistrement
            self.is_recording = True
            self.recording_file = self.recorder.start_recording()
            
            if not self.recording_file:
                log("Échec du démarrage de l'enregistrement", level=logging.ERROR)
                self.is_recording = False
                SafeDialogs.show_critical("Erreur de reconnaissance vocale", "Échec du démarrage de l'enregistrement")
                return False
            
            # Créer et afficher la boîte de dialogue d'enregistrement (NON-BLOQUANTE)
            dialog = RecordingDialog()
            
            # Connecter le signal de fermeture pour traiter l'audio
            dialog.finished.connect(lambda: self._process_recording(dialog, insert_text))
            
            # Afficher de manière non-bloquante
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            
            return True  # Retour immédiat, traitement asynchrone
            
        except Exception as e:
            log(f"Erreur lors de la reconnaissance vocale: {e}", level=logging.ERROR)
            self.is_recording = False
            SafeDialogs.show_critical("Erreur de reconnaissance vocale", f"Erreur lors de la reconnaissance vocale: {e}")
            return False
    
    def _process_recording(self, dialog, insert_text):
        """
        Traite l'enregistrement après fermeture du dialogue (asynchrone).
        
        Args:
            dialog: Le dialogue d'enregistrement
            insert_text (bool): Si True, insère le texte, sinon appelle le callback
        """
        try:
            # Arrêter l'enregistrement
            audio_file = self.recorder.stop_recording()
            self.is_recording = False
            
            if not audio_file or not os.path.exists(audio_file):
                log("Aucun fichier audio enregistré", level=logging.ERROR)
                SafeDialogs.show_critical("Erreur de reconnaissance vocale", "Aucun fichier audio n'a été enregistré")
                return
            
            # Afficher un indicateur de chargement pendant la transcription
            from utils.loading_indicator import LoadingIndicatorManager
            LoadingIndicatorManager.show("Transcription en cours...", 30000)
            
            # Transcrire l'audio dans un thread séparé pour ne pas bloquer
            threading.Thread(
                target=self._transcribe_and_process,
                args=(audio_file, insert_text),
                daemon=True
            ).start()
            
        except Exception as e:
            log(f"Erreur dans _process_recording: {e}", level=logging.ERROR)
            SafeDialogs.show_critical("Erreur", f"Erreur: {str(e)}")
            self.is_recording = False
    
    def _transcribe_and_process(self, audio_file, insert_text):
        """
        Transcrit et traite l'audio (exécuté dans un thread).
        
        Args:
            audio_file (str): Chemin du fichier audio
            insert_text (bool): Si True, insère le texte
        """
        try:
            # Transcrire l'audio
            log("Transcription de l'audio en cours...")
            text = self.transcriber.transcribe(audio_file)
            
            # Fermer l'indicateur de chargement
            from utils.loading_indicator import LoadingIndicatorManager
            LoadingIndicatorManager.close()
            
            if not text:
                log("Échec de la transcription", level=logging.ERROR)
                SafeDialogs.show_critical("Erreur de reconnaissance vocale", "Échec de la transcription audio")
                return
            
            # Supprimer le fichier audio temporaire
            try:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                    log(f"Fichier audio temporaire supprimé: {audio_file}")
            except Exception as e:
                log(f"Erreur lors de la suppression du fichier audio temporaire: {e}")
            
            # Si nous avons une fonction de rappel, l'appeler avec le texte
            if self.callback and callable(self.callback):
                self.callback(text)
                return
            
            # Sinon, insérer le texte ou le retourner selon le paramètre
            if insert_text:
                log(f"Insertion du texte transcrit: {text[:50]}{'...' if len(text) > 50 else ''}")
                self.text_inserter.insert_text(text)
            
        except Exception as e:
            LoadingIndicatorManager.close()
            log(f"Erreur dans _transcribe_and_process: {e}", level=logging.ERROR)
            SafeDialogs.show_critical("Erreur", f"Erreur: {str(e)}")
    
    def describe_voice_response(self, text):
        """
        Méthode pour la description de la réponse vocale.
        
        Args:
            text (str): Texte à décrire
            
        Returns:
            str: Description de la réponse vocale
        """
        # Ici, vous pouvez ajouter votre logique pour décrire la réponse vocale
        # Par exemple, vous pouvez utiliser une bibliothèque de traitement de langage naturel pour analyser le texte
        # et générer une description basée sur le contenu du texte
        description = f"La réponse vocale est : {text}"
        return description
    
    def cleanup(self):
        """Nettoie les ressources."""
        if self.is_recording:
            self.recorder.stop_recording()
            self.is_recording = False
        
        if self.recorder:
            self.recorder.cleanup()
        
        log("Ressources de reconnaissance vocale nettoyées")
