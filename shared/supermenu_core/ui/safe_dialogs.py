#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilitaires pour afficher des dialogues Qt de manière thread-safe.
"""

from PySide6.QtCore import QMetaObject, Qt, QObject, Q_ARG, Slot
from PySide6.QtWidgets import QMessageBox, QApplication
import itertools
import logging

logger = logging.getLogger("SuperMenu.core")

# Server errors can embed a whole HTML page; keep the box readable.
MAX_MESSAGE_LENGTH = 2000


def dialog_text(message):
    """Return the message as shown in a box, shortened when it is too long."""
    text = str(message)
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH].rstrip() + "…"
    return text


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
        # Callbacks cannot cross invokeMethod: they wait here under a token.
        self._close_callbacks = {}
        self._callback_tokens = itertools.count(1)
        # S'assurer qu'on est dans le thread principal
        app = QApplication.instance()
        if app:
            self.moveToThread(app.thread())

    @staticmethod
    def show_information(title, message, parent=None, on_closed=None):
        """
        Affiche une boîte d'information de manière thread-safe.

        Args:
            title (str): Titre de la boîte
            message (str): Message à afficher
            parent: Widget parent (optionnel)
            on_closed: appelé dans le thread Qt à la fermeture (optionnel)
        """
        SafeDialogs._request("information", title, message, on_closed)

    @staticmethod
    def show_warning(title, message, parent=None, on_closed=None):
        """
        Affiche une boîte d'avertissement de manière thread-safe.

        Args:
            title (str): Titre de la boîte
            message (str): Message à afficher
            parent: Widget parent (optionnel)
            on_closed: appelé dans le thread Qt à la fermeture (optionnel)
        """
        SafeDialogs._request("warning", title, message, on_closed)

    @staticmethod
    def show_critical(title, message, parent=None, on_closed=None):
        """
        Affiche une boîte d'erreur de manière thread-safe.

        Args:
            title (str): Titre de la boîte
            message (str): Message à afficher
            parent: Widget parent (optionnel)
            on_closed: appelé dans le thread Qt à la fermeture (optionnel)
        """
        SafeDialogs._request("critical", title, message, on_closed)

    @staticmethod
    def _request(kind, title, message, on_closed):
        instance = SafeDialogs.get_instance()
        if on_closed is None:
            QMetaObject.invokeMethod(
                instance,
                f"_show_{kind}_impl",
                Qt.QueuedConnection,
                Q_ARG(str, title),
                Q_ARG(str, message),
            )
            return
        token = str(next(instance._callback_tokens))
        instance._close_callbacks[token] = on_closed
        QMetaObject.invokeMethod(
            instance,
            "_show_with_callback_impl",
            Qt.QueuedConnection,
            Q_ARG(str, kind),
            Q_ARG(str, title),
            Q_ARG(str, message),
            Q_ARG(str, token),
        )

    def _present(self, icon, title, message, on_closed=None):
        """Show a parentless, non-blocking box the user can always reach.

        The static QMessageBox helpers open a modal dialog and spin their own
        event loop. On macOS SuperMenu runs as an LSUIElement agent with no
        Dock icon, and these dialogs fire exactly when another application is
        in front -- so a box that lands behind it cannot be raised by the user
        at all. Showing it non-modally, above other windows, keeps it reachable
        and keeps the caller's event loop free.

        Messages often relay a server's raw answer. Plain text keeps an HTML
        error page from rendering formatted content or clickable links.
        """
        try:
            box = QMessageBox(icon, title, "")
            box.setTextFormat(Qt.TextFormat.PlainText)
            box.setText(dialog_text(message))
            box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            box.setAttribute(Qt.WA_DeleteOnClose, True)
            box.setModal(False)
            self._open_dialogs.append(box)
            box.finished.connect(lambda _result: self._forget(box))
            if on_closed is not None:
                box.finished.connect(lambda _result: self._run_callback(on_closed))
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

    @staticmethod
    def _run_callback(callback):
        try:
            callback()
        except Exception:
            logger.exception("Error after closing a dialog")

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

    @Slot(str, str, str, str)
    def _show_with_callback_impl(self, kind, title, message, token):
        """Boîte dont la fermeture appelle le rappel conservé sous ``token``."""
        icon = {
            "information": QMessageBox.Icon.Information,
            "warning": QMessageBox.Icon.Warning,
        }.get(kind, QMessageBox.Icon.Critical)
        self._present(icon, title, message, self._close_callbacks.pop(token, None))
