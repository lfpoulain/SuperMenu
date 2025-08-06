#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                              QLabel, QApplication, QRubberBand, QWidget)
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QSize
from PySide6.QtGui import QCursor, QGuiApplication, QScreen, QPixmap
import sys
import os
from PIL import ImageGrab, Image
import io
import tempfile

class ScreenshotDialog(QDialog):
    """Dialogue pour capturer une zone de l'écran"""
    
    screenshot_captured = Signal(str, str)  # Signal émis lorsqu'une capture d'écran est prise (chemin, texte)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Configuration de la fenêtre
        self.setWindowTitle("Capture d'écran")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Window)
        self.setMinimumSize(400, 200)
        
        # Initialisation des variables
        self.screenshot_path = None
        self.origin = QPoint()
        self.current = QPoint()
        self.rubberband = None
        
        # Création de l'interface
        self.init_ui()
        
        # Application du style
        self.apply_style()
    
    def init_ui(self):
        """Initialisation de l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel("Cliquez sur le bouton ci-dessous pour capturer une zone de l'écran.\n"
                             "Une fois la zone sélectionnée, vous pourrez envoyer l'image avec un prompt personnalisé.")
        instructions.setObjectName("instructions")
        layout.addWidget(instructions)
        
        # Bouton de capture
        capture_button = QPushButton("Capturer une zone de l'écran")
        capture_button.setObjectName("captureButton")
        capture_button.clicked.connect(self.start_capture)
        layout.addWidget(capture_button)
        
        # Boutons d'action
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def apply_style(self):
        """Appliquer le style sombre"""
        self.setStyleSheet("""
            QDialog {
                background-color: #2c3e50;
                color: #ecf0f1;
            }
            
            #instructions {
                color: #ecf0f1;
                font-size: 14px;
                margin-bottom: 20px;
            }
            
            QPushButton {
                background-color: #3498db;
                color: #ecf0f1;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #2980b9;
            }
            
            QPushButton:pressed {
                background-color: #1f6dad;
            }
            
            #captureButton {
                background-color: #2ecc71;
                font-size: 16px;
                padding: 15px;
                margin: 20px 0;
            }
            
            #captureButton:hover {
                background-color: #27ae60;
            }
            
            #captureButton:pressed {
                background-color: #219651;
            }
        """)
    
    def start_capture(self):
        """Démarrer la capture d'écran"""
        self.hide()  # Cacher la fenêtre de dialogue
        
        # Créer un widget plein écran transparent pour capturer les événements de souris
        self.screen_overlay = QWidget()
        self.screen_overlay.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.screen_overlay.setAttribute(Qt.WA_TranslucentBackground)
        
        # Obtenir la géométrie de tous les écrans
        desktop = QApplication.instance().primaryScreen()
        geometry = desktop.geometry()
        
        # Définir la taille du widget pour couvrir tous les écrans
        self.screen_overlay.setGeometry(geometry)
        
        # Créer le rubberband pour la sélection
        self.rubberband = QRubberBand(QRubberBand.Rectangle, self.screen_overlay)
        
        # Installer les gestionnaires d'événements
        self.screen_overlay.mousePressEvent = self.overlay_mouse_press
        self.screen_overlay.mouseMoveEvent = self.overlay_mouse_move
        self.screen_overlay.mouseReleaseEvent = self.overlay_mouse_release
        self.screen_overlay.keyPressEvent = self.overlay_key_press
        
        # Afficher le widget plein écran
        self.screen_overlay.showFullScreen()
        self.screen_overlay.setCursor(Qt.CrossCursor)
    
    def overlay_mouse_press(self, event):
        """Gérer l'événement de clic de souris sur l'overlay"""
        self.origin = event.pos()
        self.rubberband.setGeometry(QRect(self.origin, QSize()))
        self.rubberband.show()
    
    def overlay_mouse_move(self, event):
        """Gérer l'événement de déplacement de souris sur l'overlay"""
        if self.rubberband.isVisible():
            self.rubberband.setGeometry(QRect(self.origin, event.pos()).normalized())
    
    def overlay_mouse_release(self, event):
        """Gérer l'événement de relâchement de souris sur l'overlay"""
        if self.rubberband.isVisible():
            # Capturer la zone sélectionnée
            rect = self.rubberband.geometry()
            print(f"Zone sélectionnée: {rect.x()}, {rect.y()}, {rect.width()}, {rect.height()}")
            
            if rect.width() > 10 and rect.height() > 10:  # Ignorer les sélections trop petites
                self.capture_screenshot(rect)
                print(f"Capture effectuée, chemin: {self.screenshot_path}")
            else:
                print("Sélection trop petite, ignorée")
            
            # Fermer l'overlay
            self.screen_overlay.close()
            
            # Si nous avons une capture d'écran, accepter le dialogue
            if self.screenshot_path and os.path.exists(self.screenshot_path):
                print("Capture réussie, acceptation du dialogue")
                self.accept()
            else:
                print("Pas de capture valide, réaffichage du dialogue")
                self.show()  # Réafficher la boîte de dialogue de capture
    
    def overlay_key_press(self, event):
        """Gérer l'événement de touche sur l'overlay"""
        if event.key() == Qt.Key_Escape:
            self.screen_overlay.close()
            self.show()  # Réafficher la boîte de dialogue de capture
    
    def capture_screenshot(self, rect):
        """Capturer une zone de l'écran"""
        # Capturer la zone sélectionnée avec PIL
        x, y, width, height = rect.x(), rect.y(), rect.width(), rect.height()
        screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        
        # Créer un fichier temporaire pour stocker l'image
        temp_dir = tempfile.gettempdir()
        self.screenshot_path = os.path.join(temp_dir, f"supermenu_screenshot_{id(self)}.png")
        
        # Enregistrer l'image
        screenshot.save(self.screenshot_path, "PNG")
        
        return self.screenshot_path
