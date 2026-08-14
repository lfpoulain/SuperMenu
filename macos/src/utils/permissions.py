"""macOS Accessibility permission helpers.

SuperMenu monitors global key events with AppKit's ``NSEvent`` API and emits
Copy/Paste shortcuts.  Apple documents Accessibility as the authorization for
both operations, so Input Monitoring is deliberately not requested as a
second, redundant TCC permission.
"""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


ACCESSIBILITY_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
)

_APPLICATION_SERVICES_PATH = (
    "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
)


def _load_boolean_function(framework_path: str, function_name: str):
    if sys.platform != "darwin":
        return None
    try:
        framework = ctypes.CDLL(framework_path)
        function = getattr(framework, function_name)
        function.argtypes = []
        function.restype = ctypes.c_bool
        return function
    except (AttributeError, OSError):
        return None


_ax_is_process_trusted = _load_boolean_function(
    _APPLICATION_SERVICES_PATH,
    "AXIsProcessTrusted",
)


def _load_accessibility_prompt_api():
    """Load the optional prompt API without affecting the status check."""
    if sys.platform != "darwin":
        return None, None
    try:
        import HIServices

        return (
            getattr(HIServices, "AXIsProcessTrustedWithOptions", None),
            getattr(HIServices, "kAXTrustedCheckOptionPrompt", None),
        )
    except ImportError:
        return None, None


_ax_is_process_trusted_with_options, _ax_prompt_key = (
    _load_accessibility_prompt_api()
)


@dataclass(frozen=True)
class PermissionStatus:
    accessibility: bool
    accessibility_check_available: bool = True
    consent_prompt_available: bool = True

    @property
    def all_granted(self) -> bool:
        return self.accessibility

    @property
    def missing_labels(self) -> tuple[str, ...]:
        labels = []
        if not self.accessibility:
            labels.append("Accessibilité")
        return tuple(labels)


def request_accessibility_permission() -> bool:
    """Ask macOS to display its native Accessibility consent dialog.

    The native function returns the current trust state, not whether it showed
    a dialog.  This helper therefore reports whether the request was dispatched
    successfully so callers do not open System Settings over the system prompt.
    """
    if not consent_prompt_is_available():
        return False
    try:
        _ax_is_process_trusted_with_options({_ax_prompt_key: True})
        return True
    except Exception:
        return False


def accessibility_is_trusted() -> bool:
    if _ax_is_process_trusted is None:
        return False
    try:
        return bool(_ax_is_process_trusted())
    except Exception:
        return False


def open_accessibility_settings() -> bool:
    return bool(QDesktopServices.openUrl(QUrl(ACCESSIBILITY_SETTINGS_URL)))


def consent_prompt_is_available() -> bool:
    """Whether macOS can be asked to show its own Accessibility dialog.

    ``HIServices`` lives in pyobjc-framework-ApplicationServices. When that
    dependency is missing the import failure is silent, and the app can only
    open a System Settings pane that does not list SuperMenu yet — macOS adds
    an app to that list when it *requests* the permission, not when it is
    merely installed. Surfacing the capability keeps the failure visible.
    """
    return _ax_is_process_trusted_with_options is not None and _ax_prompt_key is not None


def current_permission_status() -> PermissionStatus:
    return PermissionStatus(
        accessibility=accessibility_is_trusted(),
        accessibility_check_available=_ax_is_process_trusted is not None,
        consent_prompt_available=consent_prompt_is_available(),
    )
