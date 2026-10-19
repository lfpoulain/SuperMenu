#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Context manager pour une gestion robuste du presse-papiers Windows.
"""
import win32clipboard
import win32con
import logging
from dataclasses import dataclass
from PySide6.QtCore import QByteArray, QMimeData, QThread
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from src.utils.logger import log


# Qt exposes CF_DIB, CF_DIBV5 and PNG under this MIME type. Its value is a
# QImage that QMimeData.data() cannot turn into bytes, so it is cloned through
# imageData() instead of being restored as an empty, unusable image.
_QT_IMAGE_MIME = "application/x-qt-image"

# Registered formats read by the Windows clipboard history, the cloud clipboard
# and third-party clipboard monitors. A DWORD 0 opts the content out.
_DWORD_ZERO = b"\x00\x00\x00\x00"
_HISTORY_EXCLUSION_FORMATS = (
    ("CanIncludeInClipboardHistory", _DWORD_ZERO),
    ("CanUploadToCloudClipboard", _DWORD_ZERO),
)
_TRANSIENT_EXCLUSION_FORMATS = (
    ("ExcludeClipboardContentFromMonitorProcessing", _DWORD_ZERO),
    *_HISTORY_EXCLUSION_FORMATS,
)


@dataclass
class ClipboardSnapshot:
    formats: dict[str, bytes]
    image: QImage | None = None

    def restore(self):
        app = QApplication.instance()
        if app is None or QThread.currentThread() is not app.thread():
            return False

        mime_data = QMimeData()
        for mime_format, data in self.formats.items():
            mime_data.setData(mime_format, QByteArray(data))
        if self.image is not None and not self.image.isNull():
            mime_data.setImageData(self.image)
        # The user's content goes back exactly as captured: it returns to the
        # top of the Win+V history and of the cloud clipboard as before, and
        # any exclusion set by its source (a password manager) is kept. Only
        # SuperMenu's own transient writes are excluded (set_text).
        app.clipboard().setMimeData(mime_data)
        return True


class ClipboardManager:
    """Context manager pour gérer le presse-papiers de manière sûre."""

    def __init__(self, max_retries=3):
        """
        Initialise le gestionnaire de presse-papiers.

        Args:
            max_retries (int): Nombre maximum de tentatives d'ouverture du presse-papiers
        """
        self.max_retries = max_retries
        self.clipboard_opened = False

    def __enter__(self):
        """Ouvre le presse-papiers avec gestion des erreurs et retry."""
        for attempt in range(self.max_retries):
            try:
                win32clipboard.OpenClipboard()
                self.clipboard_opened = True
                return self
            except Exception as e:
                if attempt == self.max_retries - 1:
                    log(f"Failed to open clipboard after {self.max_retries} attempts: {e}", logging.ERROR)
                    raise
                # Petit délai avant la prochaine tentative
                import time
                time.sleep(0.1)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ferme le presse-papiers de manière sûre."""
        if self.clipboard_opened:
            try:
                win32clipboard.CloseClipboard()
                self.clipboard_opened = False
            except Exception as e:
                log(f"Error closing clipboard: {e}", logging.WARNING)
        # Ne pas supprimer l'exception si elle existe
        return False

    def get_text(self):
        """
        Récupère le texte du presse-papiers.

        Returns:
            str or None: Le texte du presse-papiers ou None si indisponible
        """
        if not self.clipboard_opened:
            raise RuntimeError("Clipboard not opened. Use 'with ClipboardManager() as cm:' pattern.")

        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return None
        except Exception as e:
            log(f"Error getting clipboard text: {e}", logging.WARNING)
            return None

    def set_text(self, text, transient=False):
        """
        Définit le texte du presse-papiers.

        Args:
            text (str): Le texte à copier dans le presse-papiers
            transient (bool): Écriture interne et temporaire (marqueur,
                texte à coller) à exclure de l'historique Windows, du
                presse-papiers cloud et des gestionnaires de presse-papiers
        """
        if not self.clipboard_opened:
            raise RuntimeError("Clipboard not opened. Use 'with ClipboardManager() as cm:' pattern.")

        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
        except Exception as e:
            log(f"Error setting clipboard text: {e}", logging.ERROR)
            raise
        if transient:
            self._exclude_from_history(_TRANSIENT_EXCLUSION_FORMATS)

    @staticmethod
    def _exclude_from_history(formats):
        """Best effort: the text itself is already on the clipboard."""
        for format_name, value in formats:
            try:
                win32clipboard.SetClipboardData(
                    win32clipboard.RegisterClipboardFormat(format_name), value
                )
            except Exception as e:
                log(f"Clipboard history exclusion unavailable ({format_name}): {e}", logging.DEBUG)

    @staticmethod
    def get_clipboard_text_safe():
        """
        Méthode statique pour récupérer rapidement le texte du presse-papiers.

        Returns:
            str or None: Le texte du presse-papiers ou None en cas d'erreur
        """
        try:
            with ClipboardManager() as cm:
                return cm.get_text()
        except Exception as e:
            log(f"Error in get_clipboard_text_safe: {e}", logging.ERROR)
            return None

    @staticmethod
    def set_clipboard_text_safe(text, transient=False):
        """
        Méthode statique pour définir rapidement le texte du presse-papiers.

        Args:
            text (str): Le texte à copier
            transient (bool): Exclure cette écriture interne de l'historique
                et du presse-papiers cloud Windows

        Returns:
            bool: True si succès, False sinon
        """
        try:
            with ClipboardManager() as cm:
                cm.set_text(text, transient=transient)
                return True
        except Exception as e:
            log(f"Error in set_clipboard_text_safe: {e}", logging.ERROR)
            return False

    @staticmethod
    def capture_snapshot():
        """Clone every format advertised by the Qt Windows clipboard, images included."""
        app = QApplication.instance()
        if app is None or QThread.currentThread() is not app.thread():
            return ClipboardSnapshot({})

        mime_data = app.clipboard().mimeData()
        if mime_data is None:
            return ClipboardSnapshot({})

        image = None
        if mime_data.hasImage():
            image_data = mime_data.imageData()
            if isinstance(image_data, QImage) and not image_data.isNull():
                image = QImage(image_data)

        formats = {}
        for mime_format in mime_data.formats():
            if mime_format == _QT_IMAGE_MIME and image is not None:
                continue
            data = bytes(mime_data.data(mime_format))
            if mime_format == _QT_IMAGE_MIME and not data:
                # Restoring it would advertise an image no application can read.
                continue
            formats[mime_format] = data
        return ClipboardSnapshot(formats, image)

    @staticmethod
    def restore_if_unchanged(snapshot, expected_text):
        """Do not overwrite clipboard changes made by the user meanwhile."""
        if snapshot is None:
            return False
        if ClipboardManager.get_clipboard_text_safe() != expected_text:
            return False
        return snapshot.restore()
