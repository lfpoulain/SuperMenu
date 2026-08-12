"""Capture and reactivate the macOS application targeted by an insertion."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass


try:
    from AppKit import (
        NSApplicationActivateAllWindows,
        NSApplicationActivateIgnoringOtherApps,
        NSRunningApplication,
        NSWorkspace,
    )
except ImportError:  # Allows static tests on non-macOS hosts.
    NSApplicationActivateAllWindows = 0
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
            application = NSRunningApplication.runningApplicationWithProcessIdentifier_(
                self.process_id
            )
            if application is None or application.isTerminated():
                return False
            if self.bundle_identifier:
                current_bundle = str(application.bundleIdentifier() or "")
                if current_bundle != self.bundle_identifier:
                    return False
            options = (
                NSApplicationActivateIgnoringOtherApps
                | NSApplicationActivateAllWindows
            )
            if not application.activateWithOptions_(options):
                return False
            for _attempt in range(5):
                time.sleep(0.05)
                if self.is_current():
                    return True
            return False
        except Exception:
            return False
