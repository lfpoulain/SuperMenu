#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module pour insérer du texte à la position du curseur dans SuperMenu.
"""
import time
from pynput.keyboard import Controller, Key
from src.utils.logger import log
from src.utils.clipboard_manager import ClipboardManager
from src.utils.window_target import PasteTarget
from src.audio.audio_config import CLIPBOARD_PASTE_DELAY, CLIPBOARD_COPY_DELAY, CLIPBOARD_RESTORE_DELAY

class TextInserter:
    """Classe pour insérer du texte à la position actuelle du curseur."""
    
    def __init__(self):
        """Initialise l'inserteur de texte."""
        self.keyboard = Controller()

    def _press_keyboard_shortcut(self, *keys):
        pressed = []
        try:
            for key in keys:
                self.keyboard.press(key)
                pressed.append(key)
        finally:
            for key in reversed(pressed):
                try:
                    self.keyboard.release(key)
                except Exception:
                    pass
    
    def insert_text(self, text, target=None):
        """
        Insère le texte à la position actuelle du curseur en utilisant le presse-papiers.
        
        Args:
            text (str): Le texte à insérer
        """
        if not text:
            log("Aucun texte à insérer")
            return False

        if target is None:
            target = PasteTarget.capture(allow_current_process=True)
        if target is None or not target.activate_and_verify():
            log("Insertion annulée: la cible de collage n'est plus sûre")
            return False

        original_clipboard = ClipboardManager.capture_snapshot()
        
        try:
            # Copier le nouveau texte dans le presse-papiers
            if not ClipboardManager.set_clipboard_text_safe(text):
                log("Échec de la copie dans le presse-papiers")
                return False
            
            # Attendre que le presse-papiers soit prêt
            time.sleep(CLIPBOARD_COPY_DELAY)

            # Recheck after manipulating the clipboard: focus may have changed
            # during the delay or because another application came forward.
            if not target.activate_and_verify():
                log("Insertion annulée: la cible a changé avant le collage")
                return False
            
            # Simuler Ctrl+V pour coller le texte
            self._press_keyboard_shortcut(Key.ctrl, 'v')
            
            # Attendre que le collage soit terminé
            time.sleep(CLIPBOARD_PASTE_DELAY)
            log(f"Texte inséré ({len(text)} caractères)")
            
            # Délai supplémentaire avant de restaurer le clipboard pour éviter les interférences
            time.sleep(CLIPBOARD_RESTORE_DELAY)
            return True
        finally:
            ClipboardManager.restore_if_unchanged(original_clipboard, text)
