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
from PySide6.QtGui import QFont
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
    
    # Signal émis quand l'utilisateur arrête l'enregistrement
    recording_stopped = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle(VOICE_RECOGNITION_DIALOG_TITLE)
        self.setWindowFlags(
            Qt.Window | 
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint
        )
        self.setModal(False)  # Non-bloquant !
        self.setMinimumWidth(VOICE_RECOGNITION_DIALOG_WIDTH)
        
        # Style moderne
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                border: 2px solid #e74c3c;
                border-radius: 10px;
            }
            QLabel {
                color: #ffffff;
                background-color: transparent;
                padding: 15px;
                font-size: 11pt;
            }
            QPushButton {
                background-color: #e74c3c;
                color: #ffffff;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """)
        
        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Icône/Indicateur d'enregistrement
        self.recording_label = QLabel("🎙️ Enregistrement en cours...")
        self.recording_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.recording_label.setFont(font)
        layout.addWidget(self.recording_label)
        
        # Message
        message = QLabel(VOICE_RECOGNITION_DIALOG_MESSAGE)
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        layout.addWidget(message)
        
        # Bouton stop
        stop_button = QPushButton(VOICE_RECOGNITION_STOP_BUTTON_TEXT)
        stop_button.setCursor(Qt.PointingHandCursor)
        stop_button.clicked.connect(self._on_stop_clicked)
        layout.addWidget(stop_button)
        
        self.setLayout(layout)
        
        # Timer pour l'animation du point
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate_recording)
        self.dot_count = 0
        
    def showEvent(self, event):
        """Démarrer l'animation quand le dialogue s'affiche."""
        super().showEvent(event)
        self.animation_timer.start(500)  # Animation toutes les 500ms
        
        # Centrer sur l'écran
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2
        )
    
    def closeEvent(self, event):
        """Arrêter l'animation à la fermeture."""
        self.animation_timer.stop()
        super().closeEvent(event)
    
    def _animate_recording(self):
        """Anime l'indicateur d'enregistrement."""
        dots = "." * (self.dot_count % 4)
        self.recording_label.setText(f"🎙️ Enregistrement en cours{dots}")
        self.dot_count += 1
    
    def _on_stop_clicked(self):
        """Gère le clic sur le bouton stop."""
        self.recording_stopped.emit()
        self.close()

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
        Démarre le processus de reconnaissance vocale de manière non-bloquante.
        
        Args:
            insert_text (bool): Si True, insère le texte transcrit, sinon retourne le texte
            
        Returns:
            bool: True si le processus a démarré avec succès, False en cas d'erreur
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
            
            # Créer et afficher le dialogue non-bloquant
            self.recording_dialog = RecordingDialog()
            self.recording_dialog.recording_stopped.connect(
                lambda: self._finish_recording(insert_text)
            )
            self.recording_dialog.show()
            
            return True
            
        except Exception as e:
            log(f"Erreur lors de la reconnaissance vocale: {e}", level=logging.ERROR)
            self.is_recording = False
            SafeDialogs.show_critical("Erreur de reconnaissance vocale", f"Erreur lors de la reconnaissance vocale: {e}")
            return False
    
    def _finish_recording(self, insert_text=True):
        """
        Termine l'enregistrement et traite l'audio dans un thread séparé.
        
        Args:
            insert_text (bool): Si True, insère le texte transcrit
        """
        # Arrêter l'enregistrement
        audio_file = self.recorder.stop_recording()
        self.is_recording = False
        
        if not audio_file or not os.path.exists(audio_file):
            log("Aucun fichier audio enregistré", level=logging.ERROR)
            SafeDialogs.show_critical("Erreur de reconnaissance vocale", "Aucun fichier audio n'a été enregistré")
            return
        
        # Afficher un indicateur de traitement
        from utils.loading_indicator import SimpleLoadingIndicator
        self.processing_indicator = SimpleLoadingIndicator.show_simple("🎤 Transcription en cours...")
        
        # Traiter l'audio dans un thread séparé pour ne pas bloquer l'UI
        def process_audio():
            try:
                # Transcrire l'audio
                log("Transcription de l'audio en cours...")
                text = self.transcriber.transcribe(audio_file)
                
                # Supprimer le fichier audio temporaire
                try:
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                        log(f"Fichier audio temporaire supprimé: {audio_file}")
                except Exception as e:
                    log(f"Erreur lors de la suppression du fichier audio temporaire: {e}")
                
                # Fermer l'indicateur de traitement dans le thread Qt
                QTimer.singleShot(0, self.processing_indicator.close)
                
                if not text:
                    log("Échec de la transcription", level=logging.ERROR)
                    SafeDialogs.show_critical("Erreur de reconnaissance vocale", "Échec de la transcription audio")
                    return
                
                # Si nous avons une fonction de rappel, l'appeler avec le texte
                if self.callback and callable(self.callback):
                    # Exécuter le callback dans le thread Qt principal
                    from PySide6.QtCore import QMetaObject, Qt
                    QMetaObject.invokeMethod(
                        QApplication.instance(),
                        lambda: self.callback(text),
                        Qt.QueuedConnection
                    )
                    return
                
                # Sinon, insérer le texte selon le paramètre
                if insert_text:
                    log(f"Insertion du texte transcrit: {text[:50]}{'...' if len(text) > 50 else ''}")
                    self.text_inserter.insert_text(text)
                else:
                    # Retourner le texte n'est pas possible en mode async
                    # Utiliser un callback à la place
                    log(f"Texte transcrit: {text}")
                    
            except Exception as e:
                log(f"Erreur lors du traitement de l'audio: {e}", level=logging.ERROR)
                QTimer.singleShot(0, self.processing_indicator.close)
                SafeDialogs.show_critical("Erreur de traitement", f"Erreur lors du traitement de l'audio: {e}")
        
        # Lancer le traitement dans un thread
        thread = threading.Thread(target=process_audio, daemon=True)
        thread.start()
    
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
