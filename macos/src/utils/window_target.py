"""Capture and reactivate the macOS application targeted by an insertion."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass


try:
    from AppKit import (
        NSApplication,
        NSApplicationActivateIgnoringOtherApps,
        NSRunningApplication,
        NSWorkspace,
    )
except ImportError:  # Allows static tests on non-macOS hosts.
    NSApplication = None
    NSApplicationActivateIgnoringOtherApps = 0
    NSRunningApplication = None
    NSWorkspace = None


def _frontmost_application():
    if NSWorkspace is None:
        return None
    try:
        return NSWorkspace.sharedWorkspace().frontmostApplication()
    except Exception:
        return None


def _shared_application():
    if NSApplication is None:
        return None
    try:
        return NSApplication.sharedApplication()
    except Exception:
        return None


def current_application_is_active() -> bool:
    """Return whether AppKit currently considers SuperMenu active."""
    application = _shared_application()
    if application is not None:
        try:
            return bool(application.isActive())
        except Exception:
            pass
    if NSRunningApplication is None:
        return False
    try:
        current = NSRunningApplication.currentApplication()
        return bool(current is not None and current.isActive())
    except Exception:
        return False


def activate_current_application(*, force: bool = False) -> bool:
    """Request SuperMenu activation, preferring Apple's cooperative API."""
    application = _shared_application()
    if application is not None:
        try:
            if application.isActive():
                return True
            modern_activate = getattr(application, "activate", None)
            if not force and callable(modern_activate):
                modern_activate()
                return True
        except Exception:
            pass

    if NSRunningApplication is None:
        return False
    try:
        current = NSRunningApplication.currentApplication()
        if current is None or current.isTerminated():
            return False
        return bool(
            current.activateWithOptions_(
                NSApplicationActivateIgnoringOtherApps
            )
        )
    except Exception:
        return False


@dataclass(frozen=True)
class PasteTarget:
    process_id: int
    bundle_identifier: str = ""
    application_name: str = ""

    @classmethod
    def capture(cls, *, allow_current_process: bool = False):
        application = _frontmost_application()
        if application is None:
            return None
        try:
            process_id = int(application.processIdentifier())
            if not allow_current_process and process_id == os.getpid():
                return None
            return cls(
                process_id=process_id,
                bundle_identifier=str(application.bundleIdentifier() or ""),
                application_name=str(application.localizedName() or ""),
            )
        except Exception:
            return None

    def is_current(self) -> bool:
        application = _frontmost_application()
        if application is None:
            return False
        try:
            return int(application.processIdentifier()) == self.process_id
        except Exception:
            return False

    def activate_and_verify(self) -> bool:
        if NSRunningApplication is None:
            return False
        try:
            if self.is_current():
                return True
            application = NSRunningApplication.runningApplicationWithProcessIdentifier_(
                self.process_id
            )
            if application is None or application.isTerminated():
                return False
            if self.bundle_identifier:
                current_bundle = str(application.bundleIdentifier() or "")
                if current_bundle != self.bundle_identifier:
                    return False

            cooperative = False
            own_application = _shared_application()
            if own_application is not None:
                yield_activation = getattr(
                    own_application,
                    "yieldActivationToApplication_",
                    None,
                )
                if callable(yield_activation) and own_application.isActive():
                    yield_activation(application)
                    cooperative = True

            options = 0 if cooperative else NSApplicationActivateIgnoringOtherApps
            if not application.activateWithOptions_(options):
                return False
            for _attempt in range(6):
                time.sleep(0.05)
                if self.is_current():
                    return True

            # Compatibility fallback for a target that did not honor the
            # cooperative request (notably on older macOS releases).
            if cooperative and application.activateWithOptions_(
                NSApplicationActivateIgnoringOtherApps
            ):
                for _attempt in range(4):
                    time.sleep(0.05)
                    if self.is_current():
                        return True
            return False
        except Exception:
            return False
