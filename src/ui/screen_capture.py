#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QGuiApplication
import os
import tempfile
import logging
from PIL import ImageGrab
from utils.logger import log

def capture_screen():
    """Fonction pour capturer une zone de l'écran et retourner le chemin de l'image"""
    log("Démarrage de la capture d'écran simplifiée...", logging.DEBUG)
    
    # Masquer uniquement les fenêtres de dialogue, pas les fenêtres principales
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QDialog):
            widget.hide()
    
    # Attendre un court instant pour que les fenêtres disparaissent
    QApplication.processEvents()
    
    # Créer un timer pour retarder la capture
    timer = QTimer()
    timer.setSingleShot(True)
    
    # Variables pour stocker le résultat
    screenshot_path = None
    
    def do_capture():
        nonlocal screenshot_path
        try:
            # Capturer tout l'écran
            screenshot = ImageGrab.grab()
            
            # Créer un fichier temporaire pour stocker l'image
            temp_dir = tempfile.gettempdir()
            screenshot_path = os.path.join(temp_dir, f"supermenu_screenshot_{id(timer)}.png")
            
            # Enregistrer l'image
            screenshot.save(screenshot_path, "PNG")
            log(f"Image capturée et enregistrée: {screenshot_path}", logging.DEBUG)
            
            # Réafficher les fenêtres de dialogue de l'application
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QDialog):
                    widget.show()
        except Exception as e:
            log(f"Erreur lors de la capture d'écran: {e}", logging.ERROR)
            screenshot_path = None
            
            # Réafficher les fenêtres de dialogue de l'application en cas d'erreur
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QDialog):
                    widget.show()
    
    # Connecter le timer à la fonction de capture
    timer.timeout.connect(do_capture)
    
    # Démarrer le timer (500 ms de délai)
    timer.start(500)
    
    # Attendre que le timer soit terminé
    while timer.isActive():
        QApplication.processEvents()
    
    # Attendre un peu plus pour s'assurer que la capture est terminée
    QTimer.singleShot(200, lambda: None)
    QApplication.processEvents()
    
    return screenshot_path
