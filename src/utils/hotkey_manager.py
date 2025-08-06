#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import keyboard
import time
import logging
from PySide6.QtCore import QObject, Signal, QTimer, Qt
from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QApplication
from utils.logger import log

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
        self.current_hotkey_label = QLabel("Appuyez sur une combinaison de touches...")
        self.current_hotkey_label.setStyleSheet("font-weight: bold; font-size: 16px; padding: 10px; color: #000000; background-color: #d0d0d0; border: 1px solid #a0a0a0; border-radius: 5px;")
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
        self.key_recorder = keyboard.hook(self._on_key_press)
    
    def _on_key_press(self, event):
        """Gérer l'événement de pression de touche"""
        # Réinitialiser le style
        self.current_hotkey_label.setStyleSheet("font-weight: bold; font-size: 16px; padding: 10px; color: #000000; background-color: #d0d0d0; border: 1px solid #a0a0a0; border-radius: 5px;")
        
        # Collecter les modificateurs
        modifiers = []
        if keyboard.is_pressed('ctrl'):
            modifiers.append('Ctrl')
        if keyboard.is_pressed('alt'):
            modifiers.append('Alt')
        if keyboard.is_pressed('shift'):
            modifiers.append('Shift')
            
        # Ajouter la touche principale
        key_name = event.name
        
        # Construire le raccourci complet
        if len(modifiers) == 0:
            # Raccourci sans modificateur
            hotkey = key_name
            
            # Avertissement pour les touches simples qui pourraient interférer avec la saisie normale
            if len(key_name) == 1 and key_name.isalnum():
                self.current_hotkey_label.setText(f"Attention: La touche '{key_name}' pourrait interférer avec la saisie normale")
                self.current_hotkey_label.setStyleSheet("font-weight: bold; font-size: 16px; padding: 10px; color: #ff7700; background-color: #fff0d0; border: 1px solid #ffc070; border-radius: 5px;")
            else:
                self.current_hotkey_label.setText(hotkey)
        else:
            # Raccourci avec modificateurs
            hotkey = '+'.join(modifiers) + '+' + key_name
            self.current_hotkey_label.setText(hotkey)
            
        self.recorded_hotkey = hotkey
        self.ok_button.setEnabled(True)
    
    def get_hotkey(self):
        """Retourne le raccourci enregistré"""
        return self.recorded_hotkey
    
    def closeEvent(self, event):
        """Nettoyer les hooks clavier à la fermeture"""
        keyboard.unhook(self.key_recorder)
        super().closeEvent(event)

