"""Insert text back into a previously captured macOS application."""

from __future__ import annotations

import time

from pynput.keyboard import Controller, Key

from src.utils.clipboard_manager import ClipboardManager
from src.utils.logger import log


CLIPBOARD_COPY_DELAY = 0.12
CLIPBOARD_PASTE_DELAY = 0.25
CLIPBOARD_RESTORE_DELAY = 0.15


class TextInserter:
    def __init__(self):
        self.keyboard = Controller()

    def _press_keyboard_shortcut(self, *keys) -> None:
        pressed = []
        try:
            for key in keys:
                self.keyboard.press(key)
                pressed.append(key)
        finally:
            for key in reversed(pressed):
                try:
                    self.keyboard.release(key)
                except Exception:
                    pass

    def insert_text(self, text: str, target=None) -> bool:
        if not text or target is None:
            return False
        if not target.activate_and_verify():
            log("Insertion annulée : l'application cible n'est plus disponible")
            return False

        original_clipboard = ClipboardManager.capture_snapshot()
        try:
            if not ClipboardManager.set_clipboard_text_safe(text):
                return False
            time.sleep(CLIPBOARD_COPY_DELAY)
            if not target.activate_and_verify():
                return False
            self._press_keyboard_shortcut(Key.cmd, "v")
            time.sleep(CLIPBOARD_PASTE_DELAY)
            return True
        finally:
            time.sleep(CLIPBOARD_RESTORE_DELAY)
            ClipboardManager.restore_if_unchanged(original_clipboard, text)
