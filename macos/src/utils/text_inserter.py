"""Insert text back into a previously captured macOS application."""

from __future__ import annotations

from PySide6.QtCore import QTimer

from src.utils.clipboard_manager import ClipboardManager
from src.utils.key_events import KeyEventPoster
from src.utils.logger import log


TARGET_ACTIVATION_DELAY_MS = 180
TARGET_FORCE_ACTIVATION_DELAY_MS = 220
CLIPBOARD_COPY_DELAY_MS = 120
CLIPBOARD_PASTE_DELAY_MS = 400


class TextInserter:
    def __init__(self, *, keys=None, scheduler=None):
        self.keys = keys or KeyEventPoster()
        self._schedule = scheduler or QTimer.singleShot

    def insert_text_async(self, text, target, on_finished) -> None:
        """Insert after macOS has had a main-loop turn to change focus."""
        finished = False
        clipboard_snapshot = None
        clipboard_changed = False

        def finish(success, reason=""):
            nonlocal finished, clipboard_changed
            if finished:
                return
            finished = True
            if clipboard_changed:
                ClipboardManager.restore_if_unchanged(
                    clipboard_snapshot,
                    text,
                )
                clipboard_changed = False
            on_finished(bool(success), str(reason or ""))

        def paste_now():
            if not target.is_current():
                log(
                    "Insertion annulée : une autre application est devenue "
                    "active avant le collage"
                )
                finish(False, "target_changed")
                return
            if not self.keys.paste():
                finish(False, "paste_failed")
                return
            self._schedule(
                CLIPBOARD_PASTE_DELAY_MS,
                lambda: finish(True),
            )

        def paste_after_clipboard_update():
            # A shortcut that is still physically held would otherwise be
            # merged into the synthetic Command+V by the window server.
            self.keys.when_modifiers_released(self._schedule, paste_now)

        def prepare_clipboard():
            nonlocal clipboard_snapshot, clipboard_changed
            if not target.is_current():
                finish(False, "activation_failed")
                return
            clipboard_snapshot = ClipboardManager.capture_snapshot()
            if not ClipboardManager.set_clipboard_text_safe(text):
                finish(False, "clipboard_failed")
                return
            clipboard_changed = True
            self._schedule(
                CLIPBOARD_COPY_DELAY_MS,
                paste_after_clipboard_update,
            )

        def verify_forced_activation():
            if not target.is_current():
                finish(False, "activation_failed")
                return
            prepare_clipboard()

        def verify_cooperative_activation():
            if target.is_current():
                prepare_clipboard()
                return
            if not target.request_activation(force=True):
                finish(False, "target_unavailable")
                return
            self._schedule(
                TARGET_FORCE_ACTIVATION_DELAY_MS,
                verify_forced_activation,
            )

        if not text or target is None:
            finish(False, "missing_target")
            return
        if not target.request_activation():
            finish(False, "target_unavailable")
            return
        self._schedule(
            TARGET_ACTIVATION_DELAY_MS,
            verify_cooperative_activation,
        )
