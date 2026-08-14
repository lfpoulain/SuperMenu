"""Global macOS hotkeys and the Qt shortcut recorder dialog."""

from __future__ import annotations

import logging
import re
import sys
import threading

from pynput.keyboard import HotKey
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.utils.logger import log


try:
    from AppKit import (
        NSEvent,
        NSEventMaskKeyDown,
        NSEventModifierFlagCommand,
        NSEventModifierFlagControl,
        NSEventModifierFlagDeviceIndependentFlagsMask,
        NSEventModifierFlagOption,
        NSEventModifierFlagShift,
    )
except ImportError:  # Allows the macOS source tests to run on other hosts.
    NSEvent = None
    NSEventMaskKeyDown = 0
    NSEventModifierFlagCommand = 0
    NSEventModifierFlagControl = 0
    NSEventModifierFlagDeviceIndependentFlagsMask = 0
    NSEventModifierFlagOption = 0
    NSEventModifierFlagShift = 0


_MODIFIER_ALIASES = {
    "cmd": "cmd",
    "command": "cmd",
    "meta": "cmd",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
    "shift": "shift",
}

_SPECIAL_KEYS = {
    "space": "space",
    "tab": "tab",
    "enter": "enter",
    "return": "enter",
    "esc": "esc",
    "escape": "esc",
    "backspace": "backspace",
    "delete": "delete",
    "home": "home",
    "end": "end",
    "pageup": "page_up",
    "pagedown": "page_down",
    "left": "left",
    "right": "right",
    "up": "up",
    "down": "down",
}


def _modifier_labels(modifiers, *, macos=None) -> list[str]:
    """Translate Qt modifiers to physical macOS modifier names."""
    if macos is None:
        macos = sys.platform == "darwin"
    command_modifier = (
        Qt.KeyboardModifier.ControlModifier
        if macos
        else Qt.KeyboardModifier.MetaModifier
    )
    control_modifier = (
        Qt.KeyboardModifier.MetaModifier
        if macos
        else Qt.KeyboardModifier.ControlModifier
    )
    parts = []
    if modifiers & command_modifier:
        parts.append("Cmd")
    if modifiers & Qt.KeyboardModifier.AltModifier:
        parts.append("Option")
    if modifiers & control_modifier:
        parts.append("Ctrl")
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        parts.append("Shift")
    return parts


def normalize_hotkey(hotkey: str) -> tuple[str | None, str]:
    """Convert the persisted display format to pynput's canonical format."""
    if not isinstance(hotkey, str) or not hotkey.strip():
        return None, "Le raccourci ne peut pas être vide"
    parts = [part.strip() for part in hotkey.split("+") if part.strip()]
    if len(parts) < 2:
        return None, "Le raccourci doit contenir un modificateur"

    modifiers = []
    seen = set()
    for part in parts[:-1]:
        modifier = _MODIFIER_ALIASES.get(part.lower())
        if modifier is None:
            return None, f"Modificateur inconnu : {part}"
        if modifier in seen:
            return None, "Le raccourci contient des touches dupliquées"
        seen.add(modifier)
        modifiers.append(f"<{modifier}>")

    key_token = parts[-1]
    if key_token.lower() in _MODIFIER_ALIASES:
        return None, "Le raccourci doit contenir une touche"
    key_lower = key_token.lower()
    if "cmd" in seen and key_lower == "q":
        return None, "Cmd+Q est réservé à la fermeture de macOS"
    if seen == {"cmd"} and key_lower in {"h", "m", "w"}:
        return None, "Ce raccourci est réservé à la gestion des fenêtres macOS"
    if seen == {"cmd"} and key_lower == "space":
        return None, "Cmd+Space est réservé à Spotlight"
    if key_lower in _SPECIAL_KEYS:
        key = f"<{_SPECIAL_KEYS[key_lower]}>"
    elif re.fullmatch(r"f(?:[1-9]|1[0-9]|2[0-4])", key_lower):
        key = f"<{key_lower}>"
    elif len(key_token) == 1 and key_token.isprintable():
        key = key_token.lower()
    else:
        return None, f"Touche non supportée : {key_token}"
    return "+".join(modifiers + [key]), ""


class HotkeyRecorderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Définir un nouveau raccourci")
        self.setMinimumWidth(420)
        self.recorded_hotkey = ""
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("Appuyez sur la combinaison de touches à utiliser.")
        )
        self.current_hotkey_label = QLabel(
            "Utilisez au moins Cmd, Option, Ctrl ou Shift"
        )
        self.current_hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_hotkey_label.setStyleSheet(
            "font-weight: bold; font-size: 16px; padding: 10px;"
        )
        layout.addWidget(self.current_hotkey_label)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("Annuler")
        cancel_button.clicked.connect(self.reject)
        self.ok_button = QPushButton("OK")
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.accept)
        buttons.addWidget(cancel_button)
        buttons.addWidget(self.ok_button)
        layout.addLayout(buttons)

    def keyPressEvent(self, event: QKeyEvent):
        if event.isAutoRepeat():
            return
        modifiers = event.modifiers()
        parts = _modifier_labels(modifiers)

        key = event.key()
        modifier_keys = {
            Qt.Key.Key_Meta,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
        }
        if key in modifier_keys:
            self.current_hotkey_label.setText("+".join(parts) + "+…")
            return
        if not parts:
            self.current_hotkey_label.setText("Ajoutez un modificateur")
            self.ok_button.setEnabled(False)
            return

        key_map = {
            Qt.Key.Key_Space: "Space",
            Qt.Key.Key_Tab: "Tab",
            Qt.Key.Key_Backspace: "Backspace",
            Qt.Key.Key_Return: "Enter",
            Qt.Key.Key_Enter: "Enter",
            Qt.Key.Key_Escape: "Esc",
            Qt.Key.Key_Delete: "Delete",
            Qt.Key.Key_Home: "Home",
            Qt.Key.Key_End: "End",
            Qt.Key.Key_PageUp: "PageUp",
            Qt.Key.Key_PageDown: "PageDown",
            Qt.Key.Key_Left: "Left",
            Qt.Key.Key_Right: "Right",
            Qt.Key.Key_Up: "Up",
            Qt.Key.Key_Down: "Down",
        }
        key_map.update(
            {
                getattr(Qt.Key, f"Key_F{number}"): f"F{number}"
                for number in range(1, 25)
            }
        )
        key_part = key_map.get(Qt.Key(key))
        if key_part is None:
            text = (event.text() or "").strip()
            if len(text) == 1 and text.isprintable() and text != "+":
                key_part = text.upper()
        if not key_part:
            self.current_hotkey_label.setText("Touche non supportée")
            self.ok_button.setEnabled(False)
            return

        hotkey = "+".join(parts + [key_part])
        _normalized, error = normalize_hotkey(hotkey)
        if error:
            self.current_hotkey_label.setText(error)
            self.ok_button.setEnabled(False)
            return
        self.recorded_hotkey = hotkey
        self.current_hotkey_label.setText(hotkey)
        self.ok_button.setEnabled(True)


_MACOS_SPECIAL_KEY_CODES = {
    0x24: "enter",
    0x30: "tab",
    0x31: "space",
    0x33: "backspace",
    0x35: "esc",
    0x40: "f17",
    0x4C: "enter",  # Numeric keypad Enter.
    0x4F: "f18",
    0x50: "f19",
    0x5A: "f20",
    0x60: "f5",
    0x61: "f6",
    0x62: "f7",
    0x63: "f3",
    0x64: "f8",
    0x65: "f9",
    0x67: "f11",
    0x69: "f13",
    0x6A: "f16",
    0x6B: "f14",
    0x6D: "f10",
    0x6F: "f12",
    0x71: "f15",
    0x73: "home",
    0x74: "page_up",
    0x75: "delete",
    0x76: "f4",
    0x77: "end",
    0x78: "f2",
    0x79: "page_down",
    0x7A: "f1",
    0x7B: "left",
    0x7C: "right",
    0x7D: "down",
    0x7E: "up",
}


