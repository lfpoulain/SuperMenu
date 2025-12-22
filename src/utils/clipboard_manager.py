#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Context manager pour une gestion robuste du presse-papiers Windows.
"""
import win32clipboard
import win32con
import logging
from src.utils.logger import log


class ClipboardManager:
    """Context manager pour gérer le presse-papiers de manière sûre."""
    
    def __init__(self, max_retries=3):
        """
        Initialise le gestionnaire de presse-papiers.
        
        Args:
            max_retries (int): Nombre maximum de tentatives d'ouverture du presse-papiers
        """
        self.max_retries = max_retries
        self.clipboard_opened = False
        
    def __enter__(self):
        """Ouvre le presse-papiers avec gestion des erreurs et retry."""
        for attempt in range(self.max_retries):
            try:
                win32clipboard.OpenClipboard()
                self.clipboard_opened = True
                return self
            except Exception as e:
                if attempt == self.max_retries - 1:
                    log(f"Failed to open clipboard after {self.max_retries} attempts: {e}", logging.ERROR)
                    raise
                # Petit délai avant la prochaine tentative
                import time
                time.sleep(0.1)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ferme le presse-papiers de manière sûre."""
        if self.clipboard_opened:
            try:
                win32clipboard.CloseClipboard()
                self.clipboard_opened = False
            except Exception as e:
                log(f"Error closing clipboard: {e}", logging.WARNING)
        # Ne pas supprimer l'exception si elle existe
        return False
    
    def get_text(self):
        """
        Récupère le texte du presse-papiers.
        
        Returns:
            str or None: Le texte du presse-papiers ou None si indisponible
        """
        if not self.clipboard_opened:
            raise RuntimeError("Clipboard not opened. Use 'with ClipboardManager() as cm:' pattern.")
        
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return None
        except Exception as e:
            log(f"Error getting clipboard text: {e}", logging.WARNING)
            return None
    
    def set_text(self, text):
        """
        Définit le texte du presse-papiers.
        
        Args:
            text (str): Le texte à copier dans le presse-papiers
        """
        if not self.clipboard_opened:
            raise RuntimeError("Clipboard not opened. Use 'with ClipboardManager() as cm:' pattern.")
        
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
        except Exception as e:
            log(f"Error setting clipboard text: {e}", logging.ERROR)
            raise
    
    @staticmethod
    def get_clipboard_text_safe():
        """
        Méthode statique pour récupérer rapidement le texte du presse-papiers.
        
        Returns:
            str or None: Le texte du presse-papiers ou None en cas d'erreur
        """
        try:
            with ClipboardManager() as cm:
                return cm.get_text()
        except Exception as e:
            log(f"Error in get_clipboard_text_safe: {e}", logging.ERROR)
            return None
    
    @staticmethod
    def set_clipboard_text_safe(text):
        """
        Méthode statique pour définir rapidement le texte du presse-papiers.
        
        Args:
            text (str): Le texte à copier
            
        Returns:
            bool: True si succès, False sinon
        """
        try:
            with ClipboardManager() as cm:
                cm.set_text(text)
                return True
        except Exception as e:
            log(f"Error in set_clipboard_text_safe: {e}", logging.ERROR)
            return False
