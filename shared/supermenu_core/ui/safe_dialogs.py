#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilitaires pour afficher des dialogues Qt de manière thread-safe.
"""

from PySide6.QtCore import QMetaObject, Qt, QObject, Q_ARG, Slot
from PySide6.QtWidgets import QMessageBox, QApplication
import logging

logger = logging.getLogger("SuperMenu.core")


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
        # Non-modal boxes are only kept alive by this list until they close.
        self._open_dialogs = []
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
        QMetaObject.invokeMethod(
            instance,
            "_show_information_impl",
            Qt.QueuedConnection,
            Q_ARG(str, title),
            Q_ARG(str, message),
        )

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
        QMetaObject.invokeMethod(
            instance,
            "_show_warning_impl",
            Qt.QueuedConnection,
            Q_ARG(str, title),
            Q_ARG(str, message),
        )

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
        QMetaObject.invokeMethod(
            instance,
            "_show_critical_impl",
            Qt.QueuedConnection,
            Q_ARG(str, title),
            Q_ARG(str, message),
        )

    def _present(self, icon, title, message):
        """Show a parentless, non-blocking box the user can always reach.

        The static QMessageBox helpers open a modal dialog and spin their own
        event loop. On macOS SuperMenu runs as an LSUIElement agent with no
        Dock icon, and these dialogs fire exactly when another application is
        in front -- so a box that lands behind it cannot be raised by the user
        at all. Showing it non-modally, above other windows, keeps it reachable
        and keeps the caller's event loop free.
        """
        try:
            box = QMessageBox(icon, title, str(message))
            box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            box.setAttribute(Qt.WA_DeleteOnClose, True)
            box.setModal(False)
            self._open_dialogs.append(box)
            box.finished.connect(lambda _result: self._forget(box))
            box.show()
            box.raise_()
            box.activateWindow()
        except Exception as e:
            logger.exception("Error showing dialog: %s", e)

    def _forget(self, box):
        try:
            self._open_dialogs.remove(box)
        except ValueError:
            pass

    @Slot(str, str)
    def _show_information_impl(self, title, message):
        """Implémentation réelle de show_information dans le thread Qt"""
        self._present(QMessageBox.Icon.Information, title, message)

    @Slot(str, str)
    def _show_warning_impl(self, title, message):
        """Implémentation réelle de show_warning dans le thread Qt"""
        self._present(QMessageBox.Icon.Warning, title, message)

    @Slot(str, str)
    def _show_critical_impl(self, title, message):
        """Implémentation réelle de show_critical dans le thread Qt"""
        self._present(QMessageBox.Icon.Critical, title, message)
