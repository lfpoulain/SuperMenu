#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tempfile
import subprocess
import ctypes
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QTabWidget,
    QComboBox, QTextEdit, QGroupBox, QFormLayout,
    QMessageBox, QSystemTrayIcon, QMenu, QCheckBox, QApplication,
    QDialog, QStyle, QInputDialog, QSpinBox, QFileDialog, QListWidget, QListWidgetItem, QAbstractItemView, QSplitter
)
from PySide6.QtCore import Qt, QSize, Signal, QTimer, QThread
from PySide6.QtGui import QIcon, QAction, QKeySequence

from src.config.settings import (
    Settings,
    AVAILABLE_MODELS,
    get_reasoning_efforts_for_model,
    normalize_reasoning_effort,
)
from src.utils.hotkey_manager import HotkeyManager
from src.ui.screenshot_dialog import ScreenshotDialog
from src.utils.validators import Validators
from src.utils import updater as app_updater
from src.utils.loading_indicator import SimpleLoadingIndicator
import uuid


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class _UpdateCheckWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, owner: str, repo: str, tag: str, app_id_guid: str):
        super().__init__()
        self.owner = owner
        self.repo = repo
        self.tag = tag
        self.app_id_guid = app_id_guid

    def run(self):
        try:
            release = app_updater.get_github_release_by_tag(self.owner, self.repo, self.tag)
            latest_version = app_updater.extract_version_from_release(release)
            asset_url = app_updater.find_asset_download_url(release, "SuperMenu_Setup.exe")
            installed_version = app_updater.get_installed_app_version(self.app_id_guid)

            self.finished_ok.emit(
                {
                    "installed_version": installed_version,
                    "latest_version": latest_version,
                    "asset_url": asset_url,
                    "release_url": release.get("html_url"),
                }
            )
        except Exception as e:
            self.failed.emit(str(e))


class _UpdateDownloadWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, dest_path: str):
        super().__init__()
        self.url = url
        self.dest_path = dest_path

    def run(self):
        try:
            app_updater.download_to_file(self.url, self.dest_path)
            self.finished_ok.emit(self.dest_path)
        except Exception as e:
            self.failed.emit(str(e))

