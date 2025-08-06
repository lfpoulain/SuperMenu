#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QTabWidget,
    QComboBox, QTextEdit, QGroupBox, QFormLayout,
    QMessageBox, QSystemTrayIcon, QMenu, QCheckBox, QApplication,
    QDialog, QStyle, QInputDialog, QSpinBox, QFileDialog
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon, QAction, QKeySequence

from src.config.settings import Settings
from src.utils.hotkey_manager import HotkeyManager
from src.ui.screenshot_dialog import ScreenshotDialog
import uuid

class MainWindow(QMainWindow):
    """Main application window for settings and configuration"""
    
    def __init__(self, settings, context_menu_manager=None, hotkey_manager=None, voice_hotkey_manager=None, screenshot_hotkey_manager=None):
        super().__init__()
        self.settings = settings
        self.context_menu_manager = context_menu_manager # Stocker la référence
        self.tray_icon = None
        # self.hotkey_manager = None  # Sera initialisé plus tard
        # self.voice_hotkey_manager = None
        # self.screenshot_hotkey_manager = None # Ajout pour le gestionnaire de raccourci de capture d'écran

        # Stocker les références aux gestionnaires de raccourcis passés
        self.hotkey_manager = hotkey_manager
        self.voice_hotkey_manager = voice_hotkey_manager
        self.screenshot_hotkey_manager = screenshot_hotkey_manager
        
        # Set window properties
        self.setWindowTitle("SuperMenu - Configuration")
        self.setMinimumSize(800, 600)
        
        # Create the central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Create the main layout
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create the tab widget
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_general_tab()
        self.create_prompts_tab()
        self.create_voice_prompts_tab()
        self.create_about_tab()
        
        # Create bottom buttons
        self.create_bottom_buttons()
    
    def create_general_tab(self):
        """Create the general settings tab"""
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        
        # API key section
        api_key_group = QGroupBox("Clé API OpenAI")
        api_key_layout = QVBoxLayout(api_key_group)
        
        # API key input
        api_key_label = QLabel("Clé API:")
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setText(self.settings.get_api_key())
        
        # Model selection
        model_label = QLabel("Modèle:")
        self.model_combo = QComboBox()
        self.model_combo.addItems(["gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"])
        self.model_combo.setCurrentText(self.settings.get_model())

        # API base URL input
        api_base_label = QLabel("URL de l'API:")
        self.api_base_input = QLineEdit()
        self.api_base_input.setText(self.settings.get_api_base_url())
        
        # Save API key button
        save_api_key_button = QPushButton("Enregistrer la clé API")
        save_api_key_button.clicked.connect(self.save_api_key)
        
        # Add widgets to layout
        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.api_key_input)
        api_key_layout.addWidget(model_label)
        api_key_layout.addWidget(self.model_combo)
        api_key_layout.addWidget(api_base_label)
        api_key_layout.addWidget(self.api_base_input)
        api_key_layout.addWidget(save_api_key_button)
        
        # Hotkey section
        hotkey_group = QGroupBox("Raccourcis clavier")
        hotkey_layout = QVBoxLayout(hotkey_group)
        
        # Main Hotkey info
        self.hotkey_label = QLabel(f"Raccourci principal : {self.settings.get_hotkey()}")
        hotkey_layout.addWidget(self.hotkey_label)
        
        # Change main hotkey button
        change_hotkey_button = QPushButton("Modifier le raccourci principal")
        change_hotkey_button.clicked.connect(self.change_hotkey)
        hotkey_layout.addWidget(change_hotkey_button)
        
        # Voice Hotkey info
        self.voice_hotkey_label = QLabel(f"Raccourci vocal : {self.settings.get_voice_hotkey()}")
        hotkey_layout.addWidget(self.voice_hotkey_label)
        
        # Change voice hotkey button
        change_voice_hotkey_button = QPushButton("Modifier le raccourci vocal")
        change_voice_hotkey_button.clicked.connect(self.change_voice_hotkey)
        hotkey_layout.addWidget(change_voice_hotkey_button)
        
        # Screenshot Hotkey info
        self.screenshot_hotkey_label = QLabel(f"Raccourci capture d'écran : {self.settings.get_screenshot_hotkey()}")
        hotkey_layout.addWidget(self.screenshot_hotkey_label)
        
        # Change screenshot hotkey button
        change_screenshot_hotkey_button = QPushButton("Modifier le raccourci de capture d'écran")
        change_screenshot_hotkey_button.clicked.connect(self.change_screenshot_hotkey)
        hotkey_layout.addWidget(change_screenshot_hotkey_button)
        
        # Microphone section
        microphone_group = QGroupBox("Microphone pour la reconnaissance vocale")
        microphone_layout = QVBoxLayout(microphone_group)
        
        # Microphone selection
        microphone_label = QLabel("Sélectionnez un microphone:")
        microphone_layout.addWidget(microphone_label)
        
        self.microphone_combo = QComboBox()
        self.populate_microphone_combo()
        microphone_layout.addWidget(self.microphone_combo)
        
        # Refresh microphone list button
        refresh_mic_button = QPushButton("Actualiser la liste")
        refresh_mic_button.clicked.connect(self.populate_microphone_combo)
        microphone_layout.addWidget(refresh_mic_button)
        
        # Save microphone button
        save_mic_button = QPushButton("Enregistrer la sélection")
        save_mic_button.clicked.connect(self.save_microphone_selection)
        microphone_layout.addWidget(save_mic_button)
        
        # Theme section
        theme_group = QGroupBox("Thème de l'application")
        theme_layout = QVBoxLayout(theme_group)
        
        # Theme selection
        theme_label = QLabel("Sélectionnez un thème:")
        theme_layout.addWidget(theme_label)
        
        self.theme_combo = QComboBox()
        # Ajouter les thèmes disponibles
        for theme in self.settings.available_themes:
            # Convertir le nom du thème pour l'affichage (première lettre en majuscule)
            display_name = theme.capitalize()
            if theme == "bee":
                display_name = "Abeille"
            self.theme_combo.addItem(display_name, theme)
        
        # Sélectionner le thème actuel
        current_theme = self.settings.get_theme()
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == current_theme:
                self.theme_combo.setCurrentIndex(i)
                break
                
        theme_layout.addWidget(self.theme_combo)
        
        # Save theme button
        save_theme_button = QPushButton("Appliquer le thème")
        save_theme_button.clicked.connect(self.save_theme_selection)
        theme_layout.addWidget(save_theme_button)
        
        # Add groups to layout
        general_layout.addWidget(api_key_group)
        general_layout.addWidget(hotkey_group)
        general_layout.addWidget(microphone_group)
        general_layout.addWidget(theme_group)
        general_layout.addStretch()
        
        # Add tab to tab widget
        self.tab_widget.addTab(general_tab, "Général")
    
    def create_prompts_tab(self):
        """Create the prompts settings tab"""
        prompts_tab = QWidget()
        layout = QVBoxLayout(prompts_tab)
        
        # Prompt selection
        prompt_selection_layout = QHBoxLayout()
        prompt_selection_layout.addWidget(QLabel("Sélectionner un prompt:"))
        
        self.prompt_combo = QComboBox()
        self.populate_prompt_combo()
        prompt_selection_layout.addWidget(self.prompt_combo)
        
        # Boutons d'ajout et de suppression
        add_prompt_button = QPushButton("Ajouter")
        add_prompt_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        add_prompt_button.clicked.connect(self.add_prompt)
        prompt_selection_layout.addWidget(add_prompt_button)
        
        delete_prompt_button = QPushButton("Supprimer")
        delete_prompt_button.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        delete_prompt_button.clicked.connect(self.delete_prompt)
        prompt_selection_layout.addWidget(delete_prompt_button)
        
        layout.addLayout(prompt_selection_layout)

        # Import/Export buttons
        import_export_layout = QHBoxLayout()
        export_button = QPushButton("Exporter les Prompts")
        export_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        export_button.clicked.connect(self.export_all_prompts) # Nouvelle méthode globale
        import_export_layout.addWidget(export_button)

        import_button = QPushButton("Importer les Prompts")
        import_button.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        import_button.clicked.connect(self.import_all_prompts) # Nouvelle méthode globale
        import_export_layout.addWidget(import_button)
        layout.addLayout(import_export_layout)
        
        # Prompt editing
        prompt_group = QGroupBox("Éditer le prompt")
        prompt_layout = QFormLayout(prompt_group)
        
        self.prompt_name_input = QLineEdit()
        prompt_layout.addRow("Nom affiché:", self.prompt_name_input)
        
        self.prompt_text_input = QTextEdit()
        prompt_layout.addRow("Prompt:", self.prompt_text_input)
        
        self.prompt_status_input = QLineEdit()
        prompt_layout.addRow("Message de statut:", self.prompt_status_input)
        
        self.prompt_insert_directly = QCheckBox("Insérer directement le résultat (sans afficher la fenêtre de réponse)")
        self.prompt_insert_directly.setChecked(False)
        prompt_layout.addRow("", self.prompt_insert_directly)
        
        self.prompt_position_input = QSpinBox()
        self.prompt_position_input.setMinimum(1)
        self.prompt_position_input.setMaximum(999)
        self.prompt_position_input.setValue(999)
        prompt_layout.addRow("Position dans le menu:", self.prompt_position_input)
        
        layout.addWidget(prompt_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        save_prompt_button = QPushButton("Enregistrer les modifications")
        save_prompt_button.clicked.connect(self.save_prompt)
        buttons_layout.addWidget(save_prompt_button)
        
        reset_prompt_button = QPushButton("Réinitialiser ce prompt")
        reset_prompt_button.clicked.connect(self.reset_prompt)
        buttons_layout.addWidget(reset_prompt_button)
        
        layout.addLayout(buttons_layout)
        
        # Connect prompt selection change
        self.prompt_combo.currentIndexChanged.connect(self.load_prompt)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        # Add the tab
        self.tab_widget.addTab(prompts_tab, "Prompts")
        
        # Load the first prompt
        if self.prompt_combo.count() > 0:
            self.load_prompt(0)
    
    def create_voice_prompts_tab(self):
        """Create the voice prompts settings tab"""
        voice_prompts_tab = QWidget()
        layout = QVBoxLayout(voice_prompts_tab)
        
        # Prompt selection
        prompt_selection_layout = QHBoxLayout()
        prompt_selection_layout.addWidget(QLabel("Sélectionner un prompt vocal:"))
        
        self.voice_prompt_combo = QComboBox()
        self.populate_voice_prompt_combo()
        prompt_selection_layout.addWidget(self.voice_prompt_combo)
        
        # Boutons d'ajout et de suppression
        add_prompt_button = QPushButton("Ajouter")
        add_prompt_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        add_prompt_button.clicked.connect(self.add_voice_prompt)
        prompt_selection_layout.addWidget(add_prompt_button)
        
        delete_prompt_button = QPushButton("Supprimer")
        delete_prompt_button.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        delete_prompt_button.clicked.connect(self.delete_voice_prompt)
        prompt_selection_layout.addWidget(delete_prompt_button)
        
        layout.addLayout(prompt_selection_layout)

        # Import/Export buttons (shared with text prompts for a single file export)
        # On peut choisir de les dupliquer ici pour la visibilité ou de les laisser uniquement dans l'onglet des prompts textuels.
        # Pour cet exemple, je les ajoute aussi ici pour la commodité de l'utilisateur.
        import_export_voice_layout = QHBoxLayout()
        export_voice_button = QPushButton("Exporter les Prompts (Tous)")
        export_voice_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        export_voice_button.clicked.connect(self.export_all_prompts) # Même méthode globale
        import_export_voice_layout.addWidget(export_voice_button)

        import_voice_button = QPushButton("Importer les Prompts (Tous)")
        import_voice_button.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        import_voice_button.clicked.connect(self.import_all_prompts) # Même méthode globale
        import_export_voice_layout.addWidget(import_voice_button)
        layout.addLayout(import_export_voice_layout)
        
        # Prompt editing
        prompt_group = QGroupBox("Éditer le prompt vocal")
        prompt_layout = QFormLayout(prompt_group)
        
        self.voice_prompt_name_input = QLineEdit()
        prompt_layout.addRow("Nom affiché:", self.voice_prompt_name_input)
        
        self.voice_prompt_text_input = QTextEdit()
        prompt_layout.addRow("Prompt:", self.voice_prompt_text_input)
        
        self.voice_prompt_status_input = QLineEdit()
        prompt_layout.addRow("Message de statut:", self.voice_prompt_status_input)
        
        self.voice_prompt_insert_directly = QCheckBox("Insérer directement le résultat (sans afficher la fenêtre de réponse)")
        self.voice_prompt_insert_directly.setChecked(True)
        prompt_layout.addRow("", self.voice_prompt_insert_directly)
        
        self.voice_prompt_include_selected_text = QCheckBox("Inclure le texte sélectionné dans la requête vocale")
        self.voice_prompt_include_selected_text.setChecked(False)
        prompt_layout.addRow("", self.voice_prompt_include_selected_text)
        
        prompt_layout.addRow("Ordre des éléments:", QLabel("Choisissez l'ordre des éléments dans le prompt:"))
        
        self.voice_prompt_order_combo = QComboBox()
        self.voice_prompt_order_combo.addItem("Prompt → Transcription → Texte sélectionné", "prompt_transcription_selected")
        self.voice_prompt_order_combo.addItem("Prompt → Texte sélectionné → Transcription", "prompt_selected_transcription")
        self.voice_prompt_order_combo.addItem("Texte sélectionné → Prompt → Transcription", "selected_prompt_transcription")
        self.voice_prompt_order_combo.addItem("Transcription → Prompt → Texte sélectionné", "transcription_prompt_selected")
        self.voice_prompt_order_combo.addItem("Transcription → Texte sélectionné → Prompt", "transcription_selected_prompt")
        self.voice_prompt_order_combo.addItem("Texte sélectionné → Transcription → Prompt", "selected_transcription_prompt")
        prompt_layout.addRow("", self.voice_prompt_order_combo)
        
        self.voice_prompt_position_input = QSpinBox()
        self.voice_prompt_position_input.setMinimum(1)
        self.voice_prompt_position_input.setMaximum(999)
        self.voice_prompt_position_input.setValue(999)
        prompt_layout.addRow("Position dans le menu:", self.voice_prompt_position_input)
        
        layout.addWidget(prompt_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        save_prompt_button = QPushButton("Enregistrer les modifications")
        save_prompt_button.clicked.connect(self.save_voice_prompt)
        buttons_layout.addWidget(save_prompt_button)
        
        reset_prompt_button = QPushButton("Réinitialiser ce prompt")
        reset_prompt_button.clicked.connect(self.reset_voice_prompt)
        buttons_layout.addWidget(reset_prompt_button)
        
        layout.addLayout(buttons_layout)
        
        # Connect prompt selection change
        self.voice_prompt_combo.currentIndexChanged.connect(self.load_voice_prompt)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        # Add the tab
        self.tab_widget.addTab(voice_prompts_tab, "Prompts Vocaux")
        
        # Load the first prompt
        if self.voice_prompt_combo.count() > 0:
            self.load_voice_prompt(0)
    
    def create_about_tab(self):
        """Create the about tab"""
        about_tab = QWidget()
        layout = QVBoxLayout(about_tab)
        
        # Title
        title_label = QLabel("SuperMenu")
        title_label.setAlignment(Qt.AlignCenter)
        font = title_label.font()
        font.setPointSize(16)
        font.setBold(True)
        title_label.setFont(font)
        layout.addWidget(title_label)
        
        # Version
        version_label = QLabel("Version 1.0.0")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        # Description
        description_text = QTextEdit()
        description_text.setReadOnly(True)
        description_text.setHtml("""
        <h1 style="text-align: center; color: #4CAF50;">SuperMenu</h1>
        <p style="text-align: center; font-size: 10px; color: #777;">Version 1.0.0</p>
        <p>SuperMenu est une application conçue pour simplifier et améliorer votre interaction avec les modèles d'IA d'OpenAI. Elle offre un accès rapide et personnalisable à une variété de fonctionnalités directement depuis votre bureau.</p>
        
        <h3>Fonctionnalités clés :</h3>
        <ul>
            <li>Accès rapide à des prompts textuels personnalisés via un menu contextuel.</li>
            <li>Interaction vocale pour dicter des prompts et recevoir des réponses.</li>
            <li>Capture d'écran et analyse d'image avec l'IA.</li>
            <li>Sélection dynamique du modèle OpenAI pour les requêtes texte et image.</li>
            <li>Gestion des thèmes pour personnaliser l'apparence.</li>
            <li>Export et import faciles de vos configurations de prompts.</li>
            <li>Raccourcis clavier configurables pour toutes les fonctionnalités principales.</li>
        </ul>
        
        """)
        layout.addWidget(description_text)
        
        # Add the tab
        self.tab_widget.addTab(about_tab, "À propos")
    
    def create_bottom_buttons(self):
        """Create the bottom buttons"""
        buttons_layout = QHBoxLayout()
        
        # Reset all button
        reset_all_button = QPushButton("Réinitialiser tous les paramètres")
        reset_all_button.clicked.connect(self.reset_all_settings)
        buttons_layout.addWidget(reset_all_button)
        
        # Spacer
        buttons_layout.addStretch()
        
        # Close button
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.hide)
        buttons_layout.addWidget(close_button)
        
        self.main_layout.addLayout(buttons_layout)
    
    def populate_prompt_combo(self):
        """Populate the prompt combo box"""
        self.prompt_combo.clear()
        
        # Get prompts from settings
        prompts = self.settings.get_prompts()
        
        # Add prompts to combo box
        for prompt_id, prompt_data in prompts.items():
            self.prompt_combo.addItem(prompt_data["name"], prompt_id)
    
    def load_prompt(self, index):
        """Load the selected prompt into the editing fields"""
        if index < 0 or self.prompt_combo.count() == 0:
            return
            
        prompt_id = self.prompt_combo.currentData()
        prompt_data = self.settings.get_prompt(prompt_id)
        
        if prompt_data:
            self.prompt_name_input.setText(prompt_data["name"])
            self.prompt_text_input.setText(prompt_data["prompt"])
            self.prompt_status_input.setText(prompt_data["status"])
            self.prompt_insert_directly.setChecked(prompt_data.get("insert_directly", False))
            self.prompt_position_input.setValue(prompt_data.get("position", 999))
    
    def save_api_key(self):
        """Save the API key to settings"""
        api_key = self.api_key_input.text().strip()
        model = self.model_combo.currentText()
        api_base = self.api_base_input.text().strip() or self.settings.default_api_base_url

        # Enregistrer l'URL de base de l'API quelle que soit la clé
        self.settings.set_api_base_url(api_base)

        if api_key or "api.openai.com" not in api_base:
            self.settings.set_api_key(api_key)
            self.settings.set_model(model)
            QMessageBox.information(self, "Succès", "Configuration API enregistrée avec succès!")
            # Mettre à jour la configuration du client API dans ContextMenuManager
            if self.context_menu_manager:
                self.context_menu_manager.update_client_config()
        else:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer une clé API valide.")

    def populate_microphone_combo(self):
        """Populate the microphone combo box with available microphones"""
        from src.audio.voice_recognition import VoiceRecognition
        
        # Clear the combo box
        self.microphone_combo.clear()
        
        # Add default option
        self.microphone_combo.addItem("Microphone par défaut du système", -1)
        
        # Get available microphones
        microphones = VoiceRecognition.list_microphones()
        
        # Add microphones to combo box
        for index, name in microphones:
            self.microphone_combo.addItem(f"{name}", index)
        
        # Set current selection based on settings
        current_mic_index = self.settings.get_microphone_index()
        
        if current_mic_index is None:
            # Default microphone
            self.microphone_combo.setCurrentIndex(0)
        else:
            # Find the index in the combo box that matches the stored microphone index
            for i in range(1, self.microphone_combo.count()):
                if self.microphone_combo.itemData(i) == current_mic_index:
                    self.microphone_combo.setCurrentIndex(i)
                    break
    
    def save_microphone_selection(self):
        """Save the selected microphone to settings"""
        selected_index = self.microphone_combo.currentIndex()
        mic_index = self.microphone_combo.itemData(selected_index)
        
        # Update settings
        self.settings.set_microphone_index(mic_index)
        
        QMessageBox.information(self, "Succès", "Microphone enregistré avec succès!")
    
    def change_hotkey(self):
        """Modifier le raccourci clavier"""
        if not self.hotkey_manager:
            # Cette situation ne devrait plus se produire si HotkeyManager est toujours passé
            QMessageBox.warning(self, "Erreur", "HotkeyManager non initialisé.")
            return
            # from src.utils.hotkey_manager import HotkeyManager
            # self.hotkey_manager = HotkeyManager(self.settings)
        
        # Désactiver temporairement le raccourci actuel
        self.hotkey_manager.unregister_hotkey()
        
        # Afficher le dialogue d'enregistrement de raccourci
        success = self.hotkey_manager.show_hotkey_recorder()
        
        if success:
            # Mettre à jour l'étiquette avec le nouveau raccourci
            self.hotkey_label.setText(f"Raccourci principal : {self.settings.get_hotkey()}")
            
            # Demander à l'utilisateur s'il souhaite redémarrer l'application
            reply = QMessageBox.question(
                self,
                "Raccourci modifié",
                f"Le raccourci a été modifié avec succès en {self.settings.get_hotkey()}.\n\n"
                "Pour que le nouveau raccourci soit pris en compte, l'application doit être redémarrée.\n\n"
                "Voulez-vous redémarrer l'application maintenant ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                # Redémarrer l'application
                self.restart_application()
        else:
            # Réenregistrer l'ancien raccourci
            self.hotkey_manager.register_hotkey()
    
    def change_voice_hotkey(self):
        """Modifier le raccourci vocal"""
        if not self.voice_hotkey_manager:
            # Cette situation ne devrait plus se produire
            QMessageBox.warning(self, "Erreur", "VoiceHotkeyManager non initialisé.")
            return
            # from src.utils.hotkey_manager import HotkeyManager
            # self.voice_hotkey_manager = HotkeyManager(self.settings, voice_hotkey=True)
        
        # Désactiver temporairement le raccourci actuel
        self.voice_hotkey_manager.unregister_hotkey()
        
        # Afficher le dialogue d'enregistrement de raccourci
        success = self.voice_hotkey_manager.show_hotkey_recorder()
        
        if success:
            # Mettre à jour l'étiquette avec le nouveau raccourci
            self.voice_hotkey_label.setText(f"Raccourci vocal : {self.settings.get_voice_hotkey()}")
            
            # Demander à l'utilisateur s'il souhaite redémarrer l'application
            reply = QMessageBox.question(
                self,
                "Raccourci modifié",
                f"Le raccourci vocal a été modifié avec succès en {self.settings.get_voice_hotkey()}.\n\n"
                "Pour que le nouveau raccourci soit pris en compte, l'application doit être redémarrée.\n\n"
                "Voulez-vous redémarrer l'application maintenant ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                # Redémarrer l'application
                self.restart_application()
        else:
            # Réenregistrer l'ancien raccourci
            self.voice_hotkey_manager.register_hotkey()
    
    def change_screenshot_hotkey(self):
        """Modifier le raccourci de capture d'écran"""
        if not self.screenshot_hotkey_manager:
            # Cette situation ne devrait plus se produire
            QMessageBox.warning(self, "Erreur", "ScreenshotHotkeyManager non initialisé.")
            return
            # from src.utils.hotkey_manager import HotkeyManager
            # self.screenshot_hotkey_manager = HotkeyManager(self.settings, screenshot_hotkey=True)

        # Désactiver temporairement le raccourci actuel
        self.screenshot_hotkey_manager.unregister_hotkey()
        
        # Afficher le dialogue d'enregistrement de raccourci
        success = self.screenshot_hotkey_manager.show_hotkey_recorder()
        
        if success:
            # Mettre à jour l'étiquette avec le nouveau raccourci
            self.screenshot_hotkey_label.setText(f"Raccourci capture d'écran : {self.settings.get_screenshot_hotkey()}")
            
            # Demander à l'utilisateur s'il souhaite redémarrer l'application
            reply = QMessageBox.question(
                self,
                "Raccourci modifié",
                f"Le raccourci de capture d'écran a été modifié avec succès en {self.settings.get_screenshot_hotkey()}.\n\n"
                "Pour que le nouveau raccourci soit pris en compte, l'application doit être redémarrée.\n\n"
                "Voulez-vous redémarrer l'application maintenant ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                # Redémarrer l'application
                self.restart_application()
        else:
            # Réenregistrer l'ancien raccourci
            self.screenshot_hotkey_manager.register_hotkey()
    
    def restart_application(self):
        """Redémarrer l'application"""
        import os
        import sys
        import subprocess
        
        # Fermer l'application actuelle
        QApplication.quit()
        
        # Lancer un nouveau processus pour redémarrer l'application
        if getattr(sys, 'frozen', False):
            # Si l'application est compilée (exe)
            subprocess.Popen([sys.executable])
        else:
            # Si l'application est en mode développement
            script_path = os.path.abspath(sys.argv[0])
            subprocess.Popen([sys.executable, script_path])
    
    def save_prompt(self):
        """Save the prompt"""
        if self.prompt_combo.count() == 0:
            return
            
        prompt_id = self.prompt_combo.currentData()
        name = self.prompt_name_input.text()
        prompt = self.prompt_text_input.toPlainText()
        status = self.prompt_status_input.text()
        insert_directly = self.prompt_insert_directly.isChecked()
        position = self.prompt_position_input.value()
        
        # Vérifier que les champs ne sont pas vides
        if not name or not prompt or not status:
            QMessageBox.warning(self, "Champs incomplets", 
                              "Veuillez remplir tous les champs (nom, prompt et statut).")
            return
        
        # Mettre à jour le prompt
        self.settings.update_prompt(prompt_id, name, prompt, status, insert_directly, position)
        
        # Mettre à jour le nom dans le combo
        self.prompt_combo.setItemText(self.prompt_combo.currentIndex(), name)
        
        QMessageBox.information(self, "Prompt enregistré", 
                              f"Le prompt '{name}' a été enregistré avec succès.")
    
    def reset_prompt(self):
        """Reset the current prompt to default"""
        if self.prompt_combo.count() == 0:
            return
            
        index = self.prompt_combo.currentIndex()
        prompt_id = self.prompt_combo.currentData()
        
        # Confirm reset
        reply = QMessageBox.question(
            self,
            "Confirmer la réinitialisation",
            f"Êtes-vous sûr de vouloir réinitialiser le prompt '{self.prompt_combo.itemText(index)}' ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Get the default prompt
            default_prompts = self.settings.default_prompts
            if prompt_id in default_prompts:
                default_prompt = default_prompts[prompt_id]
                
                # Update the settings
                self.settings.update_prompt(
                    prompt_id,
                    default_prompt["name"],
                    default_prompt["prompt"],
                    default_prompt["status"],
                    default_prompt.get("insert_directly", False),
                    default_prompt.get("position", 999)
                )
                
                # Update the form
                self.prompt_name_input.setText(default_prompt["name"])
                self.prompt_text_input.setText(default_prompt["prompt"])
                self.prompt_status_input.setText(default_prompt["status"])
                self.prompt_insert_directly.setChecked(default_prompt.get("insert_directly", False))
                self.prompt_position_input.setValue(default_prompt.get("position", 999))
                
                # Update the combo box
                self.prompt_combo.setItemText(index, default_prompt["name"])
                
                QMessageBox.information(self, "Succès", "Prompt réinitialisé avec succès.")
    
    def reset_all_settings(self):
        """Reset all settings to defaults"""
        # Confirm reset
        reply = QMessageBox.question(
            self,
            "Confirmer la réinitialisation",
            "Êtes-vous sûr de vouloir réinitialiser tous les paramètres ? Cette action ne peut pas être annulée.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Reset settings
            self.settings.reset_to_defaults()
            
            # Update the UI
            self.populate_prompt_combo()
            self.populate_voice_prompt_combo()
            
            # Reload the API key
            self.api_key_input.setText(self.settings.get_api_key())
            
            # Reload the model
            self.model_combo.setCurrentText(self.settings.get_model())
            
            # Reload the hotkeys
            self.hotkey_label.setText(f"Raccourci principal : {self.settings.get_hotkey()}")
            self.voice_hotkey_label.setText(f"Raccourci vocal : {self.settings.get_voice_hotkey()}")
            self.screenshot_hotkey_label.setText(f"Raccourci capture d'écran : {self.settings.get_screenshot_hotkey()}")
            
            # Load the first prompts
            if self.prompt_combo.count() > 0:
                self.load_prompt(0)
                
            if self.voice_prompt_combo.count() > 0:
                self.load_voice_prompt(0)
            
            QMessageBox.information(self, "Succès", "Tous les paramètres ont été réinitialisés avec succès.")
            # Mettre à jour la configuration du client API dans ContextMenuManager après réinitialisation
            if self.context_menu_manager:
                self.context_menu_manager.update_client_config()
    
    def setup_tray_icon(self):
        """Set up the system tray icon"""
        # Create the tray icon
        self.tray_icon = QSystemTrayIcon(self)
        
        # Set the icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "resources", "icons", "icon.png")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            # Utiliser une icône standard de Qt qui existe
            self.tray_icon.setIcon(QIcon.fromTheme("computer", QIcon.fromTheme("application-x-executable")))
        
        # Create the tray menu
        tray_menu = QMenu()
        
        # Add actions to the tray menu
        open_action = QAction("Ouvrir", self)
        open_action.triggered.connect(self.show)
        tray_menu.addAction(open_action)
        
        tray_menu.addSeparator()
        
        exit_action = QAction("Quitter", self)
        exit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(exit_action)
        
        # Set the tray menu
        self.tray_icon.setContextMenu(tray_menu)
        
        # Connect the activated signal
        self.tray_icon.activated.connect(self.tray_icon_activated)
        
        # Show the tray icon
        self.tray_icon.show()
    
    def tray_icon_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
    
    def quit_application(self):
        """Quit the application"""
        QApplication.quit()
    
    def closeEvent(self, event):
        """Handle the close event"""
        # Hide the window instead of closing it
        event.ignore()
        self.hide()
        
        # Show a balloon message
        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "SuperMenu",
                "L'application continue à s'exécuter en arrière-plan. Cliquez sur l'icône pour l'ouvrir à nouveau.",
                QSystemTrayIcon.Information,
                2000
            )

    def add_prompt(self):
        """Ajouter un nouveau prompt"""
        # Demander un ID pour le nouveau prompt
        prompt_id, ok = QInputDialog.getText(
            self,
            "Nouvel ID de prompt",
            "Entrez un identifiant unique pour le nouveau prompt (lettres, chiffres et underscore uniquement):"
        )
        
        if not ok or not prompt_id:
            return
        
        # Valider l'ID (lettres, chiffres et underscore uniquement)
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', prompt_id):
            QMessageBox.warning(
                self,
                "ID invalide",
                "L'ID doit contenir uniquement des lettres, des chiffres et des underscores."
            )
            return
        
        # Créer un nouveau prompt avec des valeurs par défaut
        new_prompt_id = self.settings.add_prompt(
            prompt_id,
            f"Nouveau prompt ({prompt_id})",
            "Entrez votre prompt ici...",
            "Traitement en cours...",
            False,
            999
        )
        
        # Mettre à jour la liste des prompts
        self.populate_prompt_combo()
        
        # Sélectionner le nouveau prompt
        index = self.prompt_combo.findData(new_prompt_id)
        if index >= 0:
            self.prompt_combo.setCurrentIndex(index)
            self.load_prompt(index)
        
        # Afficher un message de confirmation
        QMessageBox.information(
            self,
            "Prompt ajouté",
            f"Le nouveau prompt '{new_prompt_id}' a été ajouté avec succès. Vous pouvez maintenant le personnaliser."
        )
    
    def delete_prompt(self):
        """Supprimer un prompt"""
        # Vérifier qu'un prompt est sélectionné
        index = self.prompt_combo.currentIndex()
        if index < 0:
            return
        
        # Obtenir l'ID et le nom du prompt
        prompt_id = self.prompt_combo.itemData(index)
        prompt_name = self.prompt_combo.itemText(index)
        
        # Vérifier qu'il reste au moins un prompt après suppression
        if self.prompt_combo.count() <= 1:
            QMessageBox.warning(
                self,
                "Impossible de supprimer",
                "Vous ne pouvez pas supprimer le dernier prompt. Il doit toujours y avoir au moins un prompt disponible."
            )
            return
        
        # Demander confirmation
        reply = QMessageBox.question(
            self,
            "Confirmer la suppression",
            f"Êtes-vous sûr de vouloir supprimer le prompt '{prompt_name}' ?\n\nCette action est irréversible.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Supprimer le prompt
        if self.settings.delete_prompt(prompt_id):
            # Mettre à jour la liste des prompts
            self.populate_prompt_combo()
            
            # Sélectionner le premier prompt
            if self.prompt_combo.count() > 0:
                self.prompt_combo.setCurrentIndex(0)
                self.load_prompt(0)
            
            # Afficher un message de confirmation
            QMessageBox.information(
                self,
                "Prompt supprimé",
                f"Le prompt '{prompt_name}' a été supprimé avec succès."
            )
        else:
            # Afficher un message d'erreur
            QMessageBox.warning(
                self,
                "Erreur",
                f"Impossible de supprimer le prompt '{prompt_name}'."
            )

    def populate_voice_prompt_combo(self):
        """Populate the voice prompt combo box with available voice prompts"""
        self.voice_prompt_combo.clear()
        
        prompts = self.settings.get_voice_prompts()
        
        # Ajouter les prompts au combo box
        for prompt_id, prompt_data in prompts.items():
            self.voice_prompt_combo.addItem(prompt_data["name"], prompt_id)
    
    def load_voice_prompt(self, index):
        """Load the selected voice prompt into the editing fields"""
        if index < 0 or self.voice_prompt_combo.count() == 0:
            return
            
        prompt_id = self.voice_prompt_combo.currentData()
        prompt_data = self.settings.get_voice_prompt(prompt_id)
        
        if prompt_data:
            self.voice_prompt_name_input.setText(prompt_data["name"])
            self.voice_prompt_text_input.setText(prompt_data["prompt"])
            self.voice_prompt_status_input.setText(prompt_data["status"])
            self.voice_prompt_insert_directly.setChecked(prompt_data.get("insert_directly", True))
            self.voice_prompt_position_input.setValue(prompt_data.get("position", 999))
            self.voice_prompt_include_selected_text.setChecked(prompt_data.get("include_selected_text", False))
            
            # Sélectionner l'ordre des éléments
            prompt_order = prompt_data.get("prompt_order", "prompt_transcription_selected")
            index = self.voice_prompt_order_combo.findData(prompt_order)
            if index >= 0:
                self.voice_prompt_order_combo.setCurrentIndex(index)
    
    def save_voice_prompt(self):
        """Save the current voice prompt"""
        if self.voice_prompt_combo.count() == 0:
            return
            
        prompt_id = self.voice_prompt_combo.currentData()
        name = self.voice_prompt_name_input.text()
        prompt = self.voice_prompt_text_input.toPlainText()
        status = self.voice_prompt_status_input.text()
        insert_directly = self.voice_prompt_insert_directly.isChecked()
        position = self.voice_prompt_position_input.value()
        include_selected_text = self.voice_prompt_include_selected_text.isChecked()
        prompt_order = self.voice_prompt_order_combo.currentData()
        
        # Vérifier que les champs ne sont pas vides
        if not name or not prompt or not status:
            QMessageBox.warning(self, "Champs incomplets", 
                              "Veuillez remplir tous les champs (nom, prompt et statut).")
            return
        
        # Mettre à jour le prompt
        self.settings.update_voice_prompt(
            prompt_id, 
            name, 
            prompt, 
            status, 
            insert_directly, 
            position, 
            include_selected_text,
            prompt_order
        )
        
        # Mettre à jour le nom dans le combo
        self.voice_prompt_combo.setItemText(self.voice_prompt_combo.currentIndex(), name)
        
        QMessageBox.information(self, "Prompt vocal enregistré", 
                              f"Le prompt vocal '{name}' a été enregistré avec succès.")
    
    def add_voice_prompt(self):
        """Add a new voice prompt"""
        # Générer un nouvel ID unique
        prompt_id = str(uuid.uuid4())
        
        # Ajouter le nouveau prompt avec des valeurs par défaut
        self.settings.add_voice_prompt(
            prompt_id,
            f"Nouveau prompt vocal ({prompt_id})",
            "Entrez votre prompt vocal ici...",
            "Traitement en cours...",
            True,
            999,
            False,
            "prompt_transcription_selected"
        )
        
        # Mettre à jour la liste des prompts
        self.populate_voice_prompt_combo()
        
        # Sélectionner le nouveau prompt
        index = self.voice_prompt_combo.findData(prompt_id)
        if index >= 0:
            self.voice_prompt_combo.setCurrentIndex(index)
        
        QMessageBox.information(self, "Prompt vocal ajouté", 
                              f"Le nouveau prompt vocal a été ajouté avec succès. Vous pouvez maintenant le configurer.")
    
    def delete_voice_prompt(self):
        """Delete the current voice prompt"""
        if self.voice_prompt_combo.count() == 0:
            return
            
        prompt_id = self.voice_prompt_combo.currentData()
        name = self.voice_prompt_combo.currentText()
        
        # Demander confirmation
        reply = QMessageBox.question(self, "Confirmer la suppression", 
                                  f"Êtes-vous sûr de vouloir supprimer le prompt vocal '{name}' ?",
                                  QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            return
        
        # Supprimer le prompt
        success = self.settings.delete_voice_prompt(prompt_id)
        
        if success:
            # Mettre à jour le combo
            self.populate_voice_prompt_combo()
            
            # Charger le premier prompt s'il en reste
            if self.voice_prompt_combo.count() > 0:
                self.voice_prompt_combo.setCurrentIndex(0)
            else:
                # Effacer les champs
                self.voice_prompt_name_input.clear()
                self.voice_prompt_text_input.clear()
                self.voice_prompt_status_input.clear()
                
            QMessageBox.information(self, "Prompt vocal supprimé", 
                                  f"Le prompt vocal '{name}' a été supprimé avec succès.")
        else:
            QMessageBox.warning(self, "Erreur de suppression", 
                              f"Une erreur s'est produite lors de la suppression du prompt vocal '{name}'.")
    
    def reset_voice_prompt(self):
        """Reset the current voice prompt to its default value"""
        if self.voice_prompt_combo.count() == 0:
            return
            
        prompt_id = self.voice_prompt_combo.currentData()
        name = self.voice_prompt_combo.currentText()
        
        # Vérifier si ce prompt existe dans les prompts par défaut
        if prompt_id in self.settings.default_voice_prompts:
            # Demander confirmation
            reply = QMessageBox.question(self, "Confirmer la réinitialisation", 
                                      f"Êtes-vous sûr de vouloir réinitialiser le prompt vocal '{name}' à sa valeur par défaut ?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply != QMessageBox.Yes:
                return
            
            # Réinitialiser le prompt
            default_prompt = self.settings.default_voice_prompts[prompt_id]
            self.settings.update_voice_prompt(
                prompt_id, 
                default_prompt["name"], 
                default_prompt["prompt"], 
                default_prompt["status"],
                default_prompt.get("insert_directly", True),
                default_prompt.get("position", 999),
                default_prompt.get("include_selected_text", False),
                default_prompt.get("prompt_order", "prompt_transcription_selected")
            )
            
            # Mettre à jour le combo et les champs
            self.populate_voice_prompt_combo()
            index = self.voice_prompt_combo.findData(prompt_id)
            if index >= 0:
                self.voice_prompt_combo.setCurrentIndex(index)
                
            QMessageBox.information(self, "Prompt vocal réinitialisé", 
                                  f"Le prompt vocal '{name}' a été réinitialisé à sa valeur par défaut.")
        else:
            QMessageBox.warning(self, "Réinitialisation impossible", 
                              f"Le prompt vocal '{name}' n'a pas de valeur par défaut.")

    def save_theme_selection(self):
        """Save the selected theme"""
        selected_index = self.theme_combo.currentIndex()
        theme = self.theme_combo.itemData(selected_index)
        
        # Update settings
        self.settings.set_theme(theme)
        
        # Demander à l'utilisateur s'il souhaite redémarrer l'application
        reply = QMessageBox.question(
            self,
            "Thème enregistré",
            f"Le thème '{theme}' a été enregistré avec succès.\n\n"
            "Pour que le nouveau thème soit appliqué, l'application doit être redémarrée.\n\n"
            "Voulez-vous redémarrer l'application maintenant ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            # Redémarrer l'application
            self.restart_application()

    def export_all_prompts(self):
        """Export all text and voice prompts to a JSON file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Exporter les Prompts", 
            os.path.join(os.path.expanduser("~"), "supermenu_prompts.json"), 
            "JSON Files (*.json)"
        )
        if file_path:
            success, message = self.settings.export_prompts(file_path)
            if success:
                QMessageBox.information(self, "Exportation Réussie", message)
            else:
                QMessageBox.warning(self, "Erreur d'Exportation", message)

    def import_all_prompts(self):
        """Import all text and voice prompts from a JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Importer les Prompts", 
            os.path.expanduser("~"), 
            "JSON Files (*.json)"
        )
        if file_path:
            reply = QMessageBox.question(self, "Confirmer l'Importation", 
                                           "L'importation remplacera tous vos prompts actuels. Voulez-vous continuer?",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                success, message = self.settings.import_prompts(file_path)
                if success:
                    QMessageBox.information(self, "Importation Réussie", message)
                    # Rafraîchir les listes de prompts dans l'UI
                    self.populate_prompt_combo()
                    self.populate_voice_prompt_combo()
                    # Optionnellement, sélectionner le premier prompt ou aucun
                    if self.prompt_combo.count() > 0:
                        self.prompt_combo.setCurrentIndex(0)
                        self.load_prompt_details(self.prompt_combo.itemData(0)) # Charger détails du premier prompt
                    else:
                        self.clear_prompt_details() # Effacer les détails s'il n'y a plus de prompts
                    
                    if self.voice_prompt_combo.count() > 0:
                        self.voice_prompt_combo.setCurrentIndex(0)
                        self.load_voice_prompt_details(self.voice_prompt_combo.itemData(0))
                    else:
                        self.clear_voice_prompt_details()
                else:
                    QMessageBox.warning(self, "Erreur d'Importation", message)
