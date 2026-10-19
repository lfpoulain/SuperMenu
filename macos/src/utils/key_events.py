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
        CGEventSourceCreate,
        CGEventSourceSetLocalEventsSuppressionInterval,
        kCGEventFlagMaskCommand,
        kCGEventSourceStateHIDSystemState,
        kCGHIDEventTap,
    )
except ImportError:  # Allows the macOS source tests to run on other hosts.
    CGEventCreateKeyboardEvent = None
    CGEventPost = None
    CGEventSetFlags = None
    CGEventSourceCreate = None
    CGEventSourceSetLocalEventsSuppressionInterval = None
    kCGEventFlagMaskCommand = 1 << 20
    kCGEventSourceStateHIDSystemState = 1
    kCGHIDEventTap = 0


# Positional virtual key codes from Carbon's Events.h.
KEY_CODE_C = 0x08
KEY_CODE_V = 0x09
KEY_CODE_COMMAND = 0x37

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

    def __init__(self):
        self._source = None
        self._source_resolved = False

    def _event_source(self):
        """Return a source that does not mute the user's own input.

        By default macOS suppresses local keyboard and mouse events for a
        quarter of a second after a synthetic one is posted. That is what made
        the pointer stop updating and the next selection impossible right after
        a prompt ran.
        """
        if self._source_resolved:
            return self._source
        self._source_resolved = True
        if CGEventSourceCreate is None:
            return None
        try:
            source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)
            if source is not None and CGEventSourceSetLocalEventsSuppressionInterval:
                CGEventSourceSetLocalEventsSuppressionInterval(source, 0.0)
            self._source = source
        except Exception as exc:
            log(
                f"Source d'événements CoreGraphics indisponible : {exc}",
                logging.WARNING,
            )
        return self._source

    def post_key(self, key_code: int, key_down: bool, flags: int) -> None:
        if CGEventCreateKeyboardEvent is None:
            raise RuntimeError("Quartz est indisponible")
        event = CGEventCreateKeyboardEvent(
            self._event_source(),
            key_code,
            key_down,
        )
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
        """Post Command+<key> as a complete, coherent key sequence.

        Setting the Command flag on the letter alone is not enough. An
        application that receives a key-down carrying the Command flag without
        ever seeing the matching flagsChanged events can be left believing the
        modifier is still held: Chrome then stops showing the text cursor and
        refuses the next selection until its own state resynchronises. Pressing
        and releasing the modifier key itself produces those events.
        """
        flags = int(self._api.command_flag)
        modifier_pressed = False
        success = False
        try:
            self._api.post_key(KEY_CODE_COMMAND, True, flags)
            modifier_pressed = True
            self._api.post_key(key_code, True, flags)
            self._api.post_key(key_code, False, flags)
            success = True
        except Exception as exc:
            log(f"Envoi du raccourci clavier impossible : {exc}", logging.ERROR)
        if modifier_pressed:
            # Never leave Command latched, even on a partial failure: every
            # following keystroke would be read as a shortcut.
            try:
                self._api.post_key(KEY_CODE_COMMAND, False, 0)
            except Exception as exc:
                log(f"Relâchement de Command impossible : {exc}", logging.ERROR)
                return False
        return success

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
