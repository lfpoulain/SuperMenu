"""Synthesize the Copy/Paste shortcuts with deterministic modifier flags.

Two problems make ``pynput`` the wrong tool for this job on macOS.

The first is timing. The global shortcut fires on key *down*, so when SuperMenu
posts its Command+C a fraction of a second later the user is usually still
holding the shortcut's own modifiers. The window server merges that physical
state into synthetic events, and the target application receives Command+Shift+C
instead of a copy. Assigning the flags explicitly with ``CGEventSetFlags``
replaces the merged state rather than adding to it.

The second is layout. ``pynput`` resolves the character ``c`` through the active
keyboard layout, which fails outright on non-Latin layouts. Virtual key codes are
positional: ``kVK_ANSI_C`` is the same physical key on QWERTY and AZERTY, and
macOS falls back to the Latin layout for command key equivalents anyway.
"""

from __future__ import annotations

import logging

from src.utils.logger import log


try:
    from AppKit import (
        NSEvent,
        NSEventModifierFlagCommand,
        NSEventModifierFlagControl,
        NSEventModifierFlagDeviceIndependentFlagsMask,
        NSEventModifierFlagOption,
        NSEventModifierFlagShift,
    )
except ImportError:  # Allows the macOS source tests to run on other hosts.
    NSEvent = None
    NSEventModifierFlagCommand = 1 << 20
    NSEventModifierFlagControl = 1 << 18
    NSEventModifierFlagDeviceIndependentFlagsMask = 0xFFFF0000
    NSEventModifierFlagOption = 1 << 19
    NSEventModifierFlagShift = 1 << 17

try:
    from Quartz import (
        CGEventCreateKeyboardEvent,
        CGEventPost,
        CGEventSetFlags,
        kCGEventFlagMaskCommand,
        kCGHIDEventTap,
    )
except ImportError:  # Allows the macOS source tests to run on other hosts.
    CGEventCreateKeyboardEvent = None
    CGEventPost = None
    CGEventSetFlags = None
    kCGEventFlagMaskCommand = 1 << 20
    kCGHIDEventTap = 0


# Positional virtual key codes from Carbon's Events.h.
KEY_CODE_C = 0x08
KEY_CODE_V = 0x09

MODIFIER_RELEASE_POLL_MS = 20
MODIFIER_RELEASE_MAX_POLLS = 25

_SHORTCUT_MODIFIERS = (
    int(NSEventModifierFlagCommand)
    | int(NSEventModifierFlagControl)
    | int(NSEventModifierFlagOption)
    | int(NSEventModifierFlagShift)
)


class _QuartzKeyboardAPI:
    """Small injectable boundary around the CoreGraphics posting calls."""

    command_flag = int(kCGEventFlagMaskCommand)

    @staticmethod
    def post_key(key_code: int, key_down: bool, flags: int) -> None:
        if CGEventCreateKeyboardEvent is None:
            raise RuntimeError("Quartz est indisponible")
        event = CGEventCreateKeyboardEvent(None, key_code, key_down)
        if event is None:
            raise RuntimeError("macOS n'a pas créé l'événement clavier")
        CGEventSetFlags(event, flags)
        CGEventPost(kCGHIDEventTap, event)

    @staticmethod
    def held_modifiers() -> int:
        if NSEvent is None:
            return 0
        try:
            return int(NSEvent.modifierFlags()) & int(
                NSEventModifierFlagDeviceIndependentFlagsMask
            )
        except Exception:
            return 0


class KeyEventPoster:
    """Post Command shortcuts and observe the physically held modifiers."""

    def __init__(self, api=None):
        self._api = api or _QuartzKeyboardAPI()

    def modifiers_are_released(self) -> bool:
        return not (int(self._api.held_modifiers()) & _SHORTCUT_MODIFIERS)

    def post_command_shortcut(self, key_code: int) -> bool:
        try:
            flags = int(self._api.command_flag)
            self._api.post_key(key_code, True, flags)
            self._api.post_key(key_code, False, flags)
            return True
        except Exception as exc:
            log(f"Envoi du raccourci clavier impossible : {exc}", logging.ERROR)
            return False

    def copy(self) -> bool:
        return self.post_command_shortcut(KEY_CODE_C)

    def paste(self) -> bool:
        return self.post_command_shortcut(KEY_CODE_V)

    def when_modifiers_released(self, schedule, callback, poll_number: int = 0) -> None:
        """Call back once the user lets go, without blocking the run loop.

        The wait is bounded: a stuck or genuinely held modifier must not strand
        the shortcut, so after ``MODIFIER_RELEASE_MAX_POLLS`` the caller runs
        anyway and relies on the explicit flags to keep the event clean.
        """
        if self.modifiers_are_released():
            callback()
            return
        if poll_number >= MODIFIER_RELEASE_MAX_POLLS:
            log(
                "Modificateurs toujours enfoncés : envoi du raccourci malgré "
                "l'attente"
            )
            callback()
            return
        schedule(
            MODIFIER_RELEASE_POLL_MS,
            lambda: self.when_modifiers_released(
                schedule,
                callback,
                poll_number + 1,
            ),
        )
