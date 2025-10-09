#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTextEdit,
    QApplication
)
from PySide6.QtCore import Qt, QSize, QTimer, QPoint
from PySide6.QtGui import QIcon, QCursor, QKeySequence
import win32com.client

class ResponseWindow(QWidget):
    """Window to display API responses"""
    
    def __init__(self):
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("SuperMenu - Réponse")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(650, 450)
        
        # Create the main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(10)
        
        # Create the title bar
        self.create_title_bar()
        
        # Create the response text area
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setMinimumSize(600, 400)
        
        # Add the response text to the layout
        self.main_layout.addWidget(self.response_text)
        
        # Create the status bar
        self.status_label = QLabel("Prêt")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #3498db; font-style: italic;")
        self.main_layout.addWidget(self.status_label)
        
        # Create the button bar
        self.create_button_bar()
        
        # Initialize the loading animation
        self.loading = False
        self.loading_dots = 0
        self.loading_timer = None
        
        # Variable pour stocker la position d'ouverture
        self.trigger_position = None
    
    def create_title_bar(self):
        """Create the title bar"""
        self.title_label = QLabel("SuperMenu - Réponse")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.title_label)
    
    def create_button_bar(self):
        """Create the button bar"""
        button_layout = QHBoxLayout()
        
        # Retry button
        self.retry_button = QPushButton("🔄 Réessayer")
        self.retry_button.setEnabled(False)
        self.retry_button.clicked.connect(self.retry_request)
        button_layout.addWidget(self.retry_button)
        
        # Copy button
        self.copy_button = QPushButton("📋 Copier")
        self.copy_button.clicked.connect(self.copy_response)
        button_layout.addWidget(self.copy_button)
        
        # Write button
        self.write_button = QPushButton("✍️ Insérer")
        self.write_button.clicked.connect(self.write_response)
        button_layout.addWidget(self.write_button)
        
        self.main_layout.addLayout(button_layout)
    
    def set_status(self, status):
        """Set the status message"""
        self.response_text.setText(status)
        self.title_label.setText(f"SuperMenu - {status}")
    
    def set_response(self, response):
        """Set the response text"""
        self.response_text.setText(response)
        self.retry_button.setEnabled(True)
        self.copy_button.setEnabled(True)
    
    def set_loading(self, is_loading):
        """Set the loading state"""
        if is_loading:
            self.retry_button.setEnabled(False)
            self.copy_button.setEnabled(False)
        else:
            self.retry_button.setEnabled(True)
            self.copy_button.setEnabled(True)
    
    def copy_response(self):
        """Copy the response to the clipboard"""
        QApplication.clipboard().setText(self.response_text.toPlainText())
        self.copy_button.setText("Copié!")
        
        # Reset the button text after a delay
        QTimer.singleShot(2000, lambda: self.copy_button.setText("Copier"))
    
    def write_response(self):
        """Copy the response to the clipboard and paste it"""
        # Copy the response to the clipboard
        QApplication.clipboard().setText(self.response_text.toPlainText())
        
        # Hide the window
        self.hide()
        
        # Simulate Ctrl+V to paste the text
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys("^v")
    
    def retry_request(self):
        # This method should be implemented
        pass

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
            
            # Positionner la fenêtre près de la position de déclenchement, mais en s'assurant qu'elle reste visible
            x = max(screen_geometry.left(), min(self.trigger_position.x() - window_geometry.width() // 2, 
                                               screen_geometry.right() - window_geometry.width()))
            y = max(screen_geometry.top(), min(self.trigger_position.y() - window_geometry.height() // 2, 
                                               screen_geometry.bottom() - window_geometry.height()))
            
            self.move(x, y)
        else:
            # Comportement par défaut : centrer sur l'écran principal
            screen_geometry = QApplication.primaryScreen().geometry()
            window_geometry = self.frameGeometry()
            window_geometry.moveCenter(screen_geometry.center())
            self.move(window_geometry.topLeft())
        
        super().showEvent(event)
    
    def set_trigger_position(self, position):
        """Définir la position de déclenchement pour l'affichage de la fenêtre
        
        Args:
            position: QPoint représentant la position du curseur ou de la fenêtre de dialogue
        """
        self.trigger_position = position
