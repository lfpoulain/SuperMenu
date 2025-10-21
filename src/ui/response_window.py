#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Fenêtre de réponse modernisée avec pyqtdarktheme
"""

import logging
import win32com.client
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTextEdit,
    QApplication, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, QPoint
from src.ui.thinking_window import ThinkingWindow
from src.utils.thinking_parser import extract_thinking_content, has_thinking_content

class ResponseWindow(QWidget):
    """Window to display API responses"""
    
    def __init__(self):
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("SuperMenu - Réponse")
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
        
        # Create the response text area
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setMinimumSize(600, 400)
        self.response_text.setObjectName("responseText")
        self.content_layout.addWidget(self.response_text)
        
        # Create the status bar
        self.status_label = QLabel("Prêt")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setProperty("status", "info")  # Pour le style automatique
        self.content_layout.addWidget(self.status_label)
        
        # Create the button bar
        self.create_button_bar()
        
        # Initialize the loading animation
        self.loading = False
        self.loading_dots = 0
        self.loading_timer = None
        
        # Variable pour stocker la position d'ouverture
        self.trigger_position = None
        
        # Fenêtre de thinking
        self.thinking_window = ThinkingWindow()
        
        # Stocker le contenu thinking et principal séparément
        self.thinking_content = None
        self.main_content = None
    
    def create_title_bar(self):
        """Create the title bar"""
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 10)
        
        # Title
        self.title_label = QLabel("SuperMenu - Réponse")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        self.content_layout.addWidget(header)
    
    def create_button_bar(self):
        """Create the button bar"""
        button_bar = QWidget()
        button_layout = QHBoxLayout(button_bar)
        button_layout.setSpacing(8)
        
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
        self.write_button = QPushButton("✍️ Écrire")
        self.write_button.clicked.connect(self.write_response)
        button_layout.addWidget(self.write_button)
        
        button_layout.addStretch()
        
        # Checkbox pour afficher le thinking
        self.show_thinking_checkbox = QCheckBox("🧠 Afficher Thinking")
        self.show_thinking_checkbox.setEnabled(False)
        self.show_thinking_checkbox.stateChanged.connect(self.toggle_thinking_window)
        button_layout.addWidget(self.show_thinking_checkbox)
        
        self.content_layout.addWidget(button_bar)
    
    def set_status(self, status):
        """Set the status message"""
        self.response_text.setText(status)
        self.title_label.setText(f"💬 SuperMenu - {status}")
        self.status_label.setText(status)
    
    def set_response(self, response):
        """Set the response text"""
        # Extraire le contenu thinking et le contenu principal
        self.thinking_content, self.main_content = extract_thinking_content(response)
        
        # Afficher le contenu principal dans la fenêtre de réponse
        self.response_text.setText(self.main_content)
        self.response_text.setPlainText(self.main_content)  # Assure l'affichage en texte brut
        self.title_label.setText("✨ SuperMenu - Réponse")
        self.status_label.setText("✅ Terminé")
        self.status_label.setProperty("status", "success")
        self.retry_button.setEnabled(True)
        self.copy_button.setEnabled(True)
        self.write_button.setEnabled(True)
        
        # Activer la checkbox si du thinking est détecté (mais ne pas l'afficher automatiquement)
        if self.thinking_content:
            self.show_thinking_checkbox.setEnabled(True)
            self.status_label.setText("✅ Terminé (Thinking détecté)")
            # Ne pas cocher automatiquement la checkbox - l'utilisateur décide
        else:
            self.show_thinking_checkbox.setEnabled(False)
            self.show_thinking_checkbox.setChecked(False)
            # Cacher la fenêtre thinking si elle était ouverte
            if self.thinking_window and self.thinking_window.isVisible():
                self.thinking_window.hide()
    
    def set_loading(self, is_loading):
        """Set the loading state"""
        if is_loading:
            self.title_label.setText("⏳ SuperMenu - Chargement...")
            self.status_label.setText("⏳ Traitement en cours...")
            self.status_label.setProperty("status", "info")
            self.retry_button.setEnabled(False)
            self.copy_button.setEnabled(False)
            self.write_button.setEnabled(False)
        else:
            self.retry_button.setEnabled(True)
            self.copy_button.setEnabled(True)
            self.write_button.setEnabled(True)
    
    def copy_response(self):
        """Copy the response to the clipboard"""
        QApplication.clipboard().setText(self.response_text.toPlainText())
        self.copy_button.setText("✅ Copié!")
        self.copy_button.setEnabled(False)
        
        # Reset the button text after a delay
        def reset_button():
            self.copy_button.setText("📋 Copier")
            self.copy_button.setEnabled(True)
        
        QTimer.singleShot(2000, reset_button)
    
    def write_response(self):
        """Copy the response to the clipboard and paste it"""
        try:
            # Copy the response to the clipboard
            text = self.response_text.toPlainText()
            if text:
                QApplication.clipboard().setText(text)
                
                # Hide the window
                self.hide()
                
                # Attendre un peu pour que la fenêtre se cache
                QTimer.singleShot(100, self._paste_text)
            else:
                self.status_label.setText("⚠️ Aucun texte à coller")
                self.status_label.setProperty("status", "warning")
        except Exception as e:
            self.status_label.setText(f"❌ Erreur: {str(e)}")
            self.status_label.setProperty("status", "error")
    
    def _paste_text(self):
        """Coller le texte avec Ctrl+V"""
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys("^v")
        except Exception as e:
            logging.error(f"Erreur lors du collage: {e}")
    
    def retry_request(self):
        """Retry the API request - to be implemented by the caller"""
        # Cette méthode sera connectée par le gestionnaire de contexte
        self.status_label.setText("🔄 Réessai...")
        self.status_label.setProperty("status", "info")

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
        # Transmettre également à la fenêtre thinking
        if self.thinking_window:
            self.thinking_window.set_trigger_position(position)
    
    def toggle_thinking_window(self, state):
        """Toggle the thinking window visibility"""
        if state == Qt.CheckState.Checked.value:
            # Afficher la fenêtre thinking avec le contenu
            if self.thinking_content:
                self.thinking_window.set_thinking_content(self.thinking_content)
                self.thinking_window.show()
            else:
                self.thinking_window.set_thinking_content(None)
                self.thinking_window.show()
        else:
            # Cacher la fenêtre thinking
            self.thinking_window.hide()
    
    def closeEvent(self, event):
        """Handle close event"""
        # Fermer également la fenêtre thinking
        if self.thinking_window:
            self.thinking_window.hide()
        super().closeEvent(event)
    
    def hideEvent(self, event):
        """Handle hide event"""
        # Cacher également la fenêtre thinking
        if self.thinking_window and self.thinking_window.isVisible():
            self.thinking_window.hide()
        super().hideEvent(event)
