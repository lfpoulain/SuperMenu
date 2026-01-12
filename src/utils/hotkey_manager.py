#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ctypes
import ctypes.wintypes
import logging
import sys
import weakref
from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout
from src.utils.logger import log

_WM_HOTKEY = 0x0312
_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_NOREPEAT = 0x4000

_VK_BACK = 0x08
_VK_TAB = 0x09
_VK_RETURN = 0x0D
_VK_ESCAPE = 0x1B
_VK_SPACE = 0x20
_VK_PRIOR = 0x21
_VK_NEXT = 0x22
_VK_END = 0x23
_VK_HOME = 0x24
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28
_VK_INSERT = 0x2D
_VK_DELETE = 0x2E

_USER32 = ctypes.WinDLL("user32", use_last_error=True) if sys.platform.startswith("win") else None

if _USER32 is not None:
    _USER32.RegisterHotKey.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.wintypes.UINT, ctypes.wintypes.UINT]
    _USER32.RegisterHotKey.restype = ctypes.wintypes.BOOL
    _USER32.UnregisterHotKey.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
    _USER32.UnregisterHotKey.restype = ctypes.wintypes.BOOL
    _USER32.VkKeyScanW.argtypes = [ctypes.c_wchar]
    _USER32.VkKeyScanW.restype = ctypes.c_short


class _Win32HotkeyEventFilter(QAbstractNativeEventFilter):
    def __init__(self, registry):
        super().__init__()
        self._registry = registry

    def nativeEventFilter(self, eventType, message):
        try:
            try:
                if isinstance(eventType, (bytes, bytearray)):
                    event_type = bytes(eventType).decode(errors="ignore")
                else:
                    event_type = bytes(eventType).decode(errors="ignore")
            except Exception:
                event_type = str(eventType)

            if event_type not in ("windows_generic_MSG", "windows_dispatcher_MSG"):
                return False, 0

            msg = ctypes.wintypes.MSG.from_address(int(message))
            if int(msg.message) != _WM_HOTKEY:
                return False, 0

            log(f"WM_HOTKEY received (id={int(msg.wParam)})", logging.INFO)
            self._registry.dispatch(int(msg.wParam))
            return True, 0
        except Exception:
            return False, 0


class _Win32HotkeyRegistry:
    def __init__(self):
        self._installed = False
        self._filter = None
        self._next_id = 1
        self._callbacks = {}

    def ensure_installed(self):
        if self._installed:
            return True

        app = QCoreApplication.instance()
        if app is None:
            return False

        self._filter = _Win32HotkeyEventFilter(self)
        app.installNativeEventFilter(self._filter)
        self._installed = True
        return True

    def register(self, modifiers, vk, callback):
        if _USER32 is None:
            return None, "Windows hotkeys are not available on this platform"

        if not self.ensure_installed():
            return None, "QCoreApplication is not initialized"

        hotkey_id = self._next_id
        self._next_id += 1

        ok = bool(_USER32.RegisterHotKey(None, hotkey_id, int(modifiers) | _MOD_NOREPEAT, int(vk)))
        if not ok:
            err = ctypes.get_last_error()
            if int(err) == 1409:
                return None, "Ce raccourci est déjà utilisé par une autre application (win32 error 1409)"
            if int(err) == 87:
                return None, "Raccourci invalide (win32 error 87)"
            return None, f"RegisterHotKey failed (win32 error {err})"

        self._callbacks[int(hotkey_id)] = callback
        return hotkey_id, ""

    def unregister(self, hotkey_id):
        if _USER32 is None:
            return

        if hotkey_id is None:
            return

        self._callbacks.pop(int(hotkey_id), None)
        try:
            _USER32.UnregisterHotKey(None, int(hotkey_id))
        except Exception:
            pass

    def dispatch(self, hotkey_id):
        callback = self._callbacks.get(int(hotkey_id))
        if callback is None:
            log(f"WM_HOTKEY received for unknown id={int(hotkey_id)}", logging.WARNING)
            return
        try:
            callback()
        except Exception as e:
            log(f"Error while handling WM_HOTKEY: {e}", logging.ERROR)


_REGISTRY = _Win32HotkeyRegistry()


