"""macOS privacy permission helpers."""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class PermissionStatus:
    accessibility: bool
    input_monitoring: bool

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


def current_permission_status() -> PermissionStatus:
    return PermissionStatus(
        accessibility=accessibility_is_trusted(),
        input_monitoring=input_monitoring_is_trusted(),
    )


def automation_permissions_are_trusted() -> bool:
    return current_permission_status().all_granted
