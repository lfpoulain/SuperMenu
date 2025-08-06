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
        
        # Create the main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create the content widget
        self.content_widget = QWidget()
        self.content_widget.setObjectName("contentWidget")
        
        # Style sera appliqué dynamiquement en fonction du thème
        
        # Create the content layout
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        
        # Create the title bar
        self.create_title_bar()
        
        # Create the response text area
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setMinimumSize(600, 400)
        
        # Le style sera appliqué dynamiquement
        
        # Add the response text to the layout
        self.content_layout.addWidget(self.response_text)
        
        # Create the status bar
        self.status_label = QLabel("Prêt")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.status_label)
        
        # Create the button bar
        self.create_button_bar()
        
        # Add the content widget to the main layout
        self.main_layout.addWidget(self.content_widget)
        
        # Initialize the loading animation
        self.loading = False
        self.loading_dots = 0
        self.loading_timer = None
        
        # Apply initial style
        self.apply_style()
        
        # Variables for window dragging
        self.dragging = False
        self.drag_position = None
        
        # Variable pour stocker la position d'ouverture
        self.trigger_position = None
    
    def create_title_bar(self):
        """Create the title bar"""
        # Avec une fenêtre standard, nous n'avons plus besoin d'une barre de titre personnalisée
        # car la fenêtre a déjà une barre de titre avec un bouton de fermeture
        # Nous allons simplement ajouter un en-tête pour maintenir l'apparence
        
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        # Title
        self.title_label = QLabel("SuperMenu - Réponse")
        self.title_label.setStyleSheet("""
            color: white;
            font-size: 16px;
            font-weight: bold;
        """)
        header_layout.addWidget(self.title_label)
        
        # Spacer
        header_layout.addStretch()
        
        self.content_layout.addWidget(header)
    
    def create_button_bar(self):
        """Create the button bar"""
        button_bar = QWidget()
        button_layout = QHBoxLayout(button_bar)
        
        # Retry button
        self.retry_button = QPushButton("Réessayer")
        self.retry_button.setEnabled(False)
        self.retry_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: #FFFFFF;
                border: 1px solid #777777;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #777777;
                border: 1px solid #555555;
            }
        """)
        self.retry_button.clicked.connect(self.retry_request)
        button_layout.addWidget(self.retry_button)
        
        # Copy button
        self.copy_button = QPushButton("Copier")
        self.copy_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: #FFFFFF;
                border: 1px solid #777777;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #777777;
                border: 1px solid #555555;
            }
        """)
        self.copy_button.clicked.connect(self.copy_response)
        button_layout.addWidget(self.copy_button)
        
        # Write button
        self.write_button = QPushButton("Écrire")
        self.write_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: #FFFFFF;
                border: 1px solid #777777;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        self.write_button.clicked.connect(self.write_response)
        button_layout.addWidget(self.write_button)
        
        self.content_layout.addWidget(button_bar)
    
    def apply_style(self):
        """Appliquer le style en fonction du thème"""
        self.apply_dark_style()
    
    def apply_neomorphic_dark_style(self):
        """Appliquer le style Neumorphism sombre"""
        # Couleurs
        bg_color = "#252836"
        border_color = "#2e3143"
        text_color = "#ecf0f1"
        accent_color = "#3498db"
        
        # Style du widget principal
        self.content_widget.setStyleSheet(f"""
            #contentWidget {{
                background-color: {bg_color};
                border-radius: 15px;
                border: 2px solid {border_color};
            }}
        """)
        
        # Style pour le titre
        self.title_label.setStyleSheet(f"""
            color: {text_color};
            font-size: 16px;
            font-weight: bold;
            padding: 5px;
        """)
        
        # Style pour la zone de texte
        self.response_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: #2a2d3e;
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 10px;
                padding: 15px;
                font-family: 'Segoe UI', Arial;
                font-size: 14px;
                selection-background-color: {accent_color};
                selection-color: white;
            }}
        """)
        
        # Style pour les boutons
        button_style = f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 2px solid {border_color};
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: #2a2d3e;
            }}
            
            QPushButton:pressed {{
                background-color: #1e212f;
                border: 2px solid #1a1d2a;
            }}
        """
        
        self.copy_button.setStyleSheet(button_style)
        self.write_button.setStyleSheet(button_style)
        self.retry_button.setStyleSheet(button_style + f"""
            QPushButton:disabled {{
                background-color: #1e212f;
                color: #4a4e5c;
                border: 2px solid #252836;
            }}
        """)
        
        # Style pour le label de statut
        self.status_label.setStyleSheet(f"""
            color: {accent_color};
            font-size: 13px;
            font-style: italic;
            padding: 5px;
        """)
    
    def apply_neomorphic_light_style(self):
        """Appliquer le style Neumorphism clair"""
        # Couleurs
        bg_color = "#e6e9ef"
        border_color = "#d0d4dd"
        text_color = "#2c3e50"
        accent_color = "#3498db"
        
        # Style du widget principal
        self.content_widget.setStyleSheet(f"""
            #contentWidget {{
                background-color: {bg_color};
                border-radius: 15px;
                border: 2px solid {border_color};
            }}
        """)
        
        # Style pour le titre
        self.title_label.setStyleSheet(f"""
            color: {text_color};
            font-size: 16px;
            font-weight: bold;
            padding: 5px;
        """)
        
        # Style pour la zone de texte
        self.response_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: #f0f3f9;
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 10px;
                padding: 15px;
                font-family: 'Segoe UI', Arial;
                font-size: 14px;
                selection-background-color: {accent_color};
                selection-color: white;
            }}
        """)
        
        # Style pour les boutons
        button_style = f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 2px solid {border_color};
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: #f0f3f9;
            }}
            
            QPushButton:pressed {{
                background-color: #d8dbe1;
                border: 2px solid #c8ccd4;
            }}
        """
        
        self.copy_button.setStyleSheet(button_style)
        self.write_button.setStyleSheet(button_style)
        self.retry_button.setStyleSheet(button_style + f"""
            QPushButton:disabled {{
                background-color: #d8dbe1;
                color: #a0a4ad;
                border: 2px solid #e6e9ef;
            }}
        """)
        
        # Style pour le label de statut
        self.status_label.setStyleSheet(f"""
            color: {accent_color};
            font-size: 13px;
            font-style: italic;
            padding: 5px;
        """)
    
    def apply_dark_style(self):
        """Appliquer le style sombre standard"""
        # Style du widget principal
        self.content_widget.setStyleSheet("""
            #contentWidget {
                background-color: #333333;
                border-radius: 10px;
                border: 1px solid #555555;
            }
        """)
        
        # Style pour le titre
        self.title_label.setStyleSheet("""
            color: white;
            font-size: 16px;
            font-weight: bold;
            padding: 5px;
        """)
        
        # Style pour la zone de texte
        self.response_text.setStyleSheet("""
            QTextEdit {
                background-color: #444444;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 5px;
                font-family: 'Segoe UI', Arial;
                font-size: 13px;
            }
        """)
        
        # Style pour les boutons
        button_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #2980b9;
            }
            
            QPushButton:pressed {
                background-color: #1f6dad;
            }
        """
        
        self.copy_button.setStyleSheet(button_style)
        self.write_button.setStyleSheet(button_style)
        
        # Style pour le label de statut
        self.status_label.setStyleSheet("""
            color: #3498db;
            font-size: 13px;
            font-style: italic;
            padding: 5px;
        """)
    
    def apply_light_style(self):
        """Appliquer le style clair standard"""
        # Style du widget principal
        self.content_widget.setStyleSheet("""
            #contentWidget {
                background-color: #f5f5f5;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
        """)
        
        # Style pour le titre
        self.title_label.setStyleSheet("""
            color: #2c3e50;
            font-size: 16px;
            font-weight: bold;
            padding: 5px;
        """)
        
        # Style pour la zone de texte
        self.response_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 5px;
                font-family: 'Segoe UI', Arial;
                font-size: 13px;
            }
        """)
        
        # Style pour les boutons
        button_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #2980b9;
            }
            
            QPushButton:pressed {
                background-color: #1f6dad;
            }
        """
        
        self.copy_button.setStyleSheet(button_style)
        self.write_button.setStyleSheet(button_style)
        
        # Style pour le label de statut
        self.status_label.setStyleSheet("""
            color: #3498db;
            font-size: 13px;
            font-style: italic;
            padding: 5px;
        """)
    
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