def _parse_hotkey_to_win32(hotkey):
    if not hotkey or not isinstance(hotkey, str):
        return None, None, "Le raccourci ne peut pas être vide"

    hotkey = hotkey.strip()
    parts = [p.strip() for p in hotkey.split("+") if p.strip()]
    if len(parts) < 2:
        return None, None, "Le raccourci doit contenir Ctrl, Alt ou Shift"

    modifiers = 0
    seen = set()
    key_token = parts[-1]

    key_token_l = key_token.lower()
    if key_token_l in ("ctrl", "control", "alt", "shift", "win", "windows", "meta", "cmd"):
        return None, None, "Le raccourci doit contenir une touche (autre qu'un modificateur)"

    for p in parts[:-1]:
        pl = p.lower()
        if pl == "control":
            pl = "ctrl"
        if pl in seen:
            return None, None, "Le raccourci contient des touches dupliquées"
        seen.add(pl)

        if pl == "ctrl":
            modifiers |= _MOD_CONTROL
        elif pl == "alt":
            modifiers |= _MOD_ALT
        elif pl == "shift":
            modifiers |= _MOD_SHIFT
        elif pl in ("win", "windows", "meta", "cmd"):
            return None, None, "La touche Win n'est pas autorisée"
        else:
            return None, None, f"Modificateur inconnu: {p}"

    if modifiers == 0:
        return None, None, "Le raccourci doit contenir Ctrl, Alt ou Shift"

    key_l = key_token.lower()
    vk_map = {
        "backspace": _VK_BACK,
        "tab": _VK_TAB,
        "enter": _VK_RETURN,
        "return": _VK_RETURN,
        "esc": _VK_ESCAPE,
        "escape": _VK_ESCAPE,
        "space": _VK_SPACE,
        "pageup": _VK_PRIOR,
        "pagedown": _VK_NEXT,
        "end": _VK_END,
        "home": _VK_HOME,
        "left": _VK_LEFT,
        "up": _VK_UP,
        "right": _VK_RIGHT,
        "down": _VK_DOWN,
        "insert": _VK_INSERT,
        "delete": _VK_DELETE,
        "del": _VK_DELETE,
    }

    if key_l in vk_map:
        return modifiers, vk_map[key_l], ""

    if len(key_token) == 1:
        if _USER32 is None:
            return None, None, "Windows hotkeys are not available on this platform"

        vk_and_shift = int(_USER32.VkKeyScanW(key_token))
        if vk_and_shift == -1:
            return None, None, f"Touche non supportée: {key_token}"

        vk = vk_and_shift & 0xFF
        shift_state = (vk_and_shift >> 8) & 0xFF
        if shift_state & 0x01:
            modifiers |= _MOD_SHIFT
        if shift_state & 0x02:
            modifiers |= _MOD_CONTROL
        if shift_state & 0x04:
            modifiers |= _MOD_ALT
        return modifiers, vk, ""

    return None, None, f"Touche non supportée: {key_token}"


