#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilitaires pour afficher des dialogues Qt de manière thread-safe.
"""
from PySide6.QtCore import QMetaObject, Qt, QObject, Q_ARG, Slot
from PySide6.QtWidgets import QMessageBox, QApplication
import logging
from src.utils.logger import log


class SafeDialogs(QObject):
    """Classe pour afficher des dialogues de manière thread-safe."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Retourne l'instance singleton (lazy initialization)"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        super().__init__()
        # S'assurer qu'on est dans le thread principal
        app = QApplication.instance()
        if app:
            self.moveToThread(app.thread())
    
    @staticmethod
    def show_information(title, message, parent=None):
        """
        Affiche une boîte d'information de manière thread-safe.
        
        Args:
            title (str): Titre de la boîte
            message (str): Message à afficher
            parent: Widget parent (optionnel)
        """
        instance = SafeDialogs.get_instance()
        QMetaObject.invokeMethod(instance, "_show_information_impl", Qt.QueuedConnection,
                               Q_ARG(str, title),
                               Q_ARG(str, message))
    
    @staticmethod
    def show_warning(title, message, parent=None):
        """
        Affiche une boîte d'avertissement de manière thread-safe.
        
        Args:
            title (str): Titre de la boîte
            message (str): Message à afficher
            parent: Widget parent (optionnel)
        """
        instance = SafeDialogs.get_instance()
        QMetaObject.invokeMethod(instance, "_show_warning_impl", Qt.QueuedConnection,
                               Q_ARG(str, title),
                               Q_ARG(str, message))
    
    @staticmethod
    def show_critical(title, message, parent=None):
        """
        Affiche une boîte d'erreur de manière thread-safe.
        
        Args:
            title (str): Titre de la boîte
            message (str): Message à afficher
            parent: Widget parent (optionnel)
        """
        instance = SafeDialogs.get_instance()
        QMetaObject.invokeMethod(instance, "_show_critical_impl", Qt.QueuedConnection,
                               Q_ARG(str, title),
                               Q_ARG(str, message))
    
    @Slot(str, str)
    def _show_information_impl(self, title, message):
        """Implémentation réelle de show_information dans le thread Qt"""
        try:
            QMessageBox.information(None, title, message)
        except Exception as e:
            log(f"Error showing information dialog: {e}", logging.ERROR)
    
    @Slot(str, str)
    def _show_warning_impl(self, title, message):
        """Implémentation réelle de show_warning dans le thread Qt"""
        try:
            QMessageBox.warning(None, title, message)
        except Exception as e:
            log(f"Error showing warning dialog: {e}", logging.ERROR)
    
    @Slot(str, str)
    def _show_critical_impl(self, title, message):
        """Implémentation réelle de show_critical dans le thread Qt"""
        try:
            QMessageBox.critical(None, title, message)
        except Exception as e:
            log(f"Error showing critical dialog: {e}", logging.ERROR)
