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


_AX_SUCCESS = 0


class _AccessibilityAPI:
    """Small injectable boundary around the three HIServices calls used here."""

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
        return AXUIElementCreateSystemWide()

    @staticmethod
    def copy_attribute(element, attribute):
        """Return ``(error_code, value)``; PyObjC maps the out-parameter here."""
        return AXUIElementCopyAttributeValue(element, attribute, None)


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
