"""macOS privacy permission helpers.

The status checks deliberately use the native framework functions through
``ctypes``.  This keeps the two checks independent and avoids a missing PyObjC
symbol making every permission look denied.
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
INPUT_MONITORING_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
)

_APPLICATION_SERVICES_PATH = (
    "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
)
_CORE_GRAPHICS_PATH = (
    "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
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
_cg_preflight_listen_event_access = _load_boolean_function(
    _CORE_GRAPHICS_PATH,
    "CGPreflightListenEventAccess",
)
_cg_request_listen_event_access = _load_boolean_function(
    _CORE_GRAPHICS_PATH,
    "CGRequestListenEventAccess",
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
    input_monitoring: bool
    accessibility_check_available: bool = True
    input_monitoring_check_available: bool = True

    @property
    def all_granted(self) -> bool:
        return self.accessibility and self.input_monitoring

    @property
    def missing_labels(self) -> tuple[str, ...]:
        labels = []
        if not self.accessibility:
            labels.append("Accessibilité")
        if not self.input_monitoring:
            labels.append("Surveillance de l’entrée")
        return tuple(labels)


def accessibility_is_trusted(*, prompt: bool = False) -> bool:
    if prompt and _ax_is_process_trusted_with_options and _ax_prompt_key:
        try:
            _ax_is_process_trusted_with_options({_ax_prompt_key: True})
        except Exception:
            # Opening the matching settings pane remains the reliable fallback.
            pass
    if _ax_is_process_trusted is None:
        return False
    try:
        return bool(_ax_is_process_trusted())
    except Exception:
        return False


def open_accessibility_settings() -> bool:
    return bool(QDesktopServices.openUrl(QUrl(ACCESSIBILITY_SETTINGS_URL)))


def input_monitoring_is_trusted(*, prompt: bool = False) -> bool:
    function = (
        _cg_request_listen_event_access
        if prompt and _cg_request_listen_event_access is not None
        else _cg_preflight_listen_event_access
    )
    if function is None:
        return False
    try:
        return bool(function())
    except Exception:
        return False


def open_input_monitoring_settings() -> bool:
    return bool(QDesktopServices.openUrl(QUrl(INPUT_MONITORING_SETTINGS_URL)))


def current_permission_status() -> PermissionStatus:
    return PermissionStatus(
        accessibility=accessibility_is_trusted(),
        input_monitoring=input_monitoring_is_trusted(),
        accessibility_check_available=_ax_is_process_trusted is not None,
        input_monitoring_check_available=(
            _cg_preflight_listen_event_access is not None
        ),
    )


def automation_permissions_are_trusted() -> bool:
    return current_permission_status().all_granted
