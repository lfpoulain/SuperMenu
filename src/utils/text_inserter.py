#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module pour insérer du texte à la position du curseur dans SuperMenu.
"""
import time
from pynput.keyboard import Controller, Key
from src.utils.logger import log
from src.utils.clipboard_manager import ClipboardManager
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
    
    def insert_text(self, text):
        """
        Insère le texte à la position actuelle du curseur en utilisant le presse-papiers.
        
        Args:
            text (str): Le texte à insérer
        """
        if not text:
            log("Aucun texte à insérer")
            return
            
        # Sauvegarder le contenu actuel du presse-papiers
        original_clipboard = ClipboardManager.get_clipboard_text_safe()
        
        try:
            # Copier le nouveau texte dans le presse-papiers
            if not ClipboardManager.set_clipboard_text_safe(text):
                log("Échec de la copie dans le presse-papiers")
                return
            
            # Attendre que le presse-papiers soit prêt
            time.sleep(CLIPBOARD_COPY_DELAY)
            
            # Simuler Ctrl+V pour coller le texte
            self._press_keyboard_shortcut(Key.ctrl, 'v')
            
            # Attendre que le collage soit terminé
            time.sleep(CLIPBOARD_PASTE_DELAY)
            log(f"Texte inséré: {text[:50]}{'...' if len(text) > 50 else ''}")
            
            # Délai supplémentaire avant de restaurer le clipboard pour éviter les interférences
            time.sleep(CLIPBOARD_RESTORE_DELAY)
        finally:
            # Restaurer le contenu original du presse-papiers
            if original_clipboard is not None:
                ClipboardManager.set_clipboard_text_safe(original_clipboard)
    
    # Méthodes obsolètes - conservées pour compatibilité descendante
    def _get_clipboard_data(self):
        """Récupère le contenu actuel du presse-papiers (obsolète - utiliser ClipboardManager)."""
        return ClipboardManager.get_clipboard_text_safe()
    
    def _set_clipboard_data(self, data):
        """Définit le contenu du presse-papiers (obsolète - utiliser ClipboardManager)."""
        ClipboardManager.set_clipboard_text_safe(data)