class MainWindow(QMainWindow):
    """Main application window for settings and configuration"""
    
    def __init__(self, settings, context_menu_manager=None, hotkey_manager=None, voice_hotkey_manager=None, screenshot_hotkey_manager=None, custom_hotkey_manager=None):
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
        self.custom_hotkey_manager = custom_hotkey_manager
        
        self._update_check_worker = None
        self._update_download_worker = None
        self._update_loading = None

        # Set window properties
        self.setWindowTitle("SuperMenu - Configuration")
        self.setMinimumSize(900, 800)
        self.resize(1000, 820)
        
        # Create the central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Create the main layout
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create the tab widget
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_prompts_tab()
        self.create_voice_prompts_tab()
        self.create_settings_tab()
        self.create_about_tab()
        
        # Create bottom buttons
        self.create_bottom_buttons()
    
    def create_models_tab(self):
        """Create the models configuration tab"""
        return
    
    def create_prompts_tab(self):
        """Create the prompts settings tab"""
        prompts_tab = QWidget()
        layout = QVBoxLayout(prompts_tab)

        self.prompt_combo = QComboBox()
        self.populate_prompt_combo()
        self.prompt_combo.hide()

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(0)
        splitter.setChildrenCollapsible(False)

        left_panel = QWidget()
        left_panel.setFixedWidth(300)
        left_layout = QVBoxLayout(left_panel)

        self.prompt_search_input = QLineEdit()
        self.prompt_search_input.setPlaceholderText("Rechercher...")
        self.prompt_search_input.textChanged.connect(self._apply_prompt_filter)
        left_layout.addWidget(self.prompt_search_input)

        self.prompt_order_list = QListWidget()
        self.prompt_order_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.prompt_order_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.prompt_order_list.setDefaultDropAction(Qt.MoveAction)
        self.prompt_order_list.setDropIndicatorShown(True)
        self.prompt_order_list.model().rowsMoved.connect(self.on_prompt_order_changed)
        self.prompt_order_list.currentItemChanged.connect(self._on_prompt_list_current_changed)
        self.prompt_order_list.setSpacing(6)
        self.prompt_order_list.setStyleSheet(
            "QListWidget { border-radius: 6px; border: 1px solid rgba(52, 152, 219, 0.3); }"
            "QListWidget:focus { border: 2px solid #3498db; }"
            "QListWidget::item { padding: 8px; border-left: 3px solid transparent; }"
            "QListWidget::item:hover { border-left: 3px solid #64B5F6; background-color: rgba(100, 181, 246, 0.10); }"
            "QListWidget::item:selected { border-left: 3px solid #64B5F6; background-color: rgba(100, 181, 246, 0.18); }"
            "QListWidget::item:selected:hover { border-left: 3px solid #64B5F6; background-color: rgba(100, 181, 246, 0.18); }"
        )
        left_layout.addWidget(self.prompt_order_list)

        left_buttons = QHBoxLayout()
        add_prompt_button = QPushButton("➕ Ajouter")
        add_prompt_button.clicked.connect(self.add_prompt)
        left_buttons.addWidget(add_prompt_button)

        delete_prompt_button = QPushButton("🗑️ Supprimer")
        delete_prompt_button.clicked.connect(self.delete_prompt)
        left_buttons.addWidget(delete_prompt_button)

        left_layout.addLayout(left_buttons)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
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
        
        right_layout.addWidget(prompt_group)
        
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
        
        right_layout.addLayout(buttons_layout)
        
        # Connect prompt selection change
        self.prompt_combo.currentIndexChanged.connect(self.load_prompt)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)
        
        # Add the tab
        self.tab_widget.addTab(prompts_tab, "📝 Prompts")
        
        # Load the first prompt
        if self.prompt_combo.count() > 0:
            self.load_prompt(0)

        self.populate_prompt_order_list()
    
    def create_voice_prompts_tab(self):
        """Create the voice prompts settings tab"""
        voice_prompts_tab = QWidget()
        layout = QVBoxLayout(voice_prompts_tab)

        self.voice_prompt_combo = QComboBox()
        self.populate_voice_prompt_combo()
        self.voice_prompt_combo.hide()

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(0)
        splitter.setChildrenCollapsible(False)

        left_panel = QWidget()
        left_panel.setFixedWidth(300)
        left_layout = QVBoxLayout(left_panel)

        self.voice_prompt_search_input = QLineEdit()
        self.voice_prompt_search_input.setPlaceholderText("Rechercher...")
        self.voice_prompt_search_input.textChanged.connect(self._apply_voice_prompt_filter)
        left_layout.addWidget(self.voice_prompt_search_input)

        self.voice_prompt_order_list = QListWidget()
        self.voice_prompt_order_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.voice_prompt_order_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.voice_prompt_order_list.setDefaultDropAction(Qt.MoveAction)
        self.voice_prompt_order_list.setDropIndicatorShown(True)
        self.voice_prompt_order_list.model().rowsMoved.connect(self.on_voice_prompt_order_changed)
        self.voice_prompt_order_list.currentItemChanged.connect(self._on_voice_prompt_list_current_changed)
        self.voice_prompt_order_list.setSpacing(6)
        self.voice_prompt_order_list.setStyleSheet(
            "QListWidget { border-radius: 6px; border: 1px solid rgba(52, 152, 219, 0.3); }"
            "QListWidget:focus { border: 2px solid #3498db; }"
            "QListWidget::item { padding: 8px; border-left: 3px solid transparent; }"
            "QListWidget::item:hover { border-left: 3px solid #64B5F6; background-color: rgba(100, 181, 246, 0.10); }"
            "QListWidget::item:selected { border-left: 3px solid #64B5F6; background-color: rgba(100, 181, 246, 0.18); }"
            "QListWidget::item:selected:hover { border-left: 3px solid #64B5F6; background-color: rgba(100, 181, 246, 0.18); }"
        )
        left_layout.addWidget(self.voice_prompt_order_list)

        left_buttons = QHBoxLayout()
        add_prompt_button = QPushButton("➕ Ajouter")
        add_prompt_button.clicked.connect(self.add_voice_prompt)
        left_buttons.addWidget(add_prompt_button)

        delete_prompt_button = QPushButton("🗑️ Supprimer")
        delete_prompt_button.clicked.connect(self.delete_voice_prompt)
        left_buttons.addWidget(delete_prompt_button)

        left_layout.addLayout(left_buttons)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
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

        right_layout.addWidget(prompt_group)
        
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
        
        right_layout.addLayout(buttons_layout)
        
        # Connect prompt selection change
        self.voice_prompt_combo.currentIndexChanged.connect(self.load_voice_prompt)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)
        
        # Add the tab
        self.tab_widget.addTab(voice_prompts_tab, "🎤 Prompts Vocaux")
        
        # Load the first prompt
        if self.voice_prompt_combo.count() > 0:
            self.load_voice_prompt(0)

        self.populate_voice_prompt_order_list()
    
    def create_settings_tab(self):
        """Create the settings tab"""
        from PySide6.QtWidgets import QScrollArea
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        try:
            scroll_area.setFrameShape(QScrollArea.NoFrame)
        except Exception:
            pass
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        # Create the content widget
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)

        models_widget = QWidget()
        models_layout = QVBoxLayout(models_widget)

        self.use_custom_endpoint_checkbox = QCheckBox("Activer un endpoint personnalisé (ex: Ollama / LM Studio)")
        self.use_custom_endpoint_checkbox.setChecked(self.settings.get_use_custom_endpoint())
        self.use_custom_endpoint_checkbox.toggled.connect(self.toggle_custom_endpoint)
        models_layout.addWidget(self.use_custom_endpoint_checkbox)

        self.openai_group = QGroupBox("OpenAI")
        openai_layout = QVBoxLayout(self.openai_group)

        api_key_label = QLabel("Clé API:")
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setText(self.settings.get_api_key())

        model_label = QLabel("Modèle:")
        self.model_combo = QComboBox()
        self.model_combo.addItems(AVAILABLE_MODELS)
        self.model_combo.setCurrentText(self.settings.get_model())

        reasoning_label = QLabel("Raisonnement:")
        self.reasoning_effort_combo = QComboBox()
        self.reasoning_effort_combo.setToolTip("Disponible pour les modèles GPT-5.4, GPT-5.2 et GPT-5-Mini")

        openai_layout.addWidget(api_key_label)
        openai_layout.addWidget(self.api_key_input)
        openai_layout.addWidget(model_label)
        openai_layout.addWidget(self.model_combo)
        openai_layout.addWidget(reasoning_label)
        openai_layout.addWidget(self.reasoning_effort_combo)

        self.custom_group = QGroupBox("Endpoint personnalisé (Ollama, etc.)")
        custom_layout = QVBoxLayout(self.custom_group)

        custom_endpoint_label = QLabel("URL de l'endpoint (ex: http://localhost:11434):")
        self.custom_endpoint_input = QLineEdit()
        self.custom_endpoint_input.setText(self.settings.get_custom_endpoint())
        self.custom_endpoint_input.setPlaceholderText("http://localhost:11434")

        custom_endpoint_type_label = QLabel("Type d'endpoint :")
        self.custom_endpoint_type_combo = QComboBox()
        self.custom_endpoint_type_combo.addItem("Ollama", "ollama")
        self.custom_endpoint_type_combo.addItem("LM Studio", "lmstudio")
        current_custom_endpoint_type = self.settings.get_custom_endpoint_type()
        for i in range(self.custom_endpoint_type_combo.count()):
            if self.custom_endpoint_type_combo.itemData(i) == current_custom_endpoint_type:
                self.custom_endpoint_type_combo.setCurrentIndex(i)
                break

        custom_model_label = QLabel("Modèle:")
        custom_model_layout = QHBoxLayout()
        self.custom_model_combo = QComboBox()
        self.custom_model_combo.setEditable(True)
        self.custom_model_combo.setPlaceholderText("Sélectionnez ou entrez un modèle")
        custom_model_layout.addWidget(self.custom_model_combo)

        refresh_models_button = QPushButton("Actualiser")
        refresh_models_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_models_button.clicked.connect(self.refresh_custom_models)
        custom_model_layout.addWidget(refresh_models_button)

        custom_layout.addWidget(custom_endpoint_label)
        custom_layout.addWidget(self.custom_endpoint_input)
        custom_layout.addWidget(custom_endpoint_type_label)
        custom_layout.addWidget(self.custom_endpoint_type_combo)
        custom_layout.addWidget(custom_model_label)
        custom_layout.addLayout(custom_model_layout)

        current_custom_model = self.settings.get_custom_model()
        if current_custom_model:
            self.custom_model_combo.addItem(current_custom_model)
            self.custom_model_combo.setCurrentText(current_custom_model)

        note_label = QLabel("Note: La transcription audio restera sur OpenAI (4o-transcribe)")
        note_label.setStyleSheet("color: #666; font-style: italic;")
        custom_layout.addWidget(note_label)

        models_layout.addWidget(self.openai_group)
        models_layout.addWidget(self.custom_group)

        save_api_key_button = QPushButton("Enregistrer la configuration")
        save_api_key_button.clicked.connect(self.save_api_key)
        models_layout.addWidget(save_api_key_button)

        self.toggle_custom_endpoint()
        self.model_combo.currentTextChanged.connect(self.update_reasoning_effort_ui)
        self.update_reasoning_effort_ui()
        
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

        # Custom mode hotkey info
        self.custom_hotkey_label = QLabel(f"Raccourci mode personnalisé : {self.settings.get_custom_hotkey()}")
        hotkey_layout.addWidget(self.custom_hotkey_label)

        # Change custom mode hotkey button
        change_custom_hotkey_button = QPushButton("Modifier le raccourci mode personnalisé")
        change_custom_hotkey_button.clicked.connect(self.change_custom_hotkey)
        hotkey_layout.addWidget(change_custom_hotkey_button)
        
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
        
        self.microphone_combo = NoWheelComboBox()
        self.populate_microphone_combo()
        self.microphone_combo.currentIndexChanged.connect(self.on_microphone_selection_changed)
        microphone_row = QHBoxLayout()
        microphone_row.setContentsMargins(0, 0, 0, 0)
        microphone_row.setSpacing(4)
        microphone_row.addWidget(self.microphone_combo)
        microphone_layout.addLayout(microphone_row)

        self.save_microphone_button = QPushButton("💾 Enregistrer le microphone")
        self.save_microphone_button.clicked.connect(self.save_microphone_selection)
        self.save_microphone_button.setEnabled(False)
        microphone_layout.addWidget(self.save_microphone_button)

        screenshot_capture_mode_label = QLabel("Mode de capture d'écran :")
        microphone_layout.addWidget(screenshot_capture_mode_label)

        self.screenshot_capture_mode_combo = NoWheelComboBox()
        self.screenshot_capture_mode_combo.addItem("Plein écran", "fullscreen")
        self.screenshot_capture_mode_combo.addItem("Sélection de zone", "region")
        self.screenshot_capture_mode_combo.addItem("Demander à chaque capture", "ask")

        current_mode = self.settings.get_screenshot_capture_mode()
        for i in range(self.screenshot_capture_mode_combo.count()):
            if self.screenshot_capture_mode_combo.itemData(i) == current_mode:
                self.screenshot_capture_mode_combo.setCurrentIndex(i)
                break

        self.screenshot_capture_mode_combo.currentIndexChanged.connect(self.on_screenshot_capture_mode_changed)
        microphone_layout.addWidget(self.screenshot_capture_mode_combo)

        self.save_screenshot_capture_mode_button = QPushButton("💾 Enregistrer le mode de capture")
        self.save_screenshot_capture_mode_button.clicked.connect(self.save_screenshot_capture_mode)
        microphone_layout.addWidget(self.save_screenshot_capture_mode_button)

        self._update_screenshot_capture_mode_ui_state()

        settings_shortcuts_audio_widget = QWidget()
        settings_shortcuts_audio_layout = QHBoxLayout(settings_shortcuts_audio_widget)
        settings_shortcuts_audio_layout.addWidget(hotkey_group)
        settings_shortcuts_audio_layout.addWidget(microphone_group)
        settings_shortcuts_audio_layout.setStretch(0, 1)
        settings_shortcuts_audio_layout.setStretch(1, 1)

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
        settings_layout.addWidget(models_widget)
        settings_layout.addWidget(settings_shortcuts_audio_widget)
        settings_layout.addWidget(import_export_group)
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

        installed_version = self._get_installed_version_display()
        description_text.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif;">
            <h1 style="text-align: center; color: #4CAF50; margin-bottom: 5px;">🚀 SuperMenu</h1>
            <p style="text-align: center; font-size: 14px; color: #aaa; margin-top: 0;">Version """ + installed_version + """</p>
            <p style="text-align: center; font-size: 12px; color: #aaa; margin-top: 0;">Canal : nightly (GitHub Releases)</p>
            
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

            <p style="font-size: 12px; line-height: 1.6; color: #bbb;">
                Configuration : <strong style="color: #fff;">%USERPROFILE%\\SuperMenu.ini</strong><br>
                Logs : <strong style="color: #fff;">%LOCALAPPDATA%\\SuperMenu\\logs\\supermenu.log</strong>
            </p>
            
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

        open_logs_folder_button = QPushButton("📄 Ouvrir le dossier des logs")
        open_logs_folder_button.clicked.connect(self.open_logs_folder)
        layout.addWidget(open_logs_folder_button)

        open_releases_button = QPushButton("Ouvrir la page des releases")
        open_releases_button.clicked.connect(self.open_releases_page)
        layout.addWidget(open_releases_button)

        check_updates_button = QPushButton("Vérifier les mises à jour")
        check_updates_button.clicked.connect(self.check_for_updates)
        layout.addWidget(check_updates_button)
        
        # Add the tab
        self.tab_widget.addTab(about_tab, "ℹ️ À propos")

    def _get_installed_version_display(self):
        version = app_updater.get_installed_app_version("C8F9E2A0-1F3A-4E5D-B6A9-D5C8E4E0F2A1")
        if version:
            return version
        return "dev"

    def check_for_updates(self):
        if self._update_check_worker and self._update_check_worker.isRunning():
            return

        self._update_loading = SimpleLoadingIndicator("Vérification des mises à jour...")
        self._update_loading.show()

        self._update_check_worker = _UpdateCheckWorker(
            owner="lfpoulain",
            repo="supermenu",
            tag="nightly",
            app_id_guid="C8F9E2A0-1F3A-4E5D-B6A9-D5C8E4E0F2A1",
        )
        self._update_check_worker.finished_ok.connect(self._on_update_check_ok)
        self._update_check_worker.failed.connect(self._on_update_check_failed)
        self._update_check_worker.start()

    def _on_update_check_ok(self, data: dict):
        if self._update_loading:
            self._update_loading.close()
            self._update_loading = None

        installed_version = data.get("installed_version")
        latest_version = data.get("latest_version")
        asset_url = data.get("asset_url")

        if not latest_version:
            QMessageBox.warning(self, "Mise à jour", "Impossible de déterminer la version de la release.")
            return

        if not asset_url:
            QMessageBox.warning(self, "Mise à jour", "Aucun installateur n'a été trouvé sur la release (SuperMenu_Setup.exe).")
            return

        if not app_updater.is_newer_version(installed_version, latest_version):
            QMessageBox.information(
                self,
                "Mise à jour",
                f"Vous êtes déjà à jour.\n\nVersion installée : {installed_version or 'inconnue'}\nDernière version : {latest_version}",
            )
            return

        reply = QMessageBox.question(
            self,
            "Mise à jour disponible",
            f"Une mise à jour est disponible.\n\nVersion installée : {installed_version or 'inconnue'}\nNouvelle version : {latest_version}\n\nTélécharger et installer maintenant ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        dest_path = os.path.join(tempfile.gettempdir(), f"SuperMenu_Setup_{latest_version}.exe")
        self._start_download_installer(asset_url, dest_path)

    def _on_update_check_failed(self, error: str):
        if self._update_loading:
            self._update_loading.close()
            self._update_loading = None
        QMessageBox.warning(self, "Mise à jour", f"Erreur lors de la vérification des mises à jour :\n\n{error}")

    def _start_download_installer(self, url: str, dest_path: str):
        if self._update_download_worker and self._update_download_worker.isRunning():
            return

        self._update_loading = SimpleLoadingIndicator("Téléchargement de l'installateur...")
        self._update_loading.show()

        self._update_download_worker = _UpdateDownloadWorker(url, dest_path)
        self._update_download_worker.finished_ok.connect(self._on_download_ok)
        self._update_download_worker.failed.connect(self._on_download_failed)
        self._update_download_worker.start()

    def _on_download_ok(self, installer_path: str):
        if self._update_loading:
            self._update_loading.close()
            self._update_loading = None

        reply = QMessageBox.question(
            self,
            "Mise à jour prête",
            "L'installateur a été téléchargé.\n\nLancer l'installation maintenant ?\n\nL'application va se fermer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        self._launch_installer_and_quit(installer_path)

    def _on_download_failed(self, error: str):
        if self._update_loading:
            self._update_loading.close()
            self._update_loading = None
        QMessageBox.warning(self, "Mise à jour", f"Erreur lors du téléchargement :\n\n{error}")

    def _launch_installer_and_quit(self, installer_path: str):
        try:
            params = ""
            cwd = os.path.dirname(installer_path)
            rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", installer_path, params, cwd, 1)
            if rc <= 32:
                subprocess.Popen([installer_path], cwd=cwd)
        except Exception:
            try:
                os.startfile(installer_path)
            except Exception as e:
                QMessageBox.warning(self, "Mise à jour", f"Impossible de lancer l'installateur :\n\n{e}")
                return

        QApplication.quit()

    def open_settings_folder(self):
        try:
            settings_path = os.path.expanduser("~")
            os.startfile(settings_path)
        except Exception as e:
            import logging
            from src.utils.logger import log
            log(f"Erreur lors de l'ouverture du dossier: {e}", logging.ERROR)

    def open_logs_folder(self):
        try:
            logs_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "SuperMenu", "logs")
            if logs_dir and os.path.exists(logs_dir):
                os.startfile(logs_dir)
                return
            QMessageBox.information(self, "Logs", "Le dossier des logs n'existe pas encore (il sera créé au premier log).")
        except Exception as e:
            QMessageBox.warning(self, "Logs", f"Impossible d'ouvrir le dossier des logs :\n\n{e}")

    def open_releases_page(self):
        try:
            import webbrowser

            webbrowser.open("https://github.com/lfpoulain/supermenu/releases")
        except Exception as e:
            QMessageBox.warning(self, "Releases", f"Impossible d'ouvrir la page des releases :\n\n{e}")
    
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

        self._update_microphone_ui_state()

    def on_microphone_selection_changed(self, *args):
        self._update_microphone_ui_state()

    def _update_microphone_ui_state(self):
        try:
            selected_index = self.microphone_combo.currentIndex()
            current_ui_value = self.microphone_combo.itemData(selected_index)
            saved_value = self.settings.get_microphone_index()

            if saved_value is None:
                saved_value = -1

            is_saved = current_ui_value == saved_value
            self.save_microphone_button.setEnabled(not is_saved)
        except Exception:
            pass
    
    def save_microphone_selection(self):
        """Save the selected microphone to settings"""
        selected_index = self.microphone_combo.currentIndex()
        mic_index = self.microphone_combo.itemData(selected_index)

        # Update settings
        self.settings.set_microphone_index(mic_index)

        default_text = "💾 Enregistrer le microphone"
        self.save_microphone_button.setText("✅ Enregistré")
        QTimer.singleShot(900, lambda: self.save_microphone_button.setText(default_text))

        self._update_microphone_ui_state()

    def on_screenshot_capture_mode_changed(self, *args):
        self._update_screenshot_capture_mode_ui_state()

    def _update_screenshot_capture_mode_ui_state(self):
        try:
            selected_index = self.screenshot_capture_mode_combo.currentIndex()
            current_ui_value = self.screenshot_capture_mode_combo.itemData(selected_index)
            saved_value = self.settings.get_screenshot_capture_mode()

            is_saved = current_ui_value == saved_value
            self.save_screenshot_capture_mode_button.setEnabled(not is_saved)
        except Exception:
            pass

    def save_screenshot_capture_mode(self):
        try:
            selected_index = self.screenshot_capture_mode_combo.currentIndex()
            mode = self.screenshot_capture_mode_combo.itemData(selected_index)
            self.settings.set_screenshot_capture_mode(mode)
        except Exception:
            pass

        default_text = "💾 Enregistrer le mode de capture"
        self.save_screenshot_capture_mode_button.setText("✅ Enregistré")
        QTimer.singleShot(900, lambda: self.save_screenshot_capture_mode_button.setText(default_text))

        self._update_screenshot_capture_mode_ui_state()
    
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

    def change_custom_hotkey(self):
        """Modifier le raccourci du mode personnalisé"""
        if not self.custom_hotkey_manager:
            QMessageBox.warning(self, "Erreur", "CustomHotkeyManager non initialisé.")
            return

        old_hotkey = self.settings.get_custom_hotkey()
        self.custom_hotkey_manager.unregister_hotkey()

        success = self.custom_hotkey_manager.show_hotkey_recorder()

        if success:
            self.custom_hotkey_label.setText(f"Raccourci mode personnalisé : {self.settings.get_custom_hotkey()}")
            QMessageBox.information(
                self,
                "Raccourci modifié",
                f"Le raccourci du mode personnalisé a été modifié avec succès en {self.settings.get_custom_hotkey()}.\n\n"
                "Le nouveau raccourci est maintenant actif."
            )
        else:
            self.custom_hotkey_manager._set_configured_hotkey(old_hotkey)
            self.custom_hotkey_manager.register_hotkey()
    
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
        name = self.prompt_name_input.text().strip()
        prompt = self.prompt_text_input.toPlainText()
        status = self.prompt_status_input.text()
        insert_directly = self.prompt_insert_directly.isChecked()

        position = 999
        try:
            position = self.settings.get_prompt(prompt_id).get("position", 999)
        except Exception:
            position = 999
        
        # Vérifier que les champs ne sont pas vides
        if not name or not prompt or not status:
            QMessageBox.warning(self, "Champs incomplets", 
                              "Veuillez remplir tous les champs (nom, prompt et statut).")
            return
        
        # Mettre à jour le prompt
        self.settings.update_prompt(prompt_id, name, prompt, status, insert_directly, position)
        
        # Mettre à jour le nom dans le combo
        self.prompt_combo.setItemText(self.prompt_combo.currentIndex(), name)

        self.populate_prompt_order_list()
        
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
                
                # Update the combo box
                self.prompt_combo.setItemText(index, default_prompt["name"])

                self.populate_prompt_order_list()
                
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
            self.update_reasoning_effort_ui()
            
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
            self.custom_hotkey_label.setText(f"Raccourci mode personnalisé : {self.settings.get_custom_hotkey()}")
            self.screenshot_hotkey_label.setText(f"Raccourci capture d'écran : {self.settings.get_screenshot_hotkey()}")

            if self.custom_hotkey_manager:
                self.custom_hotkey_manager.register_hotkey()
            
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
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False

        # Create the tray icon
        self.tray_icon = QSystemTrayIcon(self)
        
        # Set the icon
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        icon_path = os.path.join(base_dir, "resources", "icons", "icon.png")
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

        update_action = QAction("Vérifier les mises à jour", self)
        update_action.triggered.connect(self.check_for_updates)
        tray_menu.addAction(update_action)
        
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
        return True
    
    def tray_icon_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_main_window()

    def show_main_window(self):
        """Show and focus the main window (used at startup and tray activation)."""
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
    
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
        # Demander le nom affiché du nouveau prompt
        prompt_name, ok = QInputDialog.getText(
            self,
            "Nouveau prompt",
            "Entrez le nom du nouveau prompt :"
        )
        
        if not ok or not prompt_name:
            return
        
        prompt_name = prompt_name.strip()
        prompt_id = Validators.normalize_prompt_id(prompt_name)

        if not prompt_id:
            QMessageBox.warning(
                self,
                "Nom invalide",
                "Le nom du prompt ne peut pas être vide."
            )
            return
        
        # Créer un nouveau prompt avec des valeurs par défaut
        new_prompt_id = self.settings.add_prompt(
            prompt_id,
            prompt_name,
            "",
            "Traitement en cours...",
            False,
            999
        )
        
        # Mettre à jour la liste des prompts
        self.populate_prompt_combo()

        self.populate_prompt_order_list()
        
        # Sélectionner le nouveau prompt
        index = self.prompt_combo.findData(new_prompt_id)
        if index >= 0:
            self.prompt_combo.setCurrentIndex(index)
            self.load_prompt(index)
        
        # Afficher un message de confirmation
        QMessageBox.information(
            self,
            "Prompt ajouté",
            f"Le nouveau prompt '{prompt_name}' a été ajouté avec succès. Vous pouvez maintenant le personnaliser."
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

            self.populate_prompt_order_list()
            
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

    def populate_prompt_combo(self):
        """Populate the prompt combo box with available prompts"""
        current_prompt_id = None
        try:
            current_prompt_id = self.prompt_combo.currentData()
        except Exception:
            current_prompt_id = None

        self.prompt_combo.clear()

        prompts = self.settings.get_prompts()

        sorted_prompts = sorted(prompts.items(), key=lambda x: x[1].get("position", 999))
        for prompt_id, prompt_data in sorted_prompts:
            self.prompt_combo.addItem(prompt_data["name"], prompt_id)

        if current_prompt_id is not None:
            index = self.prompt_combo.findData(current_prompt_id)
            if index >= 0:
                self.prompt_combo.setCurrentIndex(index)

    def populate_prompt_order_list(self):
        try:
            current_prompt_id = None
            try:
                current_prompt_id = self.prompt_combo.currentData()
            except Exception:
                current_prompt_id = None

            query = ""
            try:
                query = (self.prompt_search_input.text() or "").strip().lower()
            except Exception:
                query = ""
            is_filtered = bool(query)

            self._is_updating_prompt_order_list = True
            self.prompt_order_list.clear()

            if is_filtered:
                self.prompt_order_list.setDragDropMode(QAbstractItemView.NoDragDrop)
                self.prompt_order_list.setDropIndicatorShown(False)
            else:
                self.prompt_order_list.setDragDropMode(QAbstractItemView.InternalMove)
                self.prompt_order_list.setDropIndicatorShown(True)

            prompts = self.settings.get_prompts()
            sorted_prompts = sorted(prompts.items(), key=lambda x: x[1].get("position", 999))
            for prompt_id, prompt_data in sorted_prompts:
                name = prompt_data.get("name", str(prompt_id))
                if is_filtered and query not in (name or "").lower():
                    continue
                item = QListWidgetItem(name)
                item.setSizeHint(QSize(0, 44))
                item.setData(Qt.UserRole, prompt_id)
                self.prompt_order_list.addItem(item)

            if current_prompt_id is not None:
                for row in range(self.prompt_order_list.count()):
                    if self.prompt_order_list.item(row).data(Qt.UserRole) == current_prompt_id:
                        self.prompt_order_list.setCurrentRow(row)
                        break
        finally:
            self._is_updating_prompt_order_list = False

    def _apply_prompt_filter(self, *args):
        self.populate_prompt_order_list()

    def _on_prompt_list_current_changed(self, current, previous):
        if getattr(self, "_is_updating_prompt_order_list", False):
            return
        if current is None:
            return
        prompt_id = current.data(Qt.UserRole)
        if prompt_id is None:
            return
        index = self.prompt_combo.findData(prompt_id)
        if index >= 0 and index != self.prompt_combo.currentIndex():
            self.prompt_combo.setCurrentIndex(index)

    def on_prompt_order_changed(self, *args):
        if getattr(self, "_is_updating_prompt_order_list", False):
            return

        prompts = self.settings.get_prompts()
        for row in range(self.prompt_order_list.count()):
            item = self.prompt_order_list.item(row)
            prompt_id = item.data(Qt.UserRole)
            if prompt_id not in prompts:
                continue
            prompt_data = prompts[prompt_id]
            new_position = (row + 1) * 10
            if prompt_data.get("position", 999) == new_position:
                continue
            self.settings.update_prompt(
                prompt_id,
                prompt_data.get("name", str(prompt_id)),
                prompt_data.get("prompt", ""),
                prompt_data.get("status", ""),
                prompt_data.get("insert_directly", False),
                new_position,
            )

        self.populate_prompt_combo()
        self.populate_prompt_order_list()

    def populate_voice_prompt_combo(self):
        """Populate the voice prompt combo box with available voice prompts"""
        current_prompt_id = None
        try:
            current_prompt_id = self.voice_prompt_combo.currentData()
        except Exception:
            current_prompt_id = None

        self.voice_prompt_combo.clear()

        prompts = self.settings.get_voice_prompts()

        sorted_prompts = sorted(prompts.items(), key=lambda x: x[1].get("position", 999))
        for prompt_id, prompt_data in sorted_prompts:
            self.voice_prompt_combo.addItem(prompt_data["name"], prompt_id)

        if current_prompt_id is not None:
            index = self.voice_prompt_combo.findData(current_prompt_id)
            if index >= 0:
                self.voice_prompt_combo.setCurrentIndex(index)

    def populate_voice_prompt_order_list(self):
        try:
            current_prompt_id = None
            try:
                current_prompt_id = self.voice_prompt_combo.currentData()
            except Exception:
                current_prompt_id = None

            query = ""
            try:
                query = (self.voice_prompt_search_input.text() or "").strip().lower()
            except Exception:
                query = ""
            is_filtered = bool(query)

            self._is_updating_voice_prompt_order_list = True
            self.voice_prompt_order_list.clear()

            if is_filtered:
                self.voice_prompt_order_list.setDragDropMode(QAbstractItemView.NoDragDrop)
                self.voice_prompt_order_list.setDropIndicatorShown(False)
            else:
                self.voice_prompt_order_list.setDragDropMode(QAbstractItemView.InternalMove)
                self.voice_prompt_order_list.setDropIndicatorShown(True)

            prompts = self.settings.get_voice_prompts()
            sorted_prompts = sorted(prompts.items(), key=lambda x: x[1].get("position", 999))
            for prompt_id, prompt_data in sorted_prompts:
                name = prompt_data.get("name", str(prompt_id))
                if is_filtered and query not in (name or "").lower():
                    continue
                item = QListWidgetItem(name)
                item.setSizeHint(QSize(0, 44))
                item.setData(Qt.UserRole, prompt_id)
                self.voice_prompt_order_list.addItem(item)

            if current_prompt_id is not None:
                for row in range(self.voice_prompt_order_list.count()):
                    if self.voice_prompt_order_list.item(row).data(Qt.UserRole) == current_prompt_id:
                        self.voice_prompt_order_list.setCurrentRow(row)
                        break
        finally:
            self._is_updating_voice_prompt_order_list = False

    def _apply_voice_prompt_filter(self, *args):
        self.populate_voice_prompt_order_list()

    def _on_voice_prompt_list_current_changed(self, current, previous):
        if getattr(self, "_is_updating_voice_prompt_order_list", False):
            return
        if current is None:
            return
        prompt_id = current.data(Qt.UserRole)
        if prompt_id is None:
            return
        index = self.voice_prompt_combo.findData(prompt_id)
        if index >= 0 and index != self.voice_prompt_combo.currentIndex():
            self.voice_prompt_combo.setCurrentIndex(index)

    def on_voice_prompt_order_changed(self, *args):
        if getattr(self, "_is_updating_voice_prompt_order_list", False):
            return

        prompts = self.settings.get_voice_prompts()
        for row in range(self.voice_prompt_order_list.count()):
            item = self.voice_prompt_order_list.item(row)
            prompt_id = item.data(Qt.UserRole)
            if prompt_id not in prompts:
                continue
            prompt_data = prompts[prompt_id]
            new_position = (row + 1) * 10
            if prompt_data.get("position", 999) == new_position:
                continue

            self.settings.update_voice_prompt(
                prompt_id,
                prompt_data.get("name", str(prompt_id)),
                prompt_data.get("prompt", ""),
                prompt_data.get("status", ""),
                prompt_data.get("insert_directly", True),
                new_position,
                prompt_data.get("include_selected_text", False),
                prompt_data.get("prompt_order", "prompt_transcription_selected"),
            )

        self.populate_voice_prompt_combo()
        self.populate_voice_prompt_order_list()
    
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
            
            # Charge l'ordre des éléments
            order = prompt_data.get("prompt_order", "prompt_transcription_selected")
            for i in range(self.voice_prompt_order_combo.count()):
                if self.voice_prompt_order_combo.itemData(i) == order:
                    self.voice_prompt_order_combo.setCurrentIndex(i)
                    break
    
    def save_voice_prompt(self):
        """Save the current voice prompt"""
        if self.voice_prompt_combo.count() == 0:
            return
            
        prompt_id = self.voice_prompt_combo.currentData()
        name = self.voice_prompt_name_input.text().strip()
        prompt = self.voice_prompt_text_input.toPlainText()
        status = self.voice_prompt_status_input.text()
        insert_directly = self.voice_prompt_insert_directly.isChecked()

        position = 999
        try:
            position = self.settings.get_voice_prompt(prompt_id).get("position", 999)
        except Exception:
            position = 999
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

        self.populate_voice_prompt_order_list()
        
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
            "",
            "Traitement en cours...",
            True,
            999,
            False,
            "prompt_transcription_selected"
        )
        
        # Mettre à jour la liste des prompts
        self.populate_voice_prompt_combo()

        self.populate_voice_prompt_order_list()
        
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

            self.populate_voice_prompt_order_list()
            
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
            self.populate_voice_prompt_order_list()
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

    def update_reasoning_effort_ui(self):
        """Mettre à jour la liste des efforts de raisonnement selon le modèle choisi."""
        model = self.model_combo.currentText() if self.model_combo else ""
        allowed = get_reasoning_efforts_for_model(model)

        self.reasoning_effort_combo.blockSignals(True)
        self.reasoning_effort_combo.clear()
        if allowed:
            self.reasoning_effort_combo.addItems(allowed)
            saved_effort = self.settings.get_reasoning_effort()
            normalized = normalize_reasoning_effort(model, saved_effort)
            self.reasoning_effort_combo.setCurrentText(normalized)
            self.reasoning_effort_combo.setEnabled(True)
        else:
            self.reasoning_effort_combo.addItem("none")
            self.reasoning_effort_combo.setCurrentIndex(0)
            self.reasoning_effort_combo.setEnabled(False)
        self.reasoning_effort_combo.blockSignals(False)
    
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
        reasoning_effort = self.reasoning_effort_combo.currentText().strip()
        use_custom = self.use_custom_endpoint_checkbox.isChecked()
        custom_endpoint = self.custom_endpoint_input.text().strip()
        custom_endpoint_type = self.custom_endpoint_type_combo.currentData() if self.custom_endpoint_type_combo else "ollama"
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
        self.settings.set_reasoning_effort(normalize_reasoning_effort(model, reasoning_effort))
        self.settings.set_use_custom_endpoint(use_custom)
        self.settings.set_custom_endpoint(custom_endpoint)
        self.settings.set_custom_endpoint_type(custom_endpoint_type)
        self.settings.set_custom_model(custom_model)
        self.settings.set_hotkey(self.default_hotkey)
        self.settings.set_screenshot_hotkey(self.default_screenshot_hotkey)
        self.settings.set_custom_hotkey(self.default_custom_hotkey)
        self.settings.set_theme(self.default_theme)
        self.settings.set_prompts(self.default_prompts)
        self.settings.set_voice_prompts(self.default_voice_prompts)
        self.settings.set_microphone_index(self.default_microphone_index)
        self.settings.set_describe_response_prompt(self.default_describe_response_prompt)
        
        # Mettre à jour la configuration du client API sans redémarrage
        if self.context_menu_manager:
            self.context_menu_manager.update_client_config()
        
        QMessageBox.information(self, "Configuration enregistrée", 
                              "La configuration a été enregistrée avec succès.\n\nLes modifications sont actives immédiatement.")
