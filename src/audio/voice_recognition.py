#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module principal pour la reconnaissance vocale dans SuperMenu.
"""
import os
import threading
import time
import logging
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QTimer
from utils.logger import log
from audio.audio_recorder import AudioRecorder
from audio.transcription import Transcriber
from audio.text_inserter import TextInserter
from audio.audio_config import (
    VOICE_RECOGNITION_DIALOG_WIDTH,
    VOICE_RECOGNITION_DIALOG_TITLE,
    VOICE_RECOGNITION_DIALOG_MESSAGE,
    VOICE_RECOGNITION_STOP_BUTTON_TEXT
)

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
                QMessageBox.critical(None, "Erreur de reconnaissance vocale", "Échec du démarrage de l'enregistrement")
                return False
            
            # Créer et afficher la boîte de dialogue d'enregistrement
            dialog = QDialog(None)
            dialog.setWindowTitle(VOICE_RECOGNITION_DIALOG_TITLE)
            dialog.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Window)
            dialog.setMinimumWidth(VOICE_RECOGNITION_DIALOG_WIDTH)
            
            # Créer le layout
            layout = QVBoxLayout()
            
            # Ajouter un message
            message = QLabel(VOICE_RECOGNITION_DIALOG_MESSAGE)
            message.setAlignment(Qt.AlignCenter)
            layout.addWidget(message)
            
            # Ajouter un bouton pour arrêter l'enregistrement
            stop_button = QPushButton(VOICE_RECOGNITION_STOP_BUTTON_TEXT)
            layout.addWidget(stop_button)
            
            # Configurer la boîte de dialogue
            dialog.setLayout(layout)
            
            # Connecter le bouton à l'arrêt de l'enregistrement et à la fermeture de la boîte de dialogue
            stop_button.clicked.connect(dialog.accept)
            
            # Afficher la boîte de dialogue de manière modale
            dialog.exec()
            
            # Arrêter l'enregistrement
            audio_file = self.recorder.stop_recording()
            self.is_recording = False
            
            if not audio_file or not os.path.exists(audio_file):
                log("Aucun fichier audio enregistré", level=logging.ERROR)
                QMessageBox.critical(None, "Erreur de reconnaissance vocale", "Aucun fichier audio n'a été enregistré")
                return False
            
            # Transcrire l'audio
            log("Transcription de l'audio en cours...")
            text = self.transcriber.transcribe(audio_file)
            
            if not text:
                log("Échec de la transcription", level=logging.ERROR)
                QMessageBox.critical(None, "Erreur de reconnaissance vocale", "Échec de la transcription audio")
                return False
            
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
                return True
            
            # Sinon, insérer le texte ou le retourner selon le paramètre
            if insert_text:
                log(f"Insertion du texte transcrit: {text[:50]}{'...' if len(text) > 50 else ''}")
                self.text_inserter.insert_text(text)
                return True
            else:
                return text
            
        except Exception as e:
            log(f"Erreur lors de la reconnaissance vocale: {e}", level=logging.ERROR)
            self.is_recording = False
            try:
                QMessageBox.critical(None, "Erreur de reconnaissance vocale", f"Erreur lors de la reconnaissance vocale: {e}")
            except:
                pass
            return False
    
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
