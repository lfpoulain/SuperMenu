"""Capture and reactivate the macOS application targeted by an insertion."""

from __future__ import annotations

import os
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


def _shared_application(application_class):
    if application_class is None:
        return None
    try:
        return application_class.sharedApplication()
    except Exception:
        return None


def current_application_is_active() -> bool:
    """Return whether AppKit currently considers SuperMenu active."""
    application = _shared_application(NSApplication)
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


def _activate_current_application(
    application_class,
    running_application_class,
    legacy_activation_option,
    *,
    force: bool = False,
) -> bool:
    """Implementation with explicit native adapters for deterministic tests."""
    application = _shared_application(application_class)
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

    if running_application_class is None:
        return False
    try:
        current = running_application_class.currentApplication()
        if current is None or current.isTerminated():
            return False
        return bool(
            current.activateWithOptions_(
                legacy_activation_option
            )
        )
    except Exception:
        return False


def activate_current_application(*, force: bool = False) -> bool:
    """Request SuperMenu activation, preferring Apple's cooperative API."""
    return _activate_current_application(
        NSApplication,
        NSRunningApplication,
        NSApplicationActivateIgnoringOtherApps,
        force=force,
    )


# The application the user came from, remembered the moment SuperMenu is about
# to take focus. Menus opened from SuperMenu's own UI cannot capture a target
# any more -- by then SuperMenu is the frontmost application.
_last_external_target = None


@dataclass(frozen=True)
class PasteTarget:
    process_id: int
    bundle_identifier: str = ""
    application_name: str = ""

    @classmethod
    def capture(
        cls,
        *,
        allow_current_process: bool = False,
        fall_back_to_last_known: bool = False,
    ):
        global _last_external_target
        application = _frontmost_application()
        if application is None:
            return None
        try:
            process_id = int(application.processIdentifier())
            if not allow_current_process and process_id == os.getpid():
                if fall_back_to_last_known and _last_external_target is not None:
                    if _last_external_target._running_application() is not None:
                        return _last_external_target
                    _last_external_target = None
                return None
            target = cls(
                process_id=process_id,
                bundle_identifier=str(application.bundleIdentifier() or ""),
                application_name=str(application.localizedName() or ""),
            )
        except Exception:
            return None
        if target.process_id != os.getpid():
            _last_external_target = target
        return target

    @classmethod
    def remember_frontmost(cls):
        """Record the current target before SuperMenu steals the foreground.

        Call this just before activating SuperMenu, so a menu opened from the
        configuration window or the menu bar still knows where to paste.
        """
        return cls.capture()

    @classmethod
    def forget_last_known(cls) -> None:
        global _last_external_target
        _last_external_target = None

    def is_current(self) -> bool:
        application = _frontmost_application()
        if application is None:
            return False
        try:
            if int(application.processIdentifier()) != self.process_id:
                return False
            if self.bundle_identifier:
                return (
                    str(application.bundleIdentifier() or "")
                    == self.bundle_identifier
                )
            return True
        except Exception:
            return False

    def _running_application(self):
        if NSRunningApplication is None:
            return None
        try:
            application = NSRunningApplication.runningApplicationWithProcessIdentifier_(
                self.process_id
            )
            if application is None or application.isTerminated():
                return None
            if self.bundle_identifier:
                current_bundle = str(application.bundleIdentifier() or "")
                if current_bundle != self.bundle_identifier:
                    return None
            return application
        except Exception:
            return None

    def request_activation(self, *, force: bool = False) -> bool:
        """Validate the captured identity and ask macOS to foreground it."""
        if self.is_current():
            return True
        application = self._running_application()
        if application is None:
            return False
        if not force:
            try:
                own_application = _shared_application(NSApplication)
                if own_application is not None:
                    yield_activation = getattr(
                        own_application,
                        "yieldActivationToApplication_",
                        None,
                    )
                    if callable(yield_activation) and own_application.isActive():
                        yield_activation(application)
                        if application.activateWithOptions_(0):
                            return True
            except Exception:
                # The compatibility activation below is still safe because
                # the PID and bundle identifier have already been validated.
                pass

        # Compatibility path for older macOS versions, or when the
        # cooperative request was declined despite a still-valid target.
        try:
            return bool(
                application.activateWithOptions_(
                    NSApplicationActivateIgnoringOtherApps
                )
            )
        except Exception:
            return False

    # There is deliberately no synchronous activate-and-verify helper here.
    # NSRunningApplication and NSWorkspace refresh their properties through the
    # main run loop, so sleeping on the Qt thread while polling is_current()
    # suppressed the update it was waiting for and reported working activations
    # as failures. Callers schedule their polls instead; see
    # src/utils/selection.py and src/utils/text_inserter.py.
