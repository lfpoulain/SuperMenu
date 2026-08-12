"""Qt clipboard helpers used by selection and safe insertion flows."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QMimeData, QThread
from PySide6.QtWidgets import QApplication


@dataclass
class ClipboardSnapshot:
    formats: dict[str, bytes]

    def restore(self) -> bool:
        app = QApplication.instance()
        if app is None or QThread.currentThread() is not app.thread():
            return False
        mime_data = QMimeData()
        for mime_format, data in self.formats.items():
            mime_data.setData(mime_format, QByteArray(data))
        app.clipboard().setMimeData(mime_data)
        return True


class ClipboardManager:
    @staticmethod
    def get_clipboard_text_safe() -> str:
        app = QApplication.instance()
        if app is None or QThread.currentThread() is not app.thread():
            return ""
        return app.clipboard().text() or ""

    @staticmethod
    def set_clipboard_text_safe(text: str) -> bool:
        app = QApplication.instance()
        if app is None or QThread.currentThread() is not app.thread():
            return False
        app.clipboard().setText(str(text))
        return True

    @staticmethod
    def capture_snapshot() -> ClipboardSnapshot:
        app = QApplication.instance()
        if app is None or QThread.currentThread() is not app.thread():
            return ClipboardSnapshot({})
        mime_data = app.clipboard().mimeData()
        return ClipboardSnapshot(
            {
                mime_format: bytes(mime_data.data(mime_format))
                for mime_format in mime_data.formats()
            }
        )

    @staticmethod
    def restore_if_unchanged(
        snapshot: ClipboardSnapshot | None,
        expected_text: str,
    ) -> bool:
        if snapshot is None:
            return False
        if ClipboardManager.get_clipboard_text_safe() != expected_text:
            return False
        return snapshot.restore()
