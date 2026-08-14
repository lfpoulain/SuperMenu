"""Read the selected text of the frontmost application without blocking.

The previous implementation slept on the Qt main thread while polling
``NSWorkspace.frontmostApplication()``. Those AppKit properties are refreshed
asynchronously through the main run loop, so sleeping on that thread suppressed
the very update the loop was waiting for: activation could be reported as failed
after it had actually succeeded. Every wait here is scheduled instead, which
lets the run loop deliver the workspace notifications.
"""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QTimer

from src.utils.accessibility_text import AccessibilitySelectionReader
from src.utils.clipboard_manager import ClipboardManager
from src.utils.key_events import KeyEventPoster
from src.utils.logger import log, logger


ACTIVATION_POLL_MS = 25
ACTIVATION_MAX_POLLS = 12
# The copy is waited for, not slept through: the target answers in well under
# the old fixed 180 ms most of the time, and the ceiling only costs anything
# when nothing was selected.
COPY_POLL_MS = 15
COPY_MAX_POLLS = 18
RESTORE_DELAY_MS = 100


class SelectionReader:
    """Copy the current selection through a sentinel-guarded clipboard round trip."""

    def __init__(
        self,
        *,
        keys=None,
        scheduler=None,
        clipboard=None,
        accessibility=None,
    ):
        self._keys = keys or KeyEventPoster()
        self._schedule = scheduler or QTimer.singleShot
        self._clipboard = clipboard or ClipboardManager
        self._accessibility = accessibility or AccessibilitySelectionReader()

    def read_async(self, target, on_finished) -> None:
        """Call ``on_finished(text)`` with the selection, or an empty string."""
        finished = False
        snapshot = None
        clipboard_changed = False
        started_ns = time.monotonic_ns()
        phases = []
        sentinel = f"__SUPERMENU_EMPTY_SELECTION_{time.monotonic_ns()}__"

        def mark(label):
            """Record where the delay before the menu actually goes."""
            elapsed_ms = (time.monotonic_ns() - started_ns) // 1_000_000
            phases.append(f"{label} {elapsed_ms} ms")

        def finish(text):
            nonlocal finished
            if finished:
                return
            finished = True
            mark("terminé")
            log("Chronologie de la sélection : " + ", ".join(phases))
            if clipboard_changed:
                expected = text if text else sentinel
                self._schedule(
                    RESTORE_DELAY_MS,
                    lambda: self._clipboard.restore_if_unchanged(snapshot, expected),
                )
            on_finished(text or "")

        def read_clipboard(poll_number=0):
            try:
                text = self._clipboard.get_clipboard_text_safe()
            except Exception:
                logger.exception("Lecture de la sélection impossible")
                finish("")
                return
            if text and text != sentinel:
                log(
                    "Lecture de la sélection terminée : "
                    f"{len(text)} caractère(s) détecté(s)"
                )
                finish(text)
                return
            if poll_number < COPY_MAX_POLLS:
                self._schedule(
                    COPY_POLL_MS,
                    lambda: read_clipboard(poll_number + 1),
                )
                return
            log("Lecture de la sélection terminée : aucun texte sélectionné")
            finish("")

        def send_copy():
            nonlocal snapshot, clipboard_changed
            snapshot = self._clipboard.capture_snapshot()
            if not self._clipboard.set_clipboard_text_safe(sentinel):
                log(
                    "Lecture de la sélection impossible : presse-papiers "
                    "indisponible",
                    logging.WARNING,
                )
                finish("")
                return
            clipboard_changed = True
            if not self._keys.copy():
                finish("")
                return
            mark("copie envoyée")
            self._schedule(COPY_POLL_MS, read_clipboard)

        def await_modifiers():
            # The global shortcut fires on key down, so the user is very likely
            # still holding Cmd and Shift. Copying now would reach the target as
            # Cmd+Shift+C. This wait is the user's own fingers and is usually
            # the largest share of the delay before the menu appears.
            mark("cible active")
            self._keys.when_modifiers_released(
                self._schedule,
                lambda: (mark("modificateurs relâchés"), send_copy()),
            )

        def await_activation(poll_number=0):
            if target.is_current():
                await_modifiers()
                return
            if poll_number >= ACTIVATION_MAX_POLLS:
                log(
                    "Lecture de la sélection impossible : application cible "
                    "non réactivée",
                    logging.WARNING,
                )
                finish("")
                return
            self._schedule(
                ACTIVATION_POLL_MS,
                lambda: await_activation(poll_number + 1),
            )

        if target is None:
            log("Lecture de la sélection ignorée : aucune application cible")
            finish("")
            return

        # Fast path: the target application is still frontmost at this point,
        # so the system-wide focused element is its own. When it answers there
        # is no activation, no clipboard and no synthetic keystroke at all.
        direct_text = self._accessibility.selected_text()
        if direct_text:
            mark("API Accessibilité")
            log(
                "Sélection lue via l’API Accessibilité : "
                f"{len(direct_text)} caractère(s)"
            )
            finish(direct_text)
            return
        mark("Accessibilité muette, repli presse-papiers")

        if not target.request_activation():
            log(
                "Lecture de la sélection impossible : application cible "
                "indisponible",
                logging.WARNING,
            )
            finish("")
            return
        await_activation()
