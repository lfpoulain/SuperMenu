#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Indicateur de chargement thread-safe pour les opérations longues.
"""
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QProgressBar
from PySide6.QtCore import Qt, QTimer, QMetaObject, QObject, Signal
from PySide6.QtGui import QMovie
import logging
from utils.logger import log


class LoadingIndicator(QDialog):
    """Dialogue de chargement avec animation."""
    
    def __init__(self, message="Traitement en cours...", parent=None):
        super().__init__(parent)
        self.setWindowTitle("SuperMenu")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setModal(False)  # Non-bloquant
        self.setFixedSize(300, 100)
        
        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Message
        self.label = QLabel(message)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        
        # Barre de progression indéterminée
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Mode indéterminé
        layout.addWidget(self.progress)
        
        self.setLayout(layout)
        
        # Timer pour auto-fermeture (sécurité)
        self.auto_close_timer = QTimer()
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.timeout.connect(self.force_close)
    
    def show_for(self, duration_ms, max_duration_ms=30000):
        """
        Affiche l'indicateur pour une durée limitée.
        
        Args:
            duration_ms (int): Durée d'affichage en millisecondes
            max_duration_ms (int): Durée maximale de sécurité (30s par défaut)
        """
        self.show()
        self.raise_()
        self.activateWindow()
        
        # Timer principal
        QTimer.singleShot(duration_ms, self.close)
        
        # Timer de sécurité (fermeture forcée)
        self.auto_close_timer.start(max_duration_ms)
    
    def force_close(self):
        """Ferme de force l'indicateur (sécurité)."""
        log("LoadingIndicator auto-closed after timeout", logging.WARNING)
        self.close()
    
    def update_message(self, message):
        """Met à jour le message affiché."""
        self.label.setText(message)
    
    def closeEvent(self, event):
        """Nettoyage lors de la fermeture."""
        self.auto_close_timer.stop()
        super().closeEvent(event)


class LoadingIndicatorManager(QObject):
    """Gestionnaire thread-safe pour LoadingIndicator."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Retourne l'instance singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        super().__init__()
        self.current_indicator = None
    
    @staticmethod
    def show(message="Traitement en cours...", duration_ms=5000):
        """
        Affiche un indicateur de chargement de manière thread-safe.
        
        Args:
            message (str): Message à afficher
            duration_ms (int): Durée d'affichage en ms
        """
        instance = LoadingIndicatorManager.get_instance()
        QMetaObject.invokeMethod(
            instance, 
            "_show_impl", 
            Qt.QueuedConnection,
            Q_ARG(str, message),
            Q_ARG(int, duration_ms)
        )
    
    @staticmethod
    def close():
        """Ferme l'indicateur actuel de manière thread-safe."""
        instance = LoadingIndicatorManager.get_instance()
        QMetaObject.invokeMethod(
            instance,
            "_close_impl",
            Qt.QueuedConnection
        )
    
    @staticmethod
    def update_message(message):
        """Met à jour le message de l'indicateur actuel."""
        instance = LoadingIndicatorManager.get_instance()
        QMetaObject.invokeMethod(
            instance,
            "_update_message_impl",
            Qt.QueuedConnection,
            Q_ARG(str, message)
        )
    
    def _show_impl(self, message, duration_ms):
        """Implémentation réelle de show dans le thread Qt."""
        try:
            # Fermer l'indicateur précédent si existant
            if self.current_indicator:
                self.current_indicator.close()
            
            # Créer et afficher le nouveau
            self.current_indicator = LoadingIndicator(message)
            self.current_indicator.show_for(duration_ms)
        except Exception as e:
            log(f"Error showing loading indicator: {e}", logging.ERROR)
    
    def _close_impl(self):
        """Implémentation réelle de close dans le thread Qt."""
        try:
            if self.current_indicator:
                self.current_indicator.close()
                self.current_indicator = None
        except Exception as e:
            log(f"Error closing loading indicator: {e}", logging.ERROR)
    
    def _update_message_impl(self, message):
        """Implémentation réelle de update_message dans le thread Qt."""
        try:
            if self.current_indicator:
                self.current_indicator.update_message(message)
        except Exception as e:
            log(f"Error updating loading indicator: {e}", logging.ERROR)


# Import nécessaire pour Q_ARG
from PySide6.QtCore import Q_ARG