def _native_binding_signature(shortcut):
    """Return the AppKit signature for an already-normalized shortcut."""
    HotKey.parse(shortcut)
    parts = shortcut.split("+")
    modifiers = frozenset(part[1:-1] for part in parts[:-1])
    key = parts[-1]
    if len(key) > 2 and key.startswith("<") and key.endswith(">"):
        key = key[1:-1]
    return modifiers, key.lower()


class _AppKitEventAPI:
    """Small injectable boundary around AppKit's local/global monitors."""

    command_flag = NSEventModifierFlagCommand
    control_flag = NSEventModifierFlagControl
    option_flag = NSEventModifierFlagOption
    shift_flag = NSEventModifierFlagShift
    independent_flags_mask = NSEventModifierFlagDeviceIndependentFlagsMask

    @staticmethod
    def add_global_monitor(handler):
        if NSEvent is None:
            raise RuntimeError("AppKit est indisponible")
        return NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown,
            handler,
        )

    @staticmethod
    def add_local_monitor(handler):
        if NSEvent is None:
            raise RuntimeError("AppKit est indisponible")
        return NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown,
            handler,
        )

    @staticmethod
    def remove_monitor(monitor):
        if NSEvent is not None:
            NSEvent.removeMonitor_(monitor)


class _MacOSGlobalHotKeys:
    """Persistent native AppKit key monitor with replaceable bindings."""

    def __init__(self, event_api=None):
        self._event_api = event_api or _AppKitEventAPI()
        self._bindings_lock = threading.RLock()
        self._bindings = {}
        self._suspended = False
        self._global_monitor = None
        self._local_monitor = None
        self._alive = False

    def replace_bindings(self, bindings):
        parsed = {
            _native_binding_signature(shortcut): (shortcut, callback)
            for shortcut, callback in bindings.items()
        }
        with self._bindings_lock:
            self._bindings = parsed

    def set_suspended(self, suspended):
        with self._bindings_lock:
            self._suspended = bool(suspended)

    def start(self):
        if self._alive:
            return
        global_monitor = None
        local_monitor = None
        try:
            global_monitor = self._event_api.add_global_monitor(
                self._handle_global_event
            )
            local_monitor = self._event_api.add_local_monitor(
                self._handle_local_event
            )
            if global_monitor is None or local_monitor is None:
                raise RuntimeError(
                    "macOS n'a pas créé les moniteurs clavier AppKit"
                )
        except Exception:
            if global_monitor is not None:
                self._event_api.remove_monitor(global_monitor)
            if local_monitor is not None:
                self._event_api.remove_monitor(local_monitor)
            raise
        self._global_monitor = global_monitor
        self._local_monitor = local_monitor
        self._alive = True

    def wait(self):
        """Compatibility with the previous threaded listener interface."""

    def is_alive(self):
        return bool(
            self._alive
            and self._global_monitor is not None
            and self._local_monitor is not None
        )

    def stop(self):
        if not self._alive:
            return
        self._alive = False
        global_monitor = self._global_monitor
        local_monitor = self._local_monitor
        self._global_monitor = None
        self._local_monitor = None
        if global_monitor is not None:
            self._event_api.remove_monitor(global_monitor)
        if local_monitor is not None:
            self._event_api.remove_monitor(local_monitor)

    def join(self, timeout=None):
        """Compatibility with the previous threaded listener interface."""

    def _event_signature(self, event):
        flags = int(event.modifierFlags()) & int(
            self._event_api.independent_flags_mask
        )
        modifiers = set()
        for name, flag in (
            ("cmd", self._event_api.command_flag),
            ("ctrl", self._event_api.control_flag),
            ("alt", self._event_api.option_flag),
            ("shift", self._event_api.shift_flag),
        ):
            if flags & int(flag):
                modifiers.add(name)

        key_code = int(event.keyCode())
        key = _MACOS_SPECIAL_KEY_CODES.get(key_code)
        if key is None:
            key = str(event.charactersIgnoringModifiers() or "").lower()
        return frozenset(modifiers), key, key_code

    def _handle_event(self, event):
        try:
            if bool(event.isARepeat()):
                return
            modifiers, key, key_code = self._event_signature(event)
            signature = (modifiers, key)
            with self._bindings_lock:
                if self._suspended:
                    return
                binding = self._bindings.get(signature)
                configured_modifiers = {
                    configured[0] for configured in self._bindings
                }
            if modifiers in configured_modifiers:
                observed = "+".join(sorted(modifiers) + [key or "?"])
                log(
                    "Événement clavier AppKit observé : "
                    f"{observed} (keyCode={key_code})"
                )
            if binding is None:
                return
            shortcut, callback = binding
            log(f"Raccourci global AppKit détecté : {shortcut}")
            callback()
        except Exception as exc:
            log(
                f"Traitement d'un événement clavier AppKit impossible : {exc}",
                logging.ERROR,
            )

    def _handle_global_event(self, event):
        self._handle_event(event)

    def _handle_local_event(self, event):
        self._handle_event(event)
        return event


