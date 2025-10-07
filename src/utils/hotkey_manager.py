#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import keyboard
import time
import logging
import threading
from PySide6.QtCore import QObject, Signal, QTimer, Qt, QMetaObject, Q_ARG
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
        self.key_recorder = None
        try:
            self.key_recorder = keyboard.hook(self._on_key_press)
        except Exception as e:
            log(f"Error setting up keyboard hook in recorder dialog: {e}", logging.ERROR)
    
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
        if self.key_recorder is not None:
            try:
                keyboard.unhook(self.key_recorder)
                self.key_recorder = None
            except Exception as e:
                log(f"Error unhooking keyboard in recorder dialog: {e}", logging.ERROR)
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
        self._lock = threading.Lock()  # Thread safety pour current_keys
        self._is_processing_trigger = False  # Éviter les déclenchements simultanés
        self._hook_error_count = 0  # Compteur d'erreurs pour récupération automatique
        self._max_errors = 5  # Nombre maximum d'erreurs avant tentative de récupération

        # Timer pour nettoyer les touches coincées
        # Utiliser `self` comme parent pour s'assurer que le timer est
        # automatiquement détruit avec le gestionnaire.
        self.cleanup_timer = QTimer(self)
        self.cleanup_timer.setInterval(5000)  # 5 secondes d'inactivité
        self.cleanup_timer.timeout.connect(self._reset_stuck_keys)
        self.cleanup_timer.start()
        
        # Timer de vérification de la santé du hook
        self.health_check_timer = QTimer(self)
        self.health_check_timer.setInterval(30000)  # Vérifier toutes les 30 secondes
        self.health_check_timer.timeout.connect(self._check_hook_health)
        self.health_check_timer.start()
        
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
        
        # Validation du raccourci
        if not self.hotkey or not isinstance(self.hotkey, str) or self.hotkey.strip() == "":
            log("No valid hotkey configured", logging.WARNING)
            return False

        try:
            # Register the hotkey
            log(f"Registering hotkey: {self.hotkey}", logging.INFO)

            # Hook pour capturer toutes les touches - ne jamais dé-enregistrer ce hook une fois créé
            # sauf lors de la fermeture de l'application pour éviter les problèmes de synchronisation
            if self.key_listener_hook is None:
                self.key_listener_hook = keyboard.hook(self._on_any_key_safe)
                log("Keyboard hook created successfully", logging.INFO)
            self.registered = True
            self._hook_error_count = 0  # Réinitialiser le compteur d'erreurs
            # S'assurer que le timer est actif après (ré)enregistrement
            if not self.cleanup_timer.isActive():
                self.cleanup_timer.start()
            if not self.health_check_timer.isActive():
                self.health_check_timer.start()
            return True

        except Exception as e:
            log(f"Error registering hotkey: {e}", logging.ERROR)
            self._hook_error_count += 1
            return False
    
    def unregister_hotkey(self):
        """Unregister the global hotkey"""
        # Arrêter le timer de nettoyage lorsqu'on se désinscrit
        if self.cleanup_timer.isActive():
            self.cleanup_timer.stop()
        # Ne jamais désinstaller le hook pendant l'exécution normale
        # On le garde actif pour éviter les problèmes de synchronisation
        # Le hook sera désinstallé uniquement lors de la fermeture de l'application
        if self.registered:
            self.registered = False
            # Réinitialiser les touches actuelles pour éviter les états incohérents
            with self._lock:
                self.current_keys.clear()
            log("Hotkey unregistered (hook kept active)")

    def close(self):
        """Stopper le timer et nettoyer les raccourcis."""
        # Arrêter les timers
        if self.cleanup_timer.isActive():
            self.cleanup_timer.stop()
        if self.health_check_timer.isActive():
            self.health_check_timer.stop()
        # Désinstaller réellement le hook lors de la fermeture
        if self.key_listener_hook:
            try:
                keyboard.unhook(self.key_listener_hook)
                self.key_listener_hook = None
                log("Keyboard hook removed on close", logging.INFO)
            except Exception as e:
                log(f"Error removing keyboard hook on close: {e}", logging.ERROR)
        self.registered = False
        with self._lock:
            self.current_keys.clear()

    
    def _on_any_key_safe(self, event):
        """Safe wrapper for key event handling with error recovery"""
        try:
            self._on_any_key(event)
            # Réinitialiser le compteur d'erreurs en cas de succès
            if self._hook_error_count > 0:
                self._hook_error_count = max(0, self._hook_error_count - 1)
        except Exception as e:
            self._hook_error_count += 1
            log(f"Error in keyboard hook (count: {self._hook_error_count}/{self._max_errors}): {e}", logging.ERROR)
            # Si trop d'erreurs, tenter une récupération
            if self._hook_error_count >= self._max_errors:
                log("Too many hook errors, attempting recovery", logging.WARNING)
                self._attempt_recovery()
    
    def _on_any_key(self, event):
        """Handle key events to detect hotkey combinations"""
        # Ne rien faire si pas enregistré
        if not self.registered:
            return
        
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
        
        # Gérer les événements de touche avec thread safety
        with self._lock:
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
        with self._lock:
            if self.current_keys:
                log(f"Resetting stuck keys: {self.current_keys}", logging.DEBUG)
                self.current_keys.clear()
                
    def _check_hotkey(self):
        """Check if the current keys match the hotkey (must be called with lock held)"""
        # Ne rien vérifier si un déclenchement est en cours
        if self._is_processing_trigger:
            return
        
        # Obtenir le raccourci configuré
        try:
            if self.voice_hotkey:
                configured_hotkey = self.settings.get_voice_hotkey()
            elif self.screenshot_hotkey:
                configured_hotkey = self.settings.get_screenshot_hotkey()
            else:
                configured_hotkey = self.settings.get_hotkey()
            
            if not configured_hotkey:
                return
            
            configured_hotkey = configured_hotkey.lower()
        except Exception as e:
            log(f"Error getting configured hotkey: {e}", logging.ERROR)
            return
        
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
        hotkey_parts = [part.strip().lower() for part in hotkey_parts if part.strip()]
        
        if not hotkey_parts:
            return
        
        # Vérifier si toutes les touches du raccourci sont enfoncées
        if all(part in self.current_keys for part in hotkey_parts) and len(self.current_keys) == len(hotkey_parts):
            # Éviter les déclenchements multiples en vérifiant le temps écoulé
            current_time = time.time()
            if current_time - self.last_hotkey_time > 0.5:  # 500ms de délai
                self.last_hotkey_time = current_time
                self._hotkey_triggered()
    
    def _hotkey_triggered(self):
        """Handle hotkey trigger (must be called with lock held)"""
        # Marquer qu'un déclenchement est en cours
        self._is_processing_trigger = True
        
        try:
            # Émettre le signal dans le thread principal Qt pour éviter les problèmes de threading
            # CRITIQUE : keyboard.hook() s'exécute dans un thread Windows, pas le thread Qt
            # On doit donc forcer l'émission du signal dans le thread principal
            if self.voice_hotkey:
                log("Voice hotkey triggered", logging.INFO)
                QMetaObject.invokeMethod(self, "_emit_voice_signal", Qt.QueuedConnection)
            elif self.screenshot_hotkey:
                log("Screenshot hotkey triggered", logging.INFO)
                QMetaObject.invokeMethod(self, "_emit_screenshot_signal", Qt.QueuedConnection)
            else:
                log("Hotkey triggered", logging.INFO)
                QMetaObject.invokeMethod(self, "_emit_hotkey_signal", Qt.QueuedConnection)
        except Exception as e:
            log(f"Error emitting hotkey signal: {e}", logging.ERROR)
        finally:
            # Nettoyer les touches suivies pour éviter les états incohérents
            # Ne PAS ré-enregistrer le hook - il reste actif en permanence
            self.current_keys.clear()
            self._is_processing_trigger = False
    
    def _emit_hotkey_signal(self):
        """Émet le signal hotkey dans le thread principal Qt"""
        try:
            self.hotkey_triggered.emit()
        except Exception as e:
            log(f"Error in _emit_hotkey_signal: {e}", logging.ERROR)
    
    def _emit_voice_signal(self):
        """Émet le signal voice hotkey dans le thread principal Qt"""
        try:
            self.voice_hotkey_triggered.emit()
        except Exception as e:
            log(f"Error in _emit_voice_signal: {e}", logging.ERROR)
    
    def _emit_screenshot_signal(self):
        """Émet le signal screenshot hotkey dans le thread principal Qt"""
        try:
            self.screenshot_hotkey_triggered.emit()
        except Exception as e:
            log(f"Error in _emit_screenshot_signal: {e}", logging.ERROR)
    
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
    
    def _check_hook_health(self):
        """Vérifier périodiquement la santé du hook et tenter une récupération si nécessaire"""
        if self._hook_error_count >= self._max_errors:
            log("Hook health check: too many errors detected, attempting recovery", logging.WARNING)
            self._attempt_recovery()
        elif self.registered and self.key_listener_hook is None:
            log("Hook health check: hook is None but registered=True, attempting recovery", logging.WARNING)
            self._attempt_recovery()
    
    def _attempt_recovery(self):
        """Tenter de récupérer le hook en cas de problème"""
        try:
            log("Attempting to recover keyboard hook...", logging.INFO)
            # Nettoyer l'état actuel
            with self._lock:
                self.current_keys.clear()
            self._is_processing_trigger = False
            
            # Désinstaller le hook existant si présent
            if self.key_listener_hook:
                try:
                    keyboard.unhook(self.key_listener_hook)
                except:
                    pass
                self.key_listener_hook = None
            
            # Réinitialiser le compteur d'erreurs
            self._hook_error_count = 0
            
            # Réenregistrer le hook
            if self.registered:
                self.registered = False
                self.register_hotkey()
                log("Keyboard hook recovery successful", logging.INFO)
        except Exception as e:
            log(f"Failed to recover keyboard hook: {e}", logging.ERROR)
    
    def __del__(self):
        """Clean up when the object is deleted"""
        try:
            self.close()
        except:
            pass  # Ignorer les erreurs dans __del__
