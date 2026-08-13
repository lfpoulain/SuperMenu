"""Windows composition for the shared response window."""

import logging

import win32con
import win32gui
from PySide6.QtWidgets import QApplication

from supermenu_core.ui.response_window import BaseResponseWindow
from src.utils.text_inserter import TextInserter


class _WindowsInsertionAdapter:
    def __init__(self):
        self._inserter = TextInserter()

    def insert_text_async(self, text, target, callback):
        success = self._inserter.insert_text(text, target=target)
        callback(success, "" if success else "target_changed")


class ResponseWindow(BaseResponseWindow):
    def _prepare_presentation(self):
        QApplication.processEvents()

    def _raise_to_front(self):
        self._raise_to_front_qt()
        self._reinforce_foreground_win32()

    def _reinforce_foreground_win32(self):
        """Complement Qt presentation without making it depend on Win32."""
        try:
            hwnd = int(self.winId())
            if not hwnd or not win32gui.IsWindow(hwnd):
                return

            flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0,
                0,
                0,
                0,
                flags,
            )
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        except Exception as exc:
            logging.warning(
                "Impossible de forcer la fenêtre de réponse au premier plan: %s",
                exc,
            )

    def _create_text_inserter(self):
        return _WindowsInsertionAdapter()