def probe_native_hotkey_support(listener_factory=None) -> dict:
    """Install and remove the native key monitors once, reporting what happened.

    This exists for the packaged smoke test. Under the Hardened Runtime PyObjC
    compiles the Python handlers into libffi closures, and a bundle signed
    without ``com.apple.security.cs.allow-unsigned-executable-memory`` crashes
    the process on that allocation instead of raising. Running the path is
    therefore the check: a signed build that survives this call has working
    entitlements. Monitor installation itself is *not* asserted, because an
    un-trusted machine (any CI runner) legitimately refuses it.
    """
    if sys.platform != "darwin" and listener_factory is None:
        return {"ran": False, "reason": "non-darwin"}
    factory = listener_factory or _MacOSGlobalHotKeys
    try:
        listener = factory()
        listener.replace_bindings({})
        try:
            listener.start()
            installed = bool(listener.is_alive())
        finally:
            listener.stop()
        return {"ran": True, "monitors_installed": installed}
    except Exception as exc:
        return {"ran": True, "monitors_installed": False, "error": str(exc)}


class HotkeyService:
    """Own the sole process-wide macOS keyboard listener."""

    def __init__(self, listener_factory=_MacOSGlobalHotKeys):
        self._listener_factory = listener_factory
        self._listener = None
        self._owner_bindings = {}
        self._lock = threading.RLock()
        self._closed = False
        self._suspended = False
        self._last_error = ""

    @staticmethod
    def _combined_bindings(owner_bindings):
        combined = {}
        owners_by_shortcut = {}
        for owner, bindings in owner_bindings.items():
            for shortcut, callback in bindings.items():
                if shortcut in combined:
                    other = owners_by_shortcut[shortcut]
                    raise ValueError(
                        "Ce raccourci est déjà utilisé "
                        f"par {other} et ne peut pas être attribué à {owner}."
                    )
                combined[shortcut] = callback
                owners_by_shortcut[shortcut] = owner
        return combined

    def replace_owner_bindings(self, owner, bindings):
        """Atomically replace one owner's bindings without stopping the tap."""
        try:
            # Parse before changing live state so invalid input is atomic too.
            for shortcut in bindings:
                HotKey.parse(shortcut)
            with self._lock:
                candidate = dict(self._owner_bindings)
                if bindings:
                    candidate[str(owner)] = dict(bindings)
                else:
                    candidate.pop(str(owner), None)
                combined = self._combined_bindings(candidate)
                self._owner_bindings = candidate
                listener = self._listener
                if listener is not None and listener.is_alive():
                    listener.replace_bindings(combined)
            if combined and not self.ensure_started():
                return False, self._last_error
            self._last_error = ""
            log(
                "Configuration des raccourcis active : "
                + (", ".join(sorted(combined)) if combined else "aucun")
            )
            return True, ""
        except Exception as exc:
            self._last_error = str(exc)
            log(f"Configuration des raccourcis impossible : {exc}", logging.ERROR)
            return False, self._last_error

    def validate_owner_bindings(self, owner, bindings):
        try:
            for shortcut in bindings:
                HotKey.parse(shortcut)
            with self._lock:
                candidate = dict(self._owner_bindings)
                if bindings:
                    candidate[str(owner)] = dict(bindings)
                else:
                    candidate.pop(str(owner), None)
                self._combined_bindings(candidate)
            return True, ""
        except Exception as exc:
            return False, str(exc)

    def ensure_started(self):
        """Start only when absent or dead; never recycle a healthy event tap."""
        with self._lock:
            if self._closed:
                self._last_error = "Le service de raccourcis est fermé"
                return False
            if self._listener is not None and self._listener.is_alive():
                return True
            try:
                combined = self._combined_bindings(self._owner_bindings)
                listener = self._listener_factory()
                listener.replace_bindings(combined)
                listener.set_suspended(self._suspended)
                listener.start()
                listener.wait()
                if not listener.is_alive():
                    self._last_error = (
                        "Le service de raccourcis macOS n’a pas pu démarrer"
                    )
                    return False
                self._listener = listener
                self._last_error = ""
                log("Service global de raccourcis démarré")
                return True
            except Exception as exc:
                self._listener = None
                self._last_error = str(exc)
                log(
                    f"Démarrage du service de raccourcis impossible : {exc}",
                    logging.ERROR,
                )
                return False

    def restart(self):
        """Recreate native monitors after macOS changes TCC authorization."""
        with self._lock:
            if self._closed:
                self._last_error = "Le service de raccourcis est fermé"
                return False
            listener = self._listener
            self._listener = None
        if listener is not None:
            try:
                listener.stop()
                listener.join(timeout=1.0)
            except Exception as exc:
                self._last_error = str(exc)
                log(
                    "Recréation du service de raccourcis impossible : "
                    f"{exc}",
                    logging.ERROR,
                )
                return False
        log("Recréation des moniteurs clavier après autorisation macOS")
        return self.ensure_started()

    def suspend(self):
        with self._lock:
            self._suspended = True
            if self._listener is not None and self._listener.is_alive():
                self._listener.set_suspended(True)

    def resume(self):
        with self._lock:
            self._suspended = False
            if self._listener is not None and self._listener.is_alive():
                self._listener.set_suspended(False)

    @property
    def running(self):
        with self._lock:
            return bool(self._listener and self._listener.is_alive())

    @property
    def last_error(self):
        return self._last_error

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            listener = self._listener
            self._listener = None
        if listener is not None:
            try:
                listener.stop()
                listener.join(timeout=1.0)
            except Exception as exc:
                log(f"Arrêt du service de raccourcis incomplet : {exc}", logging.WARNING)


