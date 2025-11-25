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

from src.config.settings import Settings, AVAILABLE_MODELS
from src.utils.hotkey_manager import HotkeyManager
from src.ui.screenshot_dialog import ScreenshotDialog
from src.utils.validators import Validators
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
        self.setMinimumSize(850, 650)
        self.resize(850, 650)
        
        # Create the central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Create the main layout
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create the tab widget
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_models_tab()
        self.create_prompts_tab()
        self.create_voice_prompts_tab()
        self.create_settings_tab()
        self.create_about_tab()
        
        # Create bottom buttons
        self.create_bottom_buttons()
    
    def create_models_tab(self):
        """Create the models configuration tab"""
        from PySide6.QtWidgets import QScrollArea
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Create the content widget
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        
        # Checkbox pour utiliser un endpoint personnalisé
        self.use_custom_endpoint_checkbox = QCheckBox("Activer un endpoint personnalisé (ex: Ollama)")
        self.use_custom_endpoint_checkbox.setChecked(self.settings.get_use_custom_endpoint())
        self.use_custom_endpoint_checkbox.toggled.connect(self.toggle_custom_endpoint)
        general_layout.addWidget(self.use_custom_endpoint_checkbox)
        
        # Section OpenAI (par défaut)
        self.openai_group = QGroupBox("OpenAI")
        openai_layout = QVBoxLayout(self.openai_group)
        
        # API key input
        api_key_label = QLabel("Clé API:")
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setText(self.settings.get_api_key())
        
        # Model selection
        model_label = QLabel("Modèle:")
        self.model_combo = QComboBox()
        self.model_combo.addItems(AVAILABLE_MODELS)
        self.model_combo.setCurrentText(self.settings.get_model())
        
        openai_layout.addWidget(api_key_label)
        openai_layout.addWidget(self.api_key_input)
        openai_layout.addWidget(model_label)
        openai_layout.addWidget(self.model_combo)
        
        # Section Endpoint personnalisé
        self.custom_group = QGroupBox("Endpoint personnalisé (Ollama, etc.)")
        custom_layout = QVBoxLayout(self.custom_group)
        
        # Custom endpoint input
        custom_endpoint_label = QLabel("URL de l'endpoint (ex: http://localhost:11434):")
        self.custom_endpoint_input = QLineEdit()
        self.custom_endpoint_input.setText(self.settings.get_custom_endpoint())
        self.custom_endpoint_input.setPlaceholderText("http://localhost:11434")
        
        # Custom model selection
        custom_model_label = QLabel("Modèle:")
        custom_model_layout = QHBoxLayout()
        self.custom_model_combo = QComboBox()
        self.custom_model_combo.setEditable(True)
        self.custom_model_combo.setPlaceholderText("Sélectionnez ou entrez un modèle")
        custom_model_layout.addWidget(self.custom_model_combo)
        
        # Refresh models button
        refresh_models_button = QPushButton("Actualiser")
        refresh_models_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_models_button.clicked.connect(self.refresh_custom_models)
        custom_model_layout.addWidget(refresh_models_button)
        
        custom_layout.addWidget(custom_endpoint_label)
        custom_layout.addWidget(self.custom_endpoint_input)
        custom_layout.addWidget(custom_model_label)
        custom_layout.addLayout(custom_model_layout)
        
        # Charger le modèle actuel
        current_custom_model = self.settings.get_custom_model()
        if current_custom_model:
            self.custom_model_combo.addItem(current_custom_model)
            self.custom_model_combo.setCurrentText(current_custom_model)
        
        # Note explicative
        note_label = QLabel("Note: La transcription audio restera sur OpenAI (4o-transcribe)")
        note_label.setStyleSheet("color: #666; font-style: italic;")
        custom_layout.addWidget(note_label)
        
        # Add groups to layout
        general_layout.addWidget(self.openai_group)
        general_layout.addWidget(self.custom_group)
        
        # Save API key button
        save_api_key_button = QPushButton("Enregistrer la configuration")
        save_api_key_button.clicked.connect(self.save_api_key)
        general_layout.addWidget(save_api_key_button)
        
        # Initialiser l'affichage selon l'état actuel
        self.toggle_custom_endpoint()
        
        general_layout.addStretch()
        
        # Set the content widget in the scroll area
        scroll_area.setWidget(general_tab)
        
        # Add tab to tab widget
        self.tab_widget.addTab(scroll_area, "🤖 Modèles")
    
    def create_prompts_tab(self):
        """Create the prompts settings tab"""
        prompts_tab = QWidget()
        layout = QVBoxLayout(prompts_tab)
        
        # Prompt selection
        prompt_selection_layout = QHBoxLayout()
        selection_label = QLabel("📋 Sélectionner un prompt :")
        selection_label.setStyleSheet("font-weight: bold;")
        prompt_selection_layout.addWidget(selection_label)
        
        self.prompt_combo = QComboBox()
        self.prompt_combo.setMinimumWidth(300)
        self.populate_prompt_combo()
        prompt_selection_layout.addWidget(self.prompt_combo)
        
        prompt_selection_layout.addStretch()
        
        # Boutons d'ajout et de suppression
        add_prompt_button = QPushButton("➕ Ajouter")
        add_prompt_button.setMinimumWidth(120)
        add_prompt_button.clicked.connect(self.add_prompt)
        prompt_selection_layout.addWidget(add_prompt_button)
        
        delete_prompt_button = QPushButton("🗑️ Supprimer")
        delete_prompt_button.setMinimumWidth(120)
        delete_prompt_button.clicked.connect(self.delete_prompt)
        prompt_selection_layout.addWidget(delete_prompt_button)
        
        layout.addLayout(prompt_selection_layout)
        
        # Prompt editing
        prompt_group = QGroupBox("✏️ Éditer le prompt")
        prompt_layout = QFormLayout(prompt_group)
        
        # Nom affiché
        name_label = QLabel("🏷️ Nom affiché :")
        self.prompt_name_input = QLineEdit()
        self.prompt_name_input.setPlaceholderText("Ex: Corriger l'orthographe")
        prompt_layout.addRow(name_label, self.prompt_name_input)
        
        # Prompt
        prompt_label = QLabel("📝 Prompt :")
        self.prompt_text_input = QTextEdit()
        self.prompt_text_input.setMinimumHeight(100)
        self.prompt_text_input.setPlaceholderText("Ex: Corrige l'orthographe et la grammaire du texte suivant...")
        prompt_layout.addRow(prompt_label, self.prompt_text_input)
        
        # Statut
        status_label = QLabel("⏳ Message de statut :")
        self.prompt_status_input = QLineEdit()
        self.prompt_status_input.setPlaceholderText("Ex: Correction en cours...")
        prompt_layout.addRow(status_label, self.prompt_status_input)
        
        # Options
        options_label = QLabel("⚙️ Options :")
        self.prompt_insert_directly = QCheckBox("Insérer automatiquement le résultat (sans afficher la fenêtre de réponse)")
        self.prompt_insert_directly.setChecked(False)
        prompt_layout.addRow(options_label, self.prompt_insert_directly)
        
        # Position avec slider
        position_label = QLabel("📍 Position dans le menu :")
        position_widget = QWidget()
        position_layout = QHBoxLayout(position_widget)
        position_layout.setContentsMargins(0, 0, 0, 0)
        
        from PySide6.QtWidgets import QSlider
        self.prompt_position_slider = QSlider(Qt.Horizontal)
        self.prompt_position_slider.setMinimum(1)
        self.prompt_position_slider.setMaximum(20)
        self.prompt_position_slider.setValue(20)
        self.prompt_position_slider.setTickPosition(QSlider.TicksBelow)
        self.prompt_position_slider.setTickInterval(1)
        position_layout.addWidget(self.prompt_position_slider)
        
        self.prompt_position_input = QSpinBox()
        self.prompt_position_input.setMinimum(1)
        self.prompt_position_input.setMaximum(999)
        self.prompt_position_input.setValue(999)
        self.prompt_position_input.setMaximumWidth(80)
        position_layout.addWidget(self.prompt_position_input)
        
        # Connecter slider et spinbox
        self.prompt_position_slider.valueChanged.connect(self.prompt_position_input.setValue)
        self.prompt_position_input.valueChanged.connect(self.prompt_position_slider.setValue)
        
        prompt_layout.addRow(position_label, position_widget)
        
        layout.addWidget(prompt_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        reset_prompt_button = QPushButton("🔄 Réinitialiser")
        reset_prompt_button.setMinimumWidth(140)
        reset_prompt_button.clicked.connect(self.reset_prompt)
        buttons_layout.addWidget(reset_prompt_button)
        
        save_prompt_button = QPushButton("💾 Enregistrer")
        save_prompt_button.setMinimumWidth(140)
        save_prompt_button.setDefault(True)
        save_prompt_button.clicked.connect(self.save_prompt)
        buttons_layout.addWidget(save_prompt_button)
        
        layout.addLayout(buttons_layout)
        
        # Connect prompt selection change
        self.prompt_combo.currentIndexChanged.connect(self.load_prompt)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        # Add the tab
        self.tab_widget.addTab(prompts_tab, "📝 Prompts")
        
        # Load the first prompt
        if self.prompt_combo.count() > 0:
            self.load_prompt(0)
    
    def create_voice_prompts_tab(self):
        """Create the voice prompts settings tab"""
        voice_prompts_tab = QWidget()
        layout = QVBoxLayout(voice_prompts_tab)
        
        # Prompt selection
        prompt_selection_layout = QHBoxLayout()
        selection_label = QLabel("🎤 Sélectionner un prompt vocal :")
        selection_label.setStyleSheet("font-weight: bold;")
        prompt_selection_layout.addWidget(selection_label)
        
        self.voice_prompt_combo = QComboBox()
        self.voice_prompt_combo.setMinimumWidth(300)
        self.populate_voice_prompt_combo()
        prompt_selection_layout.addWidget(self.voice_prompt_combo)
        
        prompt_selection_layout.addStretch()
        
        # Boutons d'ajout et de suppression
        add_prompt_button = QPushButton("➕ Ajouter")
        add_prompt_button.setMinimumWidth(120)
        add_prompt_button.clicked.connect(self.add_voice_prompt)
        prompt_selection_layout.addWidget(add_prompt_button)
        
        delete_prompt_button = QPushButton("🗑️ Supprimer")
        delete_prompt_button.setMinimumWidth(120)
        delete_prompt_button.clicked.connect(self.delete_voice_prompt)
        prompt_selection_layout.addWidget(delete_prompt_button)
        
        layout.addLayout(prompt_selection_layout)
        
        # Prompt editing
        prompt_group = QGroupBox("🎤 Éditer le prompt vocal")
        prompt_layout = QFormLayout(prompt_group)
        
        # Nom affiché
        name_label = QLabel("🏷️ Nom affiché :")
        self.voice_prompt_name_input = QLineEdit()
        self.voice_prompt_name_input.setPlaceholderText("Ex: Décrire et résumer")
        prompt_layout.addRow(name_label, self.voice_prompt_name_input)
        
        # Prompt
        prompt_label = QLabel("📝 Prompt :")
        self.voice_prompt_text_input = QTextEdit()
        self.voice_prompt_text_input.setMinimumHeight(100)
        self.voice_prompt_text_input.setPlaceholderText("Ex: Analyse et décris ce qui suit...")
        prompt_layout.addRow(prompt_label, self.voice_prompt_text_input)
        
        # Statut
        status_label = QLabel("⏳ Message de statut :")
        self.voice_prompt_status_input = QLineEdit()
        self.voice_prompt_status_input.setPlaceholderText("Ex: Traitement en cours...")
        prompt_layout.addRow(status_label, self.voice_prompt_status_input)
        
        # Options
        options_label = QLabel("⚙️ Options :")
        options_widget = QWidget()
        options_layout = QVBoxLayout(options_widget)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(8)
        
        self.voice_prompt_insert_directly = QCheckBox("Insérer automatiquement le résultat (sans afficher la fenêtre de réponse)")
        self.voice_prompt_insert_directly.setChecked(True)
        options_layout.addWidget(self.voice_prompt_insert_directly)
        
        self.voice_prompt_include_selected_text = QCheckBox("Inclure automatiquement le texte sélectionné dans la requête vocale")
        self.voice_prompt_include_selected_text.setChecked(False)
        options_layout.addWidget(self.voice_prompt_include_selected_text)
        
        prompt_layout.addRow(options_label, options_widget)
        
        # Ordre des éléments
        order_label = QLabel("🔄 Ordre des éléments :")
        self.voice_prompt_order_combo = QComboBox()
        self.voice_prompt_order_combo.addItem("📝 Prompt → 🎤 Transcription → 📄 Texte", "prompt_transcription_selected")
        self.voice_prompt_order_combo.addItem("📝 Prompt → 📄 Texte → 🎤 Transcription", "prompt_selected_transcription")
        self.voice_prompt_order_combo.addItem("📄 Texte → 📝 Prompt → 🎤 Transcription", "selected_prompt_transcription")
        self.voice_prompt_order_combo.addItem("🎤 Transcription → 📝 Prompt → 📄 Texte", "transcription_prompt_selected")
        self.voice_prompt_order_combo.addItem("🎤 Transcription → 📄 Texte → 📝 Prompt", "transcription_selected_prompt")
        self.voice_prompt_order_combo.addItem("📄 Texte → 🎤 Transcription → 📝 Prompt", "selected_transcription_prompt")
        prompt_layout.addRow(order_label, self.voice_prompt_order_combo)
        
        # Position avec slider
        position_label = QLabel("📍 Position dans le menu :")
        position_widget = QWidget()
        position_layout = QHBoxLayout(position_widget)
        position_layout.setContentsMargins(0, 0, 0, 0)
        
        from PySide6.QtWidgets import QSlider
        self.voice_prompt_position_slider = QSlider(Qt.Horizontal)
        self.voice_prompt_position_slider.setMinimum(1)
        self.voice_prompt_position_slider.setMaximum(20)
        self.voice_prompt_position_slider.setValue(20)
        self.voice_prompt_position_slider.setTickPosition(QSlider.TicksBelow)
        self.voice_prompt_position_slider.setTickInterval(1)
        position_layout.addWidget(self.voice_prompt_position_slider)
        
        self.voice_prompt_position_input = QSpinBox()
        self.voice_prompt_position_input.setMinimum(1)
        self.voice_prompt_position_input.setMaximum(999)
        self.voice_prompt_position_input.setValue(999)
        self.voice_prompt_position_input.setMaximumWidth(80)
        position_layout.addWidget(self.voice_prompt_position_input)
        
        # Connecter slider et spinbox
        self.voice_prompt_position_slider.valueChanged.connect(self.voice_prompt_position_input.setValue)
        self.voice_prompt_position_input.valueChanged.connect(self.voice_prompt_position_slider.setValue)
        
        prompt_layout.addRow(position_label, position_widget)
        
        layout.addWidget(prompt_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        reset_prompt_button = QPushButton("🔄 Réinitialiser")
        reset_prompt_button.setMinimumWidth(140)
        reset_prompt_button.clicked.connect(self.reset_voice_prompt)
        buttons_layout.addWidget(reset_prompt_button)
        
        save_prompt_button = QPushButton("💾 Enregistrer")
        save_prompt_button.setMinimumWidth(140)
        save_prompt_button.setDefault(True)
        save_prompt_button.clicked.connect(self.save_voice_prompt)
        buttons_layout.addWidget(save_prompt_button)
        
        layout.addLayout(buttons_layout)
        
        # Connect prompt selection change
        self.voice_prompt_combo.currentIndexChanged.connect(self.load_voice_prompt)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        # Add the tab
        self.tab_widget.addTab(voice_prompts_tab, "🎤 Prompts Vocaux")
        
        # Load the first prompt
        if self.voice_prompt_combo.count() > 0:
            self.load_voice_prompt(0)
    
    def create_settings_tab(self):
        """Create the settings tab"""
        from PySide6.QtWidgets import QScrollArea
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Create the content widget
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        
        # Import/Export section
        import_export_group = QGroupBox("📦 Import/Export des Prompts")
        import_export_layout = QVBoxLayout(import_export_group)
        
        # Description
        info_label = QLabel("Exportez et importez tous vos prompts (texte et vocaux) en un seul fichier.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("font-size: 12px; color: #888; margin-bottom: 10px;")
        import_export_layout.addWidget(info_label)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        export_button = QPushButton("📤 Exporter tous les Prompts")
        # Icône retirée
        export_button.clicked.connect(self.export_all_prompts)
        export_button.setMinimumHeight(40)
        buttons_layout.addWidget(export_button)
        
        import_button = QPushButton("📥 Importer tous les Prompts")
        # Icône retirée
        import_button.clicked.connect(self.import_all_prompts)
        import_button.setMinimumHeight(40)
        buttons_layout.addWidget(import_button)
        
        import_export_layout.addLayout(buttons_layout)
        
        # Hotkey section
        hotkey_group = QGroupBox("⌨️ Raccourcis clavier")
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
        microphone_group = QGroupBox("🎤 Microphone pour la reconnaissance vocale")
        microphone_layout = QVBoxLayout(microphone_group)
        
        # Microphone selection
        microphone_label = QLabel("Sélectionnez un microphone:")
        microphone_layout.addWidget(microphone_label)
        
        self.microphone_combo = QComboBox()
        self.populate_microphone_combo()
        self.microphone_combo.currentIndexChanged.connect(self.save_microphone_selection)
        microphone_layout.addWidget(self.microphone_combo)

        # Refresh microphone list button
        refresh_mic_button = QPushButton("🔄 Actualiser la liste")
        refresh_mic_button.clicked.connect(self.populate_microphone_combo)
        microphone_layout.addWidget(refresh_mic_button)
        
        # Theme section
        theme_group = QGroupBox("🎨 Thème de l'application")
        theme_layout = QVBoxLayout(theme_group)
        
        # Theme selection
        theme_label = QLabel("Sélectionnez un thème:")
        theme_layout.addWidget(theme_label)
        
        self.theme_combo = QComboBox()
        # Importer les noms de thèmes depuis ThemeManager
        from src.ui.theme_manager import ThemeManager
        theme_names = ThemeManager.get_theme_names()
        
        # Ajouter les thèmes disponibles
        for theme_key, theme_display in theme_names.items():
            self.theme_combo.addItem(theme_display, theme_key)
        
        # Sélectionner le thème actuel
        current_theme = self.settings.get_theme()
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == current_theme:
                self.theme_combo.setCurrentIndex(i)
                break
                
        theme_layout.addWidget(self.theme_combo)
        
        # Save theme button
        save_theme_button = QPushButton("✨ Appliquer le thème")
        save_theme_button.clicked.connect(self.save_theme_selection)
        theme_layout.addWidget(save_theme_button)
        
        # Add groups to layout
        settings_layout.addWidget(import_export_group)
        settings_layout.addWidget(hotkey_group)
        settings_layout.addWidget(microphone_group)
        settings_layout.addWidget(theme_group)
        settings_layout.addStretch()
        
        # Set the content widget in the scroll area
        scroll_area.setWidget(settings_tab)
        
        # Add tab to tab widget
        self.tab_widget.addTab(scroll_area, "⚙️ Réglages")
    
    def create_about_tab(self):
        """Create the about tab"""
        about_tab = QWidget()
        layout = QVBoxLayout(about_tab)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Description
        description_text = QTextEdit()
        description_text.setReadOnly(True)
        description_text.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif;">
            <h1 style="text-align: center; color: #4CAF50; margin-bottom: 5px;">🚀 SuperMenu</h1>
            <p style="text-align: center; font-size: 14px; color: #aaa; margin-top: 0;">Version 2.1</p>
            
            <p style="font-size: 13px; line-height: 1.6; color: #ddd;">
                SuperMenu est une application puissante conçue pour simplifier et améliorer votre interaction avec les modèles d'IA. 
                Elle offre un accès rapide et personnalisable à une variété de fonctionnalités directement depuis votre bureau.
            </p>
            
            <ul style="line-height: 1.8; font-size: 13px; color: #ddd; margin-top: 20px;">
                <li><strong style="color: #fff;">Prompts personnalisés</strong> : Accès rapide à vos prompts textuels via un menu contextuel</li>
                <li><strong style="color: #fff;">Interaction vocale</strong> : Dictez vos prompts et recevez des réponses instantanées</li>
                <li><strong style="color: #fff;">Analyse d'images</strong> : Capture d'écran et analyse avec l'IA</li>
                <li><strong style="color: #fff;">Multi-endpoints</strong> : Support OpenAI et endpoints personnalisés (Ollama, etc.)</li>
                <li><strong style="color: #fff;">Thèmes personnalisables</strong> : Adaptez l'apparence à vos préférences</li>
                <li><strong style="color: #fff;">Import/Export</strong> : Sauvegardez et partagez vos configurations</li>
                <li><strong style="color: #fff;">Raccourcis clavier</strong> : Configurez vos propres raccourcis pour un accès ultra-rapide</li>
            </ul>
            
            <hr style="margin: 25px 0; border: none; border-top: 1px solid #555;">
            
            <p style="text-align: center; font-size: 13px; color: #ddd; margin-top: 15px;">
                <strong style="color: #ccc;">Développé par LFPoulain avec ❤️</strong>
            </p>
            
            <p style="text-align: center; margin-top: 10px;">
                <a href="https://github.com/lfpoulain/supermenu" style="color: #64B5F6; text-decoration: none; font-size: 12px;">
                    github.com/lfpoulain/supermenu
                </a>
            </p>
        </div>
        """)
        layout.addWidget(description_text)
        
        # Button to open settings folder
        open_settings_folder_button = QPushButton("📂 Ouvrir le dossier des paramètres")
        open_settings_folder_button.clicked.connect(self.open_settings_folder)
        layout.addWidget(open_settings_folder_button)
        
        # Add the tab
        self.tab_widget.addTab(about_tab, "ℹ️ À propos")
    
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
    
    def open_settings_folder(self):
        """Open the folder containing the settings file"""
        try:
            settings_path = os.path.expanduser("~")
            os.startfile(settings_path)
        except Exception as e:
            import logging
            from utils.logger import log
            log(f"Erreur lors de l'ouverture du dossier: {e}", logging.ERROR)
    
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
            
            # Mise à jour de la position
            position = prompt_data.get("position", 999)
            self.prompt_position_input.setValue(position)
            
            # Synchroniser le slider (max 20)
            if position <= 20:
                self.prompt_position_slider.setValue(position)
            else:
                self.prompt_position_slider.setValue(20)
    


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
    
    def change_hotkey(self):
        """Modifier le raccourci clavier"""
        if not self.hotkey_manager:
            # Cette situation ne devrait plus se produire si HotkeyManager est toujours passé
            QMessageBox.warning(self, "Erreur", "HotkeyManager non initialisé.")
            return
        
        # Sauvegarder l'ancien raccourci au cas où l'utilisateur annule
        old_hotkey = self.settings.get_hotkey()
        
        # Désactiver temporairement le raccourci actuel
        self.hotkey_manager.unregister_hotkey()
        
        # Afficher le dialogue d'enregistrement de raccourci
        success = self.hotkey_manager.show_hotkey_recorder()
        
        if success:
            # Mettre à jour l'étiquette avec le nouveau raccourci
            self.hotkey_label.setText(f"Raccourci principal : {self.settings.get_hotkey()}")
            
            # Le raccourci a déjà été enregistré par show_hotkey_recorder()
            # Informer l'utilisateur que c'est fait
            QMessageBox.information(
                self,
                "Raccourci modifié",
                f"Le raccourci a été modifié avec succès en {self.settings.get_hotkey()}.\n\n"
                "Le nouveau raccourci est maintenant actif."
            )
        else:
            # L'utilisateur a annulé, réenregistrer l'ancien raccourci
            self.hotkey_manager.register_hotkey()
    
    def change_voice_hotkey(self):
        """Modifier le raccourci vocal"""
        if not self.voice_hotkey_manager:
            # Cette situation ne devrait plus se produire
            QMessageBox.warning(self, "Erreur", "VoiceHotkeyManager non initialisé.")
            return
        
        # Sauvegarder l'ancien raccourci au cas où l'utilisateur annule
        old_hotkey = self.settings.get_voice_hotkey()
        
        # Désactiver temporairement le raccourci actuel
        self.voice_hotkey_manager.unregister_hotkey()
        
        # Afficher le dialogue d'enregistrement de raccourci
        success = self.voice_hotkey_manager.show_hotkey_recorder()
        
        if success:
            # Mettre à jour l'étiquette avec le nouveau raccourci
            self.voice_hotkey_label.setText(f"Raccourci vocal : {self.settings.get_voice_hotkey()}")
            
            # Le raccourci a déjà été enregistré par show_hotkey_recorder()
            # Informer l'utilisateur que c'est fait
            QMessageBox.information(
                self,
                "Raccourci modifié",
                f"Le raccourci vocal a été modifié avec succès en {self.settings.get_voice_hotkey()}.\n\n"
                "Le nouveau raccourci est maintenant actif."
            )
        else:
            # L'utilisateur a annulé, réenregistrer l'ancien raccourci
            self.voice_hotkey_manager.register_hotkey()
    
    def change_screenshot_hotkey(self):
        """Modifier le raccourci de capture d'écran"""
        if not self.screenshot_hotkey_manager:
            # Cette situation ne devrait plus se produire
            QMessageBox.warning(self, "Erreur", "ScreenshotHotkeyManager non initialisé.")
            return
        
        # Sauvegarder l'ancien raccourci au cas où l'utilisateur annule
        old_hotkey = self.settings.get_screenshot_hotkey()

        # Désactiver temporairement le raccourci actuel
        self.screenshot_hotkey_manager.unregister_hotkey()
        
        # Afficher le dialogue d'enregistrement de raccourci
        success = self.screenshot_hotkey_manager.show_hotkey_recorder()
        
        if success:
            # Mettre à jour l'étiquette avec le nouveau raccourci
            self.screenshot_hotkey_label.setText(f"Raccourci capture d'écran : {self.settings.get_screenshot_hotkey()}")
            
            # Le raccourci a déjà été enregistré par show_hotkey_recorder()
            # Informer l'utilisateur que c'est fait
            QMessageBox.information(
                self,
                "Raccourci modifié",
                f"Le raccourci de capture d'écran a été modifié avec succès en {self.settings.get_screenshot_hotkey()}.\n\n"
                "Le nouveau raccourci est maintenant actif."
            )
        else:
            # L'utilisateur a annulé, réenregistrer l'ancien raccourci
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
            
            # Reload the API configuration
            self.api_key_input.setText(self.settings.get_api_key())
            self.model_combo.setCurrentText(self.settings.get_model())
            
            # Reload custom endpoint configuration
            self.use_custom_endpoint_checkbox.setChecked(self.settings.get_use_custom_endpoint())
            self.custom_endpoint_input.setText(self.settings.get_custom_endpoint())
            self.custom_model_combo.clear()
            current_custom_model = self.settings.get_custom_model()
            if current_custom_model:
                self.custom_model_combo.addItem(current_custom_model)
                self.custom_model_combo.setCurrentText(current_custom_model)
            
            # Update the display based on endpoint type
            self.toggle_custom_endpoint()
            
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
            self.voice_prompt_include_selected_text.setChecked(prompt_data.get("include_selected_text", False))
            
            # Mise à jour de la position
            position = prompt_data.get("position", 999)
            self.voice_prompt_position_input.setValue(position)
            
            # Synchroniser le slider (max 20)
            if position <= 20:
                self.voice_prompt_position_slider.setValue(position)
            else:
                self.voice_prompt_position_slider.setValue(20)
            
            # Charge l'ordre des éléments
            order = prompt_data.get("order", "prompt_transcription_selected")
            for i in range(self.voice_prompt_order_combo.count()):
                if self.voice_prompt_order_combo.itemData(i) == order:
                    self.voice_prompt_order_combo.setCurrentIndex(i)
                    break
    
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
    
    def toggle_custom_endpoint(self):
        """Basculer l'affichage entre OpenAI et endpoint personnalisé"""
        use_custom = self.use_custom_endpoint_checkbox.isChecked()
        
        # Afficher/masquer les sections appropriées
        self.openai_group.setVisible(not use_custom)
        self.custom_group.setVisible(use_custom)
    
    def refresh_custom_models(self):
        """Récupérer la liste des modèles disponibles depuis l'endpoint personnalisé"""
        from src.api.openai_client import OpenAIClient
        
        endpoint = self.custom_endpoint_input.text().strip()
        
        if not endpoint:
            QMessageBox.warning(self, "Endpoint manquant", 
                              "Veuillez d'abord entrer l'URL de l'endpoint personnalisé.")
            return
        
        # Valider l'URL
        is_valid, error_msg = Validators.validate_url(endpoint)
        if not is_valid:
            QMessageBox.warning(self, "URL invalide", error_msg)
            return
        
        # Afficher un message de chargement
        from PySide6.QtWidgets import QProgressDialog
        progress = QProgressDialog("Récupération des modèles disponibles...", "Annuler", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()
        
        # Récupérer les modèles
        api_key = self.api_key_input.text().strip() if self.api_key_input.text().strip() else None
        success, result = OpenAIClient.fetch_available_models(endpoint, api_key)
        
        progress.close()
        
        if success:
            # Sauvegarder le modèle actuellement sélectionné
            current_model = self.custom_model_combo.currentText()
            
            # Mettre à jour le combo box
            self.custom_model_combo.clear()
            self.custom_model_combo.addItems(result)
            
            # Restaurer la sélection si le modèle existe toujours
            if current_model and current_model in result:
                self.custom_model_combo.setCurrentText(current_model)
            elif result:
                self.custom_model_combo.setCurrentIndex(0)
            
            QMessageBox.information(self, "Modèles récupérés", 
                                  f"{len(result)} modèle(s) trouvé(s) sur le serveur.")
        else:
            QMessageBox.warning(self, "Erreur", 
                              f"Impossible de récupérer les modèles:\n\n{result}")
    
    def save_api_key(self):
        """Save the API key and configuration"""
        api_key = self.api_key_input.text().strip()
        model = self.model_combo.currentText()
        use_custom = self.use_custom_endpoint_checkbox.isChecked()
        custom_endpoint = self.custom_endpoint_input.text().strip()
        custom_model = self.custom_model_combo.currentText().strip()
        
        # Validation
        if not use_custom and api_key:
            is_valid, error_msg = Validators.validate_api_key(api_key)
            if not is_valid:
                QMessageBox.warning(self, "Clé API invalide", error_msg)
                return
        
        if use_custom:
            if custom_endpoint:
                is_valid, error_msg = Validators.validate_url(custom_endpoint)
                if not is_valid:
                    QMessageBox.warning(self, "URL invalide", error_msg)
                    return
            
            if custom_model:
                is_valid, error_msg = Validators.validate_model_name(custom_model)
                if not is_valid:
                    QMessageBox.warning(self, "Nom de modèle invalide", error_msg)
                    return
        
        # Save settings
        self.settings.set_api_key(api_key)
        self.settings.set_model(model)
        self.settings.set_use_custom_endpoint(use_custom)
        self.settings.set_custom_endpoint(custom_endpoint)
        self.settings.set_custom_model(custom_model)
        
        # Mettre à jour la configuration du client API sans redémarrage
        if self.context_menu_manager:
            self.context_menu_manager.update_client_config()
        
        QMessageBox.information(self, "Configuration enregistrée", 
                              "La configuration a été enregistrée avec succès.\n\nLes modifications sont actives immédiatement.")
