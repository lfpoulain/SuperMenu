"""Read the selected text straight from the Accessibility API.

SuperMenu already holds the Accessibility authorization, which also grants
read access to other applications' UI elements. When the focused element
answers ``kAXSelectedText`` there is no reason to run the clipboard dance at
all: no synthetic Command+C, no sentinel value, no overwriting and restoring
the user's clipboard, and no waiting on focus changes.

Coverage is not universal -- several Electron and Java toolkits expose nothing
useful -- so this is strictly an opportunistic fast path. Anything other than a
confident, non-empty answer returns ``None`` and the caller falls back to the
clipboard round trip.
"""

from __future__ import annotations

import logging
import os

from src.utils.logger import log


try:
    from HIServices import (
        AXUIElementCopyAttributeValue,
        AXUIElementCreateSystemWide,
        kAXFocusedUIElementAttribute,
        kAXSelectedTextAttribute,
    )
except ImportError:  # Allows the macOS source tests to run on other hosts.
    AXUIElementCopyAttributeValue = None
    AXUIElementCreateSystemWide = None
    kAXFocusedUIElementAttribute = "AXFocusedUIElement"
    kAXSelectedTextAttribute = "AXSelectedText"

# Optional bindings, looked up one by one: a symbol missing from an older
# PyObjC only disables its own safeguard, never the fast path above.
try:
    import HIServices as _hiservices
except ImportError:
    _hiservices = None
try:
    import CoreFoundation as _core_foundation
except ImportError:
    _core_foundation = None

AXUIElementSetMessagingTimeout = getattr(
    _hiservices, "AXUIElementSetMessagingTimeout", None
)
AXUIElementGetPid = getattr(_hiservices, "AXUIElementGetPid", None)
AXUIElementCreateApplication = getattr(
    _hiservices, "AXUIElementCreateApplication", None
)
kAXFocusedWindowAttribute = getattr(
    _hiservices, "kAXFocusedWindowAttribute", "AXFocusedWindow"
)
CFEqual = getattr(_core_foundation, "CFEqual", None)


_AX_SUCCESS = 0
# These calls run on the Qt main thread. Against a frozen application each one
# would otherwise wait for the system default of about six seconds, freezing
# every SuperMenu menu and window. A healthy application answers in a few
# milliseconds, but a busy one -- a huge document, a loaded Chromium tree --
# may need several hundred: a tighter ceiling would hand those to the
# clipboard fallback while they are still busy with the abandoned request.
AX_MESSAGING_TIMEOUT_S = 1.0


def limit_messaging_timeout(element) -> None:
    """Cap how long an Accessibility call on ``element`` may block.

    Applied to the system-wide element, Apple documents the timeout as global
    to the calling process. A failure keeps the system default.
    """
    if element is None or AXUIElementSetMessagingTimeout is None:
        return
    try:
        AXUIElementSetMessagingTimeout(element, AX_MESSAGING_TIMEOUT_S)
    except Exception as exc:
        log(
            f"Délai maximal Accessibilité non appliqué : {exc}",
            logging.DEBUG,
        )


def focused_window_of_application(process_id):
    """Return the Accessibility element of the app's focused window.

    ``None`` means "unknown": missing bindings, no permission, no window, an
    application that does not answer in time. Callers must then keep their
    application-level behaviour.
    """
    if (
        AXUIElementCreateApplication is None
        or AXUIElementCopyAttributeValue is None
    ):
        return None
    try:
        application = AXUIElementCreateApplication(int(process_id))
        if application is None:
            return None
        limit_messaging_timeout(application)
        error, window = AXUIElementCopyAttributeValue(
            application,
            kAXFocusedWindowAttribute,
            None,
        )
    except Exception as exc:
        log(
            f"Lecture Accessibilité de la fenêtre active impossible : {exc}",
            logging.DEBUG,
        )
        return None
    if error != _AX_SUCCESS:
        return None
    return window


def same_accessibility_element(first, second):
    """Compare two elements; ``None`` when the comparison is impossible."""
    if first is None or second is None:
        return None
    try:
        # Every query returns a new reference, so identity means nothing
        # here: CFEqual compares the UI elements the references point to.
        if CFEqual is not None:
            return bool(CFEqual(first, second))
        return bool(first == second)
    except Exception:
        return None


class _AccessibilityAPI:
    """Small injectable boundary around the HIServices calls used here."""

    focused_attribute = kAXFocusedUIElementAttribute
    selected_text_attribute = kAXSelectedTextAttribute

    @staticmethod
    def is_available() -> bool:
        return (
            AXUIElementCreateSystemWide is not None
            and AXUIElementCopyAttributeValue is not None
        )

    @staticmethod
    def system_wide_element():
        element = AXUIElementCreateSystemWide()
        limit_messaging_timeout(element)
        return element

    @staticmethod
    def copy_attribute(element, attribute):
        """Return ``(error_code, value)``; PyObjC maps the out-parameter here."""
        return AXUIElementCopyAttributeValue(element, attribute, None)

    @staticmethod
    def element_pid(element):
        """Return ``(error_code, pid)``, or ``None`` without the binding."""
        if AXUIElementGetPid is None:
            return None
        return AXUIElementGetPid(element, None)


class AccessibilitySelectionReader:
    """Ask the system-wide focused element for its selected text."""

    def __init__(self, api=None):
        self._api = api or _AccessibilityAPI()

    def selected_text(self):
        """Return the selection, or ``None`` when the API cannot answer."""
        if not self._api.is_available():
            return None
        try:
            system_wide = self._api.system_wide_element()
            if system_wide is None:
                return None
            error, focused = self._api.copy_attribute(
                system_wide,
                self._api.focused_attribute,
            )
            if error != _AX_SUCCESS or focused is None:
                return None
            if self._belongs_to_supermenu(focused):
                # SuperMenu's own field: a menu opened from its interface
                # must never send a selection made in SuperMenu itself.
                log(
                    "Lecture Accessibilité ignorée : l’élément focalisé "
                    "appartient à SuperMenu",
                    logging.DEBUG,
                )
                return None
            error, value = self._api.copy_attribute(
                focused,
                self._api.selected_text_attribute,
            )
            if error != _AX_SUCCESS or value is None:
                return None
        except Exception as exc:
            log(
                f"Lecture Accessibilité de la sélection impossible : {exc}",
                logging.DEBUG,
            )
            return None

        text = str(value)
        # An empty answer is treated as "no idea" rather than "nothing is
        # selected": several toolkits report an empty selection even when the
        # user has one, and the clipboard path still gets it right.
        return text or None

    def _belongs_to_supermenu(self, element) -> bool:
        """True only when the element is known to be one of SuperMenu's own.

        Any other answer, an unknown owner included, keeps the fast path:
        hosted views such as open panels may report another process.
        """
        element_pid = getattr(self._api, "element_pid", None)
        if not callable(element_pid):
            return False
        try:
            answer = element_pid(element)
            if answer is None:
                return False
            error, process_id = answer
            return (
                error == _AX_SUCCESS
                and process_id is not None
                and int(process_id) == os.getpid()
            )
        except Exception:
            return False