class HotkeyManager(QObject):
    hotkey_triggered = Signal()
    custom_hotkey_triggered = Signal()
    # Internal hop used to unwind the AppKit handler before any work starts.
    _dispatch_requested = Signal()

    def __init__(self, settings, custom_hotkey: bool = False, service=None):
        super().__init__()
        self.settings = settings
        self.custom_hotkey = custom_hotkey
        self.hotkey = ""
        self._dispatch_requested.connect(
            self._deliver_hotkey,
            Qt.ConnectionType.QueuedConnection,
        )
        self.service = service or HotkeyService()
        self._owns_service = service is None
        self._owner = "mode personnalisé" if custom_hotkey else "menu principal"
        self._binding_active = False
        self._last_register_error = ""
        self.register_hotkey()

    def _get_configured_hotkey(self) -> str:
        if self.custom_hotkey:
            return self.settings.get_custom_hotkey()
        return self.settings.get_hotkey()

    def _set_configured_hotkey(self, hotkey: str) -> None:
        if self.custom_hotkey:
            self.settings.set_custom_hotkey(hotkey)
        else:
            self.settings.set_hotkey(hotkey)

    def register_hotkey(self) -> bool:
        self.hotkey = self._get_configured_hotkey()
        normalized, error = normalize_hotkey(self.hotkey)
        if error:
            self._last_register_error = error
            log(
                f"Raccourci refusé pour {self._owner} ({self.hotkey}) : {error}",
                logging.ERROR,
            )
            return False
        success, error = self.service.replace_owner_bindings(
            self._owner,
            {normalized: self._on_hotkey_triggered},
        )
        self._binding_active = success
        self._last_register_error = error
        if success:
            log(f"Raccourci enregistré : {self.hotkey}")
        return success

    def unregister_hotkey(self) -> None:
        self.service.replace_owner_bindings(self._owner, {})
        self._binding_active = False

    def _on_hotkey_triggered(self) -> None:
        """Runs inside the native key handler; hand off and return at once.

        AppKit invokes the monitor handler on the main run loop, so a direct
        signal connection would run the whole menu, clipboard and activation
        sequence before the handler unwinds — with the run loop blocked
        throughout. The queued hop puts that work on the next event loop turn.
        """
        try:
            self._dispatch_requested.emit()
        except RuntimeError as exc:
            log(f"Signal de raccourci ignoré pendant la fermeture : {exc}")

    def _deliver_hotkey(self) -> None:
        try:
            if self.custom_hotkey:
                self.custom_hotkey_triggered.emit()
            else:
                self.hotkey_triggered.emit()
        except RuntimeError as exc:
            log(f"Signal de raccourci ignoré pendant la fermeture : {exc}")

    def set_hotkey(self, hotkey):
        previous = self._get_configured_hotkey()
        self._set_configured_hotkey(hotkey)
        if self.register_hotkey():
            return True
        attempted_error = self._last_register_error
        self._set_configured_hotkey(previous)
        self.register_hotkey()
        self._last_register_error = attempted_error
        return False

    def close(self) -> None:
        self.unregister_hotkey()
        if self._owns_service:
            self.service.close()

    @property
    def registered(self):
        return self._binding_active and self.service.running

    @property
    def last_register_error(self) -> str:
        return self._last_register_error


