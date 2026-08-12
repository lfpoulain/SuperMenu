"""Global macOS hotkeys and the Qt shortcut recorder dialog."""

from __future__ import annotations

import logging
import re
import sys

from pynput.keyboard import GlobalHotKeys
from PySide6.QtCore import QCoreApplication, QObject, Signal, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.utils.logger import log
from src.utils.permissions import (
    accessibility_is_trusted,
    input_monitoring_is_trusted,
)


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

    def showEvent(self, event):
        try:
            self.grabKeyboard()
        except Exception:
            pass
        super().showEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.isAutoRepeat():
            return
        modifiers = event.modifiers()
        parts = []
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("Cmd")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("Option")
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")

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

    def closeEvent(self, event):
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        super().closeEvent(event)


class HotkeyManager(QObject):
    hotkey_triggered = Signal()
    custom_hotkey_triggered = Signal()

    def __init__(self, settings, custom_hotkey: bool = False):
        super().__init__()
        self.settings = settings
        self.custom_hotkey = custom_hotkey
        self.hotkey = ""
        self.registered = False
        self._listener = None
        self._last_register_error = ""
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.close)
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
        self.unregister_hotkey()
        self.hotkey = self._get_configured_hotkey()
        normalized, error = normalize_hotkey(self.hotkey)
        if error:
            self._last_register_error = error
            return False
        if sys.platform == "darwin" and not accessibility_is_trusted():
            self._last_register_error = "Autorisation Accessibilité requise"
            return False
        if sys.platform == "darwin" and not input_monitoring_is_trusted():
            self._last_register_error = "Autorisation Surveillance de l’entrée requise"
            return False
        try:
            self._listener = GlobalHotKeys({normalized: self._on_hotkey_triggered})
            self._listener.start()
            self.registered = True
            self._last_register_error = ""
            log(f"Raccourci enregistré : {self.hotkey}")
            return True
        except Exception as exc:
            self._listener = None
            self._last_register_error = str(exc)
            log(f"Impossible d'enregistrer {self.hotkey}: {exc}", logging.ERROR)
            return False

    def unregister_hotkey(self) -> None:
        listener = self._listener
        self._listener = None
        self.registered = False
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    def _on_hotkey_triggered(self) -> None:
        if self.custom_hotkey:
            self.custom_hotkey_triggered.emit()
        else:
            self.hotkey_triggered.emit()

    def show_hotkey_recorder(self, parent=None) -> bool:
        previous = self._get_configured_hotkey()
        dialog = HotkeyRecorderDialog(parent)
        if dialog.exec() != QDialog.Accepted or not dialog.recorded_hotkey:
            return False
        self._set_configured_hotkey(dialog.recorded_hotkey)
        if self.register_hotkey():
            return True
        self._set_configured_hotkey(previous)
        self.register_hotkey()
        QMessageBox.warning(
            parent,
            "Raccourci non enregistré",
            self._last_register_error,
        )
        return False

    def close(self) -> None:
        self.unregister_hotkey()


class PromptHotkeyManager(QObject):
    prompt_hotkey_triggered = Signal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._listener = None
        self._errors = {}
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.close)
        self.refresh_hotkeys()

    @property
    def errors(self):
        return dict(self._errors)

    def refresh_hotkeys(self):
        self.unregister_hotkeys()
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
            mapping[normalized] = (
                lambda selected_prompt_id=prompt_id: self.prompt_hotkey_triggered.emit(
                    selected_prompt_id
                )
            )
        if not mapping:
            return True, {}
        if sys.platform == "darwin" and not accessibility_is_trusted():
            self._errors["permissions"] = "Autorisation Accessibilité requise"
            return False, dict(self._errors)
        if sys.platform == "darwin" and not input_monitoring_is_trusted():
            self._errors["permissions"] = (
                "Autorisation Surveillance de l’entrée requise"
            )
            return False, dict(self._errors)
        try:
            self._listener = GlobalHotKeys(mapping)
            self._listener.start()
        except Exception as exc:
            self._errors["registration"] = str(exc)
        return not self._errors, dict(self._errors)

    def unregister_hotkeys(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    def close(self) -> None:
        self.unregister_hotkeys()
