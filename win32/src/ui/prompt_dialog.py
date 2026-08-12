#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dialogue de prompt personnalisé modernisé avec pyqtdarktheme
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QTextEdit, QPushButton, QFrame
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
        self.setWindowTitle("✨ GodMode - Prompt personnalisé")
        self.setMinimumSize(650, 450)
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
        instructions = QLabel("📝 Entrez votre prompt personnalisé ci-dessous. Le texte sélectionné sera traité selon ce prompt.")
        instructions.setStyleSheet("font-size: 13px; padding: 5px;")
        layout.addWidget(instructions)
        
        # Conteneur pour l'aperçu (texte ou image)
        self.preview_container = QVBoxLayout()
        
        # Afficher un aperçu du texte sélectionné
        if selected_text:
            preview_label = QLabel("📄 Texte sélectionné :")
            preview_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
            self.preview_container.addWidget(preview_label)
            
            preview_text = QTextEdit()
            preview_text.setReadOnly(True)
            preview_text.setMaximumHeight(100)
            preview_text.setText(selected_text[:500] + ("..." if len(selected_text) > 500 else ""))
            self.preview_container.addWidget(preview_text)
        
        layout.addLayout(self.preview_container)
        
        # Champ de saisie du prompt
        prompt_label = QLabel("⚙️ Votre prompt :")
        prompt_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(prompt_label)
        
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("Exemple : Résume ce texte en 3 points clés...")
        self.prompt_input.setMinimumHeight(150)
        layout.addWidget(self.prompt_input)
        
        # Boutons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("❌ Annuler")
        self.cancel_button.setMinimumWidth(120)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.submit_button = QPushButton("✅ Envoyer")
        self.submit_button.setMinimumWidth(120)
        self.submit_button.setDefault(True)  # Bouton par défaut
        self.submit_button.clicked.connect(self.accept_prompt)
        button_layout.addWidget(self.submit_button)
        
        layout.addLayout(button_layout)
        
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
        image_label = QLabel("🖼️ Image capturée :")
        image_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        self.preview_container.addWidget(image_label)
        
        # Créer un cadre pour l'image
        image_frame = QFrame()
        image_frame.setObjectName("imageFrame")
        image_frame.setFrameShape(QFrame.StyledPanel)
        image_frame.setFrameShadow(QFrame.Sunken)
        # Le style sera appliqué automatiquement par le thème
        
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
        self.setWindowTitle("✨ GodMode - Prompt personnalisé avec image")
    
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