class HotkeyManager(QObject):
    """Manage global hotkeys"""
    
    # Signal emitted when the hotkey is triggered
    hotkey_triggered = Signal()
    
    # Signal emitted when the voice hotkey is triggered
    voice_hotkey_triggered = Signal()
    
    # Signal emitted when the screenshot hotkey is triggered
    screenshot_hotkey_triggered = Signal()
    
    def __init__(self, settings, voice_hotkey=False, screenshot_hotkey=False):
        super().__init__()
        self.settings = settings
        self.registered = False
        self.voice_hotkey = voice_hotkey
        self.screenshot_hotkey = screenshot_hotkey
        self.current_keys = set()
        self.last_hotkey_time = 0
        self.key_listener_hook = None  # Initialiser la variable pour stocker le hook

        # Timer pour nettoyer les touches coincées
        # Utiliser `self` comme parent pour s'assurer que le timer est
        # automatiquement détruit avec le gestionnaire.
        self.cleanup_timer = QTimer(self)
        self.cleanup_timer.setInterval(5000)  # 5 secondes d'inactivité
        self.cleanup_timer.timeout.connect(self._reset_stuck_keys)
        self.cleanup_timer.start()
        
        # Register the hotkey
        self.register_hotkey()
    
    def register_hotkey(self):
        """Register the global hotkey"""
        # Unregister any existing hotkey
        self.unregister_hotkey()
        
        # Get the hotkey from settings
        if self.voice_hotkey:
            self.hotkey = self.settings.get_voice_hotkey()
        elif self.screenshot_hotkey:
            self.hotkey = self.settings.get_screenshot_hotkey()
        else:
            self.hotkey = self.settings.get_hotkey()
        
        if not self.hotkey:
            log("No hotkey configured")
            return

        try:
            # Register the hotkey
            log(f"Registering hotkey: {self.hotkey}", logging.INFO)

            # Hook pour capturer toutes les touches
            self.key_listener_hook = keyboard.hook(self._on_any_key)  # Stocker la référence du hook
            self.registered = True
            # S'assurer que le timer est actif après (ré)enregistrement
            self.cleanup_timer.start()

        except Exception as e:
            log(f"Error registering hotkey: {e}", logging.ERROR)
    
    def unregister_hotkey(self):
        """Unregister the global hotkey"""
        # Arrêter le timer de nettoyage lorsqu'on se désinscrit
        if self.cleanup_timer.isActive():
            self.cleanup_timer.stop()
        if self.registered and self.key_listener_hook:
            try:
                # Unhook the keyboard listener
                keyboard.unhook(self.key_listener_hook)  # Utiliser la référence spécifique du hook
                self.key_listener_hook = None
                self.registered = False
                log("Hotkey unregistered")
            except Exception as e:
                log(f"Error unregistering hotkey: {e}", logging.ERROR)
        elif self.registered:
            # Fallback ou cas où key_listener_hook n'est pas défini mais registered est True
            # Cela ne devrait pas arriver avec la logique actuelle, mais c'est une sécurité
            try:
                keyboard.unhook_all() # Tentative de nettoyage général si le hook spécifique n'est pas connu
                self.registered = False
                log("Fallback: All hotkeys unregistered due to missing specific hook reference", logging.WARNING)
            except Exception as e:
                log(f"Error during fallback unregister_hotkey: {e}", logging.ERROR)

    def close(self):
        """Stopper le timer et nettoyer les raccourcis."""
        self.unregister_hotkey()

    
    def _on_any_key(self, event):
        """Handle key events to detect hotkey combinations"""
        # Redémarrer le timer de nettoyage à chaque événement
        self.cleanup_timer.start()

        # Obtenir le nom de la touche
        key_name = event.name.lower()
        
        # Ignorer certaines touches spéciales
        if key_name in ['left ctrl', 'right ctrl']:
            key_name = 'ctrl'
        elif key_name in ['left alt', 'right alt']:
            key_name = 'alt'
        elif key_name in ['left shift', 'right shift']:
            key_name = 'shift'
        
        # Gérer les événements de touche
        if event.event_type == keyboard.KEY_DOWN:
            # Ajouter la touche à l'ensemble des touches enfoncées
            if key_name not in self.current_keys:
                self.current_keys.add(key_name)
                self._check_hotkey()
        elif event.event_type == keyboard.KEY_UP:
            # Retirer la touche de l'ensemble des touches enfoncées
            if key_name in self.current_keys:
                self.current_keys.remove(key_name)

    def _reset_stuck_keys(self):
        """Réinitialise les touches si aucune activité n'est détectée."""
        if self.current_keys:
            log("Resetting stuck keys", logging.DEBUG)
            self.current_keys.clear()
                
    def _check_hotkey(self):
        """Check if the current keys match the hotkey"""
        # Obtenir le raccourci configuré
        if self.voice_hotkey:
            configured_hotkey = self.settings.get_voice_hotkey().lower()
        elif self.screenshot_hotkey:
            configured_hotkey = self.settings.get_screenshot_hotkey().lower()
        else:
            configured_hotkey = self.settings.get_hotkey().lower()
        
        # Vérifier s'il s'agit d'un raccourci sans modificateur (une seule touche)
        if "+" not in configured_hotkey:
            # Pour les raccourcis à touche unique, vérifier si la touche est enfoncée
            if configured_hotkey in self.current_keys and len(self.current_keys) == 1:
                # Éviter les déclenchements multiples en vérifiant le temps écoulé
                current_time = time.time()
                if current_time - self.last_hotkey_time > 0.5:  # 500ms de délai
                    self.last_hotkey_time = current_time
                    self._hotkey_triggered()
            return
        
        # Pour les raccourcis avec modificateurs
        # Diviser le raccourci en touches individuelles
        hotkey_parts = configured_hotkey.split("+")
        hotkey_parts = [part.strip().lower() for part in hotkey_parts]
        
        # Vérifier si toutes les touches du raccourci sont enfoncées
        if all(part in self.current_keys for part in hotkey_parts) and len(self.current_keys) == len(hotkey_parts):
            # Éviter les déclenchements multiples en vérifiant le temps écoulé
            current_time = time.time()
            if current_time - self.last_hotkey_time > 0.5:  # 500ms de délai
                self.last_hotkey_time = current_time
                self._hotkey_triggered()
    
    def _hotkey_triggered(self):
        """Handle hotkey trigger"""
        # Émettre le signal approprié en fonction du type de raccourci
        if self.voice_hotkey:
            log("Voice hotkey triggered", logging.DEBUG)
            self.voice_hotkey_triggered.emit()
        elif self.screenshot_hotkey:
            log("Screenshot hotkey triggered", logging.DEBUG)
            self.screenshot_hotkey_triggered.emit()
        else:
            log("Hotkey triggered", logging.DEBUG)
            self.hotkey_triggered.emit()
    
    def show_hotkey_recorder(self):
        """Show a dialog to record a new hotkey"""
        dialog = HotkeyRecorderDialog()
        result = dialog.exec()
        
        if result == QDialog.Accepted and dialog.recorded_hotkey:
            # Save the new hotkey
            if self.voice_hotkey:
                self.settings.set_voice_hotkey(dialog.recorded_hotkey)
            elif self.screenshot_hotkey:
                self.settings.set_screenshot_hotkey(dialog.recorded_hotkey)
            else:
                self.settings.set_hotkey(dialog.recorded_hotkey)
            
            # Re-register with the new hotkey
            self.register_hotkey()
            return True
        
        return False
    
    def get_new_hotkey(self):
        """Get a new hotkey from the user"""
        dialog = HotkeyRecorderDialog()
        result = dialog.exec()
        
        if result == QDialog.Accepted and dialog.recorded_hotkey:
            return dialog.recorded_hotkey
        
        return None
    
    def __del__(self):
        """Clean up when the object is deleted"""
        self.close()
