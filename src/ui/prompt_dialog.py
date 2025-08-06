#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QTextEdit, QPushButton, QApplication, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

class PromptDialog(QDialog):
    """Dialogue pour saisir un prompt personnalisé"""
    
    # Signal émis lorsque le prompt est validé
    prompt_submitted = Signal(str)
    
    def __init__(self, selected_text, parent=None):
        super().__init__(parent)
        
        # Configurer la fenêtre
        self.setWindowTitle(" GodMode - Prompt personnalisé")
        self.setMinimumSize(600, 400)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Window)
        
        # Stocker le texte sélectionné
        self.selected_text = selected_text
        
        # Variables pour l'image
        self.image_path = None
        self.image_label = None
        
        # Créer le layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Ajouter des instructions
        instructions = QLabel("Entrez votre prompt personnalisé ci-dessous. Le texte sélectionné sera traité selon ce prompt.")
        instructions.setObjectName("instructions")
        layout.addWidget(instructions)
        
        # Conteneur pour l'aperçu (texte ou image)
        self.preview_container = QVBoxLayout()
        
        # Afficher un aperçu du texte sélectionné
        if selected_text:
            preview_label = QLabel("Texte sélectionné :")
            preview_label.setObjectName("sectionLabel")
            self.preview_container.addWidget(preview_label)
            
            preview_text = QTextEdit()
            preview_text.setReadOnly(True)
            preview_text.setMaximumHeight(100)
            preview_text.setText(selected_text[:500] + ("..." if len(selected_text) > 500 else ""))
            preview_text.setObjectName("previewText")
            self.preview_container.addWidget(preview_text)
        
        layout.addLayout(self.preview_container)
        
        # Champ de saisie du prompt
        prompt_label = QLabel("Votre prompt :")
        prompt_label.setObjectName("sectionLabel")
        layout.addWidget(prompt_label)
        
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("Exemple : Résume ce texte en 3 points clés...")
        self.prompt_input.setObjectName("promptInput")
        layout.addWidget(self.prompt_input)
        
        # Boutons
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.clicked.connect(self.reject)
        
        self.submit_button = QPushButton("Envoyer")
        self.submit_button.setObjectName("submitButton")
        self.submit_button.clicked.connect(self.accept_prompt)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.submit_button)
        
        layout.addLayout(button_layout)
        
        # Appliquer le style
        self.apply_style()
        
        # Focus sur le champ de saisie
        self.prompt_input.setFocus()
    
    def set_image_path(self, image_path):
        """Définir une image à utiliser au lieu du texte sélectionné"""
        self.image_path = image_path
        
        # Mettre à jour les instructions
        for i in range(self.preview_container.count()):
            item = self.preview_container.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        # Ajouter le label pour l'image
        image_label = QLabel("Image capturée :")
        image_label.setObjectName("sectionLabel")
        self.preview_container.addWidget(image_label)
        
        # Créer un cadre pour l'image
        image_frame = QFrame()
        image_frame.setObjectName("imageFrame")
        image_frame.setFrameShape(QFrame.StyledPanel)
        image_frame.setFrameShadow(QFrame.Sunken)
        image_frame.setStyleSheet("""
            #imageFrame {
                background-color: #34495e;
                border-radius: 8px;
                padding: 5px;
            }
        """)
        
        image_layout = QVBoxLayout(image_frame)
        
        # Ajouter l'aperçu de l'image
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(150)
        self.image_label.setMaximumHeight(250)
        
        # Charger et redimensionner l'image
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(400, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(pixmap)
        
        image_layout.addWidget(self.image_label)
        self.preview_container.addWidget(image_frame)
        
        # Mettre à jour le placeholder du prompt
        self.prompt_input.setPlaceholderText("Exemple : Décris cette image en détail...")
        
        # Mettre à jour le titre de la fenêtre
        self.setWindowTitle(" GodMode - Prompt personnalisé avec image")
    
    def apply_style(self):
        """Appliquer le style sombre"""
        self.apply_dark_style()
    
    def apply_neomorphic_dark_style(self):
        """Appliquer le style Neumorphism sombre"""
        # Couleurs
        bg_color = "#252836"
        border_color = "#2e3143"
        text_color = "#ecf0f1"
        accent_color = "#3498db"
        
        # Style global
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border-radius: 15px;
            }}
            
            #instructions {{
                color: {text_color};
                font-size: 14px;
                margin-bottom: 10px;
            }}
            
            #sectionLabel {{
                color: {text_color};
                font-size: 14px;
                font-weight: bold;
                margin-top: 10px;
            }}
            
            QTextEdit {{
                background-color: #2a2d3e;
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 10px;
                padding: 10px;
                font-family: 'Segoe UI', Arial;
                font-size: 14px;
                selection-background-color: {accent_color};
                selection-color: white;
            }}
            
            #cancelButton, #submitButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 2px solid {border_color};
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }}
            
            #cancelButton:hover, #submitButton:hover {{
                background-color: #2a2d3e;
            }}
            
            #cancelButton:pressed, #submitButton:pressed {{
                background-color: #1e212f;
                border: 2px solid #1a1d2a;
            }}
            
            #submitButton {{
                color: {text_color};
                font-weight: bold;
            }}
        """)
    
    def apply_neomorphic_light_style(self):
        """Appliquer le style Neumorphism clair"""
        # Couleurs
        bg_color = "#e6e9ef"
        border_color = "#d0d4dd"
        text_color = "#2c3e50"
        accent_color = "#3498db"
        
        # Style global
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border-radius: 15px;
            }}
            
            #instructions {{
                color: {text_color};
                font-size: 14px;
                margin-bottom: 10px;
            }}
            
            #sectionLabel {{
                color: {text_color};
                font-size: 14px;
                font-weight: bold;
                margin-top: 10px;
            }}
            
            QTextEdit {{
                background-color: #f0f3f9;
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 10px;
                padding: 10px;
                font-family: 'Segoe UI', Arial;
                font-size: 14px;
                selection-background-color: {accent_color};
                selection-color: white;
            }}
            
            #cancelButton, #submitButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 2px solid {border_color};
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }}
            
            #cancelButton:hover, #submitButton:hover {{
                background-color: #f0f3f9;
            }}
            
            #cancelButton:pressed, #submitButton:pressed {{
                background-color: #d8dbe1;
                border: 2px solid #c8ccd4;
            }}
            
            #submitButton {{
                color: {text_color};
                font-weight: bold;
            }}
        """)
    
    def apply_dark_style(self):
        """Appliquer le style sombre standard"""
        self.setStyleSheet("""
            QDialog {
                background-color: #2c3e50;
                color: #ecf0f1;
            }
            
            #instructions {
                color: #ecf0f1;
                font-size: 14px;
                margin-bottom: 10px;
            }
            
            #sectionLabel {
                color: #ecf0f1;
                font-size: 14px;
                font-weight: bold;
                margin-top: 10px;
            }
            
            QTextEdit {
                background-color: #34495e;
                color: #ecf0f1;
                border: 1px solid #546e7a;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Segoe UI', Arial;
                selection-background-color: #3498db;
                selection-color: white;
            }
            
            #cancelButton, #submitButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            
            #cancelButton:hover, #submitButton:hover {
                background-color: #2980b9;
            }
            
            #cancelButton:pressed, #submitButton:pressed {
                background-color: #1f6dad;
            }
            
            #cancelButton {
                background-color: #e0e0e0;
                color: #2c3e50;
            }
            
            #cancelButton:hover {
                background-color: #d0d0d0;
            }
            
            #cancelButton:pressed {
                background-color: #c0c0c0;
            }
        """)
    
    def submit_prompt(self):
        """Soumettre le prompt personnalisé"""
        prompt = self.prompt_input.toPlainText().strip()
        
        if not prompt:
            return
        
        # Émettre le signal avec le prompt
        self.prompt_submitted.emit(prompt)
        self.accept()
    
    def accept_prompt(self):
        self.submit_prompt()
    
    def get_prompt(self):
        """Récupérer le prompt saisi"""
        return self.prompt_input.toPlainText().strip()
    
    @staticmethod
    def show_prompt_dialog(selected_text, parent=None):
        """Méthode statique pour afficher le dialogue et récupérer le prompt"""
        dialog = PromptDialog(selected_text, parent)
        result = dialog.exec()
        
        if result == QDialog.Accepted:
            return dialog.prompt_input.toPlainText().strip()
        
        return None
