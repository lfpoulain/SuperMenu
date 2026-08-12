"""macOS privacy permission helpers."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


try:
    from Quartz import (
        AXIsProcessTrusted,
        AXIsProcessTrustedWithOptions,
        CGPreflightListenEventAccess,
        CGRequestListenEventAccess,
        kAXTrustedCheckOptionPrompt,
    )
except ImportError:  # Allows static tests on non-macOS hosts.
    AXIsProcessTrusted = None
    AXIsProcessTrustedWithOptions = None
    CGPreflightListenEventAccess = None
    CGRequestListenEventAccess = None
    kAXTrustedCheckOptionPrompt = None


ACCESSIBILITY_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
)
INPUT_MONITORING_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
)


def accessibility_is_trusted(*, prompt: bool = False) -> bool:
    if AXIsProcessTrusted is None:
        return False
    try:
        if prompt and AXIsProcessTrustedWithOptions is not None:
            return bool(
                AXIsProcessTrustedWithOptions(
                    {kAXTrustedCheckOptionPrompt: True}
                )
            )
        return bool(AXIsProcessTrusted())
    except Exception:
        return False


def open_accessibility_settings() -> bool:
    return bool(QDesktopServices.openUrl(QUrl(ACCESSIBILITY_SETTINGS_URL)))


def input_monitoring_is_trusted(*, prompt: bool = False) -> bool:
    if CGPreflightListenEventAccess is None:
        return False
    try:
        if prompt and CGRequestListenEventAccess is not None:
            return bool(CGRequestListenEventAccess())
        return bool(CGPreflightListenEventAccess())
    except Exception:
        return False


def open_input_monitoring_settings() -> bool:
    return bool(QDesktopServices.openUrl(QUrl(INPUT_MONITORING_SETTINGS_URL)))


def automation_permissions_are_trusted() -> bool:
    return accessibility_is_trusted() and input_monitoring_is_trusted()