class HotkeyRecorderDialog(QDialog):
    """Dialogue pour enregistrer un nouveau raccourci clavier"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Définir un nouveau raccourci")
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() | Qt.Window)  # Ajouter le bouton de fermeture
        
        self.layout = QVBoxLayout(self)
        
        # Instructions
        self.label = QLabel("Appuyez sur la combinaison de touches que vous souhaitez utiliser comme raccourci.")
        self.layout.addWidget(self.label)
        
        # Affichage du raccourci actuel
        self.current_hotkey_label = QLabel("⏳ Appuyez sur une combinaison de touches...")
        self.current_hotkey_label.setObjectName("hotkeyDisplay")
        self.current_hotkey_label.setStyleSheet("font-weight: bold; font-size: 16px; padding: 10px; border-radius: 5px;")
        self.current_hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.current_hotkey_label)
        
        # Boutons
        self.button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.clicked.connect(self.reject)
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setEnabled(False)
        
        self.button_layout.addWidget(self.cancel_button)
        self.button_layout.addWidget(self.ok_button)
        self.layout.addLayout(self.button_layout)
        
        # Variables pour stocker le raccourci
        self.recorded_hotkey = ""
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
 
    def showEvent(self, event):
        try:
            self.grabKeyboard()
        except Exception:
            pass
        super().showEvent(event)
 
    def keyPressEvent(self, event: QKeyEvent):
        try:
            if event.isAutoRepeat():
                return
 
            self.current_hotkey_label.setProperty("state", "normal")
            self.current_hotkey_label.setStyleSheet("font-weight: bold; font-size: 16px; padding: 10px; border-radius: 5px;")
 
            mods = event.modifiers()
            if mods & Qt.KeyboardModifier.MetaModifier:
                self.current_hotkey_label.setText("⚠️ La touche Win n'est pas autorisée")
                self.ok_button.setEnabled(False)
                return
 
            parts = []
            if mods & Qt.KeyboardModifier.ControlModifier:
                parts.append("Ctrl")
            if mods & Qt.KeyboardModifier.AltModifier:
                parts.append("Alt")
            if mods & Qt.KeyboardModifier.ShiftModifier:
                parts.append("Shift")
 
            key = event.key()
            if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
                if parts:
                    self.current_hotkey_label.setText("+".join(parts) + "+...")
                return
 
            if not parts:
                self.current_hotkey_label.setText("⚠️ Utilise Ctrl, Alt ou Shift")
                self.ok_button.setEnabled(False)
                return
 
            key_text = (event.text() or "").strip()
            if key_text == "+":
                self.current_hotkey_label.setText("⚠️ La touche '+' n'est pas supportée")
                self.ok_button.setEnabled(False)
                return
 
            if key_text and len(key_text) == 1 and key_text.isprintable():
                key_part = key_text
            else:
                key_map = {
                    Qt.Key.Key_Space: "Space",
                    Qt.Key.Key_Tab: "Tab",
                    Qt.Key.Key_Backspace: "Backspace",
                    Qt.Key.Key_Return: "Enter",
                    Qt.Key.Key_Enter: "Enter",
                    Qt.Key.Key_Escape: "Esc",
                    Qt.Key.Key_Delete: "Delete",
                    Qt.Key.Key_Insert: "Insert",
                    Qt.Key.Key_Home: "Home",
                    Qt.Key.Key_End: "End",
                    Qt.Key.Key_PageUp: "PageUp",
                    Qt.Key.Key_PageDown: "PageDown",
                    Qt.Key.Key_Left: "Left",
                    Qt.Key.Key_Right: "Right",
                    Qt.Key.Key_Up: "Up",
                    Qt.Key.Key_Down: "Down",
                }
                key_part = key_map.get(Qt.Key(key))
 
            if not key_part:
                self.current_hotkey_label.setText("⚠️ Touche non supportée")
                self.ok_button.setEnabled(False)
                return
 
            hotkey = "+".join(parts + [key_part])
            self.current_hotkey_label.setText(f"✅ {hotkey}")
            self.current_hotkey_label.setProperty("state", "success")
            self.recorded_hotkey = hotkey
            self.ok_button.setEnabled(True)
        except Exception:
            self.ok_button.setEnabled(False)
    
    def get_hotkey(self):
        """Retourne le raccourci enregistré"""
        return self.recorded_hotkey
    
    def closeEvent(self, event):
        """Nettoyer les hooks clavier à la fermeture"""
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        super().closeEvent(event)

class HotkeyManager(QObject):
    """Manage hotkeys for the application"""
    
    # Signals publics
    hotkey_triggered = Signal()
    voice_hotkey_triggered = Signal()
    screenshot_hotkey_triggered = Signal()

    def __init__(self, settings, voice_hotkey=False, screenshot_hotkey=False):
        super().__init__()
        self.settings = settings
        self.hotkey = ""
        self.registered = False
        self.voice_hotkey = voice_hotkey
        self.screenshot_hotkey = screenshot_hotkey
        self._hotkey_id = None
        self._last_register_error = ""

        app = QCoreApplication.instance()
        if app is not None:
            try:
                app.aboutToQuit.connect(self.close)
            except Exception:
                pass

        self.register_hotkey()

    def _get_configured_hotkey(self):
        if self.voice_hotkey:
            return self.settings.get_voice_hotkey()
        if self.screenshot_hotkey:
            return self.settings.get_screenshot_hotkey()
        return self.settings.get_hotkey()

    def _set_configured_hotkey(self, hotkey):
        if self.voice_hotkey:
            self.settings.set_voice_hotkey(hotkey)
            return
        if self.screenshot_hotkey:
            self.settings.set_screenshot_hotkey(hotkey)
            return
        self.settings.set_hotkey(hotkey)

    def register_hotkey(self):
        self.unregister_hotkey()

        self.hotkey = self._get_configured_hotkey()
        self._last_register_error = ""

        modifiers, vk, err = _parse_hotkey_to_win32(self.hotkey)
        if err:
            self._last_register_error = err
            log(f"No valid hotkey configured: {err}", logging.WARNING)
            return False

        inst_ref = weakref.ref(self)

        def _cb():
            inst = inst_ref()
            if inst is None:
                return
            inst._on_hotkey_triggered()

        hotkey_id, reg_err = _REGISTRY.register(modifiers, vk, _cb)
        if reg_err:
            self._last_register_error = reg_err
            log(f"Error registering hotkey '{self.hotkey}': {reg_err}", logging.ERROR)
            return False

        self._hotkey_id = hotkey_id
        self.registered = True
        log(f"Registering hotkey: {self.hotkey}", logging.INFO)
        return True

    def unregister_hotkey(self):
        if self._hotkey_id is not None:
            _REGISTRY.unregister(self._hotkey_id)
            self._hotkey_id = None
        self.registered = False

    def _on_hotkey_triggered(self):
        try:
            if self.voice_hotkey:
                self.voice_hotkey_triggered.emit()
            elif self.screenshot_hotkey:
                self.screenshot_hotkey_triggered.emit()
            else:
                self.hotkey_triggered.emit()
        except Exception as e:
            log(f"Error emitting hotkey signal: {e}", logging.ERROR)

    def close(self):
        self.unregister_hotkey()
    
    def show_hotkey_recorder(self):
        """Show a dialog to record a new hotkey"""
        old_hotkey = self._get_configured_hotkey()
        dialog = HotkeyRecorderDialog()
        result = dialog.exec()

        if result != QDialog.Accepted or not dialog.recorded_hotkey:
            return False

        self._set_configured_hotkey(dialog.recorded_hotkey)
        if self.register_hotkey():
            return True

        self._set_configured_hotkey(old_hotkey)
        self.register_hotkey()
        QMessageBox.warning(
            None,
            "Erreur",
            f"Impossible d'enregistrer le raccourci '{dialog.recorded_hotkey}'.\n\n{self._last_register_error}",
        )
        return False
    
    def get_new_hotkey(self):
        """Get a new hotkey from the user"""
        dialog = HotkeyRecorderDialog()
        result = dialog.exec()
        
        if result == QDialog.Accepted and dialog.recorded_hotkey:
            return dialog.recorded_hotkey
        
        return None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