class PromptHotkeyManager(QObject):
    prompt_hotkey_triggered = Signal(str)
    # See HotkeyManager._on_hotkey_triggered for why this hop exists.
    _dispatch_requested = Signal(str)

    def __init__(self, settings, service=None):
        super().__init__()
        self.settings = settings
        self._dispatch_requested.connect(
            self.prompt_hotkey_triggered,
            Qt.ConnectionType.QueuedConnection,
        )
        self.service = service or HotkeyService()
        self._owns_service = service is None
        self._owner = "raccourcis des prompts"
        self._binding_active = False
        self._errors = {}
        self.refresh_hotkeys()

    @property
    def errors(self):
        return dict(self._errors)

    def refresh_hotkeys(self):
        self._errors = {}
        mapping = {}
        for prompt_id, prompt in sorted(
            self.settings.get_prompts().items(),
            key=lambda item: (item[1].get("position", 999), item[0]),
        ):
            hotkey = str(prompt.get("hotkey", "") or "").strip()
            if not hotkey:
                continue
            normalized, error = normalize_hotkey(hotkey)
            if error:
                self._errors[prompt_id] = error
                continue
            if normalized in mapping:
                self._errors[prompt_id] = (
                    "Ce raccourci est déjà utilisé par un autre prompt."
                )
                continue
            mapping[normalized] = (
                lambda selected_prompt_id=prompt_id: self._emit_prompt_hotkey(
                    selected_prompt_id
                )
            )
        success, error = self.service.replace_owner_bindings(self._owner, mapping)
        self._binding_active = success and bool(mapping)
        if not success:
            self._errors["registration"] = error
        return not self._errors, dict(self._errors)

    def _emit_prompt_hotkey(self, prompt_id):
        try:
            self._dispatch_requested.emit(prompt_id)
        except RuntimeError as exc:
            log(f"Raccourci de prompt ignoré pendant la fermeture : {exc}")

    def validate_prompts(self, prompts):
        mapping = {}
        errors = {}
        for prompt_id, prompt in prompts.items():
            hotkey = str(prompt.get("hotkey", "") or "").strip()
            if not hotkey:
                continue
            normalized, error = normalize_hotkey(hotkey)
            if error:
                errors[prompt_id] = error
                continue
            if normalized in mapping:
                errors[prompt_id] = (
                    "Ce raccourci est déjà utilisé par un autre prompt."
                )
                continue
            mapping[normalized] = lambda: None
        if errors:
            return False, errors
        success, error = self.service.validate_owner_bindings(self._owner, mapping)
        return success, {} if success else {"registration": error}

    def unregister_hotkeys(self) -> None:
        self.service.replace_owner_bindings(self._owner, {})
        self._binding_active = False

    def close(self) -> None:
        self.unregister_hotkeys()
        if self._owns_service:
            self.service.close()
