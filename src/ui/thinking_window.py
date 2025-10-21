#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Fenêtre pour afficher le contenu thinking des modèles avec reasoning
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTextEdit,
    QApplication
)
from PySide6.QtCore import Qt, QTimer, QPoint


class ThinkingWindow(QWidget):
    """Window to display thinking content from reasoning models"""
    
    def __init__(self):
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("SuperMenu - Thinking")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        
        # Create the main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create the content layout
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.addLayout(self.content_layout)
        
        # Create the title bar
        self.create_title_bar()
        
        # Create the thinking text area
        self.thinking_text = QTextEdit()
        self.thinking_text.setReadOnly(True)
        self.thinking_text.setMinimumSize(600, 400)
        self.thinking_text.setObjectName("thinkingText")
        self.thinking_text.setPlaceholderText("Le contenu thinking apparaîtra ici...")
        self.content_layout.addWidget(self.thinking_text)
        
        # Create the status bar
        self.status_label = QLabel("En attente du thinking...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setProperty("status", "info")
        self.content_layout.addWidget(self.status_label)
        
        # Create the button bar
        self.create_button_bar()
        
        # Variable pour stocker la position d'ouverture
        self.trigger_position = None
    
    def create_title_bar(self):
        """Create the title bar"""
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 10)
        
        # Title
        self.title_label = QLabel("🧠 SuperMenu - Thinking")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        self.content_layout.addWidget(header)
    
    def create_button_bar(self):
        """Create the button bar"""
        button_bar = QWidget()
        button_layout = QHBoxLayout(button_bar)
        button_layout.setSpacing(8)
        
        # Copy button
        self.copy_button = QPushButton("📋 Copier")
        self.copy_button.clicked.connect(self.copy_thinking)
        self.copy_button.setEnabled(False)
        button_layout.addWidget(self.copy_button)
        
        # Close button
        self.close_button = QPushButton("✖️ Fermer")
        self.close_button.clicked.connect(self.hide)
        button_layout.addWidget(self.close_button)
        
        button_layout.addStretch()
        
        self.content_layout.addWidget(button_bar)
    
    def set_thinking_content(self, thinking_content):
        """Set the thinking content"""
        if thinking_content:
            self.thinking_text.setPlainText(thinking_content)
            self.title_label.setText("🧠 SuperMenu - Thinking")
            self.status_label.setText("✅ Thinking chargé")
            self.status_label.setProperty("status", "success")
            self.copy_button.setEnabled(True)
        else:
            self.thinking_text.setPlainText("")
            self.title_label.setText("🧠 SuperMenu - Thinking")
            self.status_label.setText("ℹ️ Aucun thinking détecté")
            self.status_label.setProperty("status", "info")
            self.copy_button.setEnabled(False)
    
    def clear_content(self):
        """Clear the thinking content"""
        self.thinking_text.clear()
        self.status_label.setText("En attente du thinking...")
        self.status_label.setProperty("status", "info")
        self.copy_button.setEnabled(False)
    
    def copy_thinking(self):
        """Copy the thinking content to the clipboard"""
        QApplication.clipboard().setText(self.thinking_text.toPlainText())
        self.copy_button.setText("✅ Copié!")
        self.copy_button.setEnabled(False)
        
        # Reset the button text after a delay
        def reset_button():
            self.copy_button.setText("📋 Copier")
            self.copy_button.setEnabled(True)
        
        QTimer.singleShot(2000, reset_button)
    
    def showEvent(self, event):
        """Handle show event"""
        if self.trigger_position:
            # Utiliser la position du curseur ou de la fenêtre de dialogue
            screen = QApplication.screenAt(self.trigger_position)
            if not screen:
                screen = QApplication.primaryScreen()
            
            # Calculer la position optimale sur l'écran
            screen_geometry = screen.availableGeometry()
            window_geometry = self.frameGeometry()
            
            # Positionner la fenêtre à droite de la position de déclenchement
            x = min(self.trigger_position.x() + 50, 
                   screen_geometry.right() - window_geometry.width())
            y = max(screen_geometry.top(), min(self.trigger_position.y() - window_geometry.height() // 2, 
                                               screen_geometry.bottom() - window_geometry.height()))
            
            self.move(x, y)
        else:
            # Comportement par défaut : centrer sur l'écran principal
            screen_geometry = QApplication.primaryScreen().geometry()
            window_geometry = self.frameGeometry()
            window_geometry.moveCenter(screen_geometry.center())
            # Décaler légèrement vers la droite
            self.move(window_geometry.topLeft().x() + 100, window_geometry.topLeft().y())
        
        super().showEvent(event)
    
    def set_trigger_position(self, position):
        """Définir la position de déclenchement pour l'affichage de la fenêtre
        
        Args:
            position: QPoint représentant la position du curseur ou de la fenêtre de dialogue
        """
        self.trigger_position = position
