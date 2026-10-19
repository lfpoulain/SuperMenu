"""Pages de réglages de la fenêtre principale : fournisseur, modèles et capture."""

from supermenu_core.config.openai_models import (
    AVAILABLE_MODELS,
    get_reasoning_efforts_for_model,
    normalize_reasoning_effort,
)
from src.config.settings import CUSTOM_REASONING_EFFORTS
from supermenu_core.ui.controls import ChoiceBox
from supermenu_core.ui.model_catalog import (
    DeviceNameButton,
    clear_model_provenance,
    configure_model_combo,
    populate_model_catalog,
    restore_model_target,
    selected_model_details,
    selected_model_id,
    selected_model_target,
    selection_summary,
)
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QTimer, Qt, Signal
from supermenu_core.utils.validators import Validators
from src.ui.background_worker import _BackgroundWorker
from supermenu_core.api.model_capabilities import (
    choose_reasoning_option,
    normalize_reasoning_option,
)


class _CustomModelsWorker(_BackgroundWorker):
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, endpoint: str, api_key: str | None, endpoint_type: str):
        super().__init__()
        self.endpoint = endpoint
        self.api_key = api_key
        self.endpoint_type = endpoint_type

    def run(self):
        try:
            from src.api.openai_client import OpenAIClient

            success, result = OpenAIClient.fetch_available_model_details(
                self.endpoint,
                self.api_key,
                endpoint_type=self.endpoint_type,
            )
            if success:
                self.finished_ok.emit(result)
            else:
                self.failed.emit(str(result))
        except Exception as e:
            self.failed.emit(str(e))


class SettingsPageMixin:
    """Provider, model and capture settings pages of the main window."""

    def create_settings_tab(self):
        """Create the settings tab"""
        from supermenu_core.ui.settings_panel import SettingsPanel, Disclosure

        self.settings_panel = SettingsPanel()
        pages = self.settings_panel.add_standard_pages()
        text_page, voice_page = pages["text"], pages["voice"]
        shortcuts_page, app_page = pages["shortcuts"], pages["app"]
        self.app_settings_layout = app_page

        models_widget = QWidget()
        models_layout = QVBoxLayout(models_widget)
        models_layout.setContentsMargins(0, 0, 0, 0)
        models_layout.setSpacing(8)

        self.ai_provider_combo = ChoiceBox()
        self.ai_provider_combo.addItem("OpenAI", "openai")
        self.ai_provider_combo.addItem("Ollama / LM Studio", "custom")
        self.ai_provider_combo.addItem("IA locale Microsoft — Foundry Local", "foundry")
        self.ai_provider_combo.setCurrentIndex(self.ai_provider_combo.findData(self.settings.get_ai_provider()))
        models_layout.addWidget(QLabel("Moteur de texte"))
        models_layout.addWidget(self.ai_provider_combo)

        self.openai_group = QGroupBox("OpenAI")
        openai_layout = QVBoxLayout(self.openai_group)

        api_key_label = QLabel("Clé API:")
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setText(self.settings.get_api_key())

        model_label = QLabel("Modèle:")
        self.model_combo = ChoiceBox()
        self.model_combo.addItems(AVAILABLE_MODELS)
        self.model_combo.setCurrentText(self.settings.get_model())

        reasoning_label = QLabel("Raisonnement:")
        self.reasoning_effort_combo = ChoiceBox()
        self.reasoning_effort_combo.setToolTip(
            "Effort OpenAI propre au modèle. GPT-5.6 accepte "
            "none, low, medium, high, xhigh et max; GPT-5.4 s'arrête à xhigh."
        )

        openai_layout.addWidget(api_key_label)
        openai_layout.addWidget(self.api_key_input)
        openai_layout.addWidget(model_label)
        openai_layout.addWidget(self.model_combo)
        openai_advanced = Disclosure()
        openai_advanced.content_layout.addWidget(reasoning_label)
        openai_advanced.content_layout.addWidget(self.reasoning_effort_combo)
        openai_layout.addWidget(openai_advanced)

        self.custom_group = QGroupBox("Endpoint personnalisé (Ollama, etc.)")
        custom_layout = QVBoxLayout(self.custom_group)

        custom_endpoint_label = QLabel("URL de l'endpoint (ex: http://localhost:11434):")
        self.custom_endpoint_input = QLineEdit()
        self.custom_endpoint_input.setText(self.settings.get_custom_endpoint())
        self.custom_endpoint_input.setPlaceholderText("http://localhost:11434")

        custom_endpoint_api_key_label = QLabel(
            "Jeton de l'endpoint (optionnel) :"
        )
        self.custom_endpoint_api_key_input = QLineEdit()
        self.custom_endpoint_api_key_input.setEchoMode(QLineEdit.Password)
        self.custom_endpoint_api_key_input.setText(
            self.settings.get_custom_endpoint_api_key()
        )
        self.custom_endpoint_api_key_input.setPlaceholderText(
            "Jeton distinct de la clé OpenAI"
        )

        custom_endpoint_type_label = QLabel("Type d'endpoint :")
        self.custom_endpoint_type_combo = ChoiceBox()
        self.custom_endpoint_type_combo.addItem("Ollama", "ollama")
        self.custom_endpoint_type_combo.addItem("LM Studio / Bionic", "lmstudio")
        current_custom_endpoint_type = self.settings.get_custom_endpoint_type()
        for i in range(self.custom_endpoint_type_combo.count()):
            if self.custom_endpoint_type_combo.itemData(i) == current_custom_endpoint_type:
                self.custom_endpoint_type_combo.setCurrentIndex(i)
                break

        custom_model_label = QLabel("Modèle:")
        custom_model_layout = QHBoxLayout()
        self.custom_model_combo = ChoiceBox()
        configure_model_combo(self.custom_model_combo)
        self.custom_model_combo.setPlaceholderText("Sélectionnez ou entrez un modèle")
        custom_model_layout.addWidget(self.custom_model_combo, 1)

        refresh_models_button = QPushButton("Actualiser")
        refresh_models_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_models_button.clicked.connect(self.refresh_custom_models)
        custom_model_layout.addWidget(refresh_models_button)

        custom_layout.addWidget(custom_endpoint_label)
        custom_layout.addWidget(self.custom_endpoint_input)
        endpoint_advanced = Disclosure()
        endpoint_options = endpoint_advanced.content_layout
        endpoint_options.addWidget(custom_endpoint_api_key_label)
        endpoint_options.addWidget(self.custom_endpoint_api_key_input)
        endpoint_options.addWidget(custom_endpoint_type_label)
        endpoint_options.addWidget(self.custom_endpoint_type_combo)
        custom_layout.addWidget(custom_model_label)
        custom_layout.addLayout(custom_model_layout)
        self.custom_model_provenance = QLabel()
        self.custom_model_provenance.setTextFormat(Qt.TextFormat.PlainText)
        self.custom_model_provenance.setWordWrap(True)
        custom_layout.addWidget(self.custom_model_provenance)
        self.device_name_button = DeviceNameButton(self.custom_model_combo, self.settings, lambda: self.custom_endpoint_input.text().strip())
        custom_layout.addWidget(self.device_name_button)

        self.custom_reasoning_label = QLabel("Raisonnement / think :")
        self.custom_reasoning_effort_combo = ChoiceBox()
        self.custom_reasoning_effort_combo.setToolTip(
            "Les choix sont adaptés aux capacités annoncées par le modèle."
        )
        endpoint_options.addWidget(self.custom_reasoning_label)
        endpoint_options.addWidget(self.custom_reasoning_effort_combo)

        current_custom_model = self.settings.get_custom_model()
        if current_custom_model:
            self.custom_model_combo.addItem(current_custom_model)
            self.custom_model_combo.setCurrentText(current_custom_model)
            restore_model_target(self.custom_model_combo, self.settings.get_custom_model_target())

        self.custom_model_combo.currentTextChanged.connect(
            self.update_custom_reasoning_effort_ui
        )
        self.custom_reasoning_effort_combo.currentIndexChanged.connect(
            self._apply_custom_reasoning_setting
        )
        self.custom_endpoint_type_combo.currentIndexChanged.connect(
            self._on_custom_endpoint_configuration_changed
        )
        self.custom_endpoint_input.editingFinished.connect(
            self._on_custom_endpoint_configuration_changed
        )
        self.update_custom_reasoning_effort_ui()

        custom_layout.addWidget(endpoint_advanced)

        models_layout.addWidget(self.openai_group)
        models_layout.addWidget(self.custom_group)
        from src.ui.foundry_settings import FoundrySettingsWidget
        self.foundry_group = FoundrySettingsWidget(self.settings, self)
        models_layout.addWidget(self.foundry_group)
        self.ai_provider_combo.currentIndexChanged.connect(self.toggle_custom_endpoint)

        self.toggle_custom_endpoint()
        self.model_combo.currentTextChanged.connect(self.update_reasoning_effort_ui)
        self.update_reasoning_effort_ui()
        
        # Import/Export section
        import_export_group = QGroupBox("Import/Export des Prompts")
        import_export_layout = QVBoxLayout(import_export_group)
        
        # Description
        info_label = QLabel("Exportez et importez tous vos prompts (texte et vocaux) en un seul fichier.")
        info_label.setWordWrap(True)
        info_label.setObjectName("mutedText")
        import_export_layout.addWidget(info_label)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        export_button = QPushButton("Exporter tous les Prompts")
        # Icône retirée
        export_button.clicked.connect(self.export_all_prompts)
        export_button.setMinimumHeight(30)
        buttons_layout.addWidget(export_button)
        
        import_button = QPushButton("Importer tous les Prompts")
        # Icône retirée
        import_button.clicked.connect(self.import_all_prompts)
        import_button.setMinimumHeight(30)
        buttons_layout.addWidget(import_button)
        
        import_export_layout.addLayout(buttons_layout)
        
        from supermenu_core.ui.shortcut_settings import ShortcutSettings
        hotkey_group = ShortcutSettings()
        self.shortcut_settings = hotkey_group
        self.hotkey_label = hotkey_group.add_shortcut("Menu principal", self.settings.get_hotkey(), self.change_hotkey)
        self.custom_hotkey_label = hotkey_group.add_shortcut("Mode personnalisé", self.settings.get_custom_hotkey(), self.change_custom_hotkey)
        self.voice_hotkey_label = hotkey_group.add_shortcut("Menu vocal", self.settings.get_voice_hotkey(), self.change_voice_hotkey)
        self.screenshot_hotkey_label = hotkey_group.add_shortcut("Capture d’écran", self.settings.get_screenshot_hotkey(), self.change_screenshot_hotkey)
        if self.context_menu_manager:
            hotkey_group.add_test(self.context_menu_manager.show_menu)
        for manager, _field, _hotkey in self._core_hotkey_rows():
            registration_failed = getattr(manager, "registration_failed", None)
            if registration_failed is not None:
                registration_failed.connect(self._on_hotkey_registration_failed)
        self._refresh_hotkey_states()

        # Shared voice controls keep the speech engine independent of text settings.
        from supermenu_core.ui.speech_settings import SpeechSettingsWidget
        from src.audio.speech_backend import create_speech_backend

        self.speech_settings = SpeechSettingsWidget(
            self.settings, lambda options: create_speech_backend(self.settings, options), self
        )
        microphone_group = self.speech_settings
        self.speech_settings.dictation_requested.connect(self.start_dictation)
        if self.context_menu_manager:
            self.speech_settings.settings_saved.connect(self.context_menu_manager.update_client_config)
        self.api_key_input.textChanged.connect(self.speech_settings.api_key_input.setText)
        self.speech_settings.api_key_input.textChanged.connect(self.api_key_input.setText)
        QApplication.instance().aboutToQuit.connect(lambda: self.speech_settings.cancel(silent=True))

        # Screenshot section
        screenshot_group = QGroupBox("Capture d'écran")
        self.screenshot_group = screenshot_group
        screenshot_layout = QVBoxLayout(screenshot_group)
        screenshot_capture_mode_label = QLabel("Mode de capture d'écran :")
        screenshot_layout.addWidget(screenshot_capture_mode_label)

        self.screenshot_capture_mode_combo = ChoiceBox()
        self.screenshot_capture_mode_combo.addItem("Plein écran", "fullscreen")
        self.screenshot_capture_mode_combo.addItem("Sélection de zone", "region")
        self.screenshot_capture_mode_combo.addItem("Demander à chaque capture", "ask")

        current_mode = self.settings.get_screenshot_capture_mode()
        for i in range(self.screenshot_capture_mode_combo.count()):
            if self.screenshot_capture_mode_combo.itemData(i) == current_mode:
                self.screenshot_capture_mode_combo.setCurrentIndex(i)
                break

        self.screenshot_capture_mode_combo.currentIndexChanged.connect(self.on_screenshot_capture_mode_changed)
        screenshot_layout.addWidget(self.screenshot_capture_mode_combo)

        self.save_screenshot_capture_mode_button = QPushButton("Enregistrer le mode de capture")
        self.save_screenshot_capture_mode_button.setProperty("variant", "primary")
        self.save_screenshot_capture_mode_button.clicked.connect(self.save_screenshot_capture_mode)
        screenshot_layout.addWidget(self.save_screenshot_capture_mode_button)

        self._update_screenshot_capture_mode_ui_state()

        # Response window
        response_window_group = QGroupBox("Fenêtre de correction")
        response_window_layout = QVBoxLayout(response_window_group)

        response_window_info = QLabel(
            "Retrouvez votre dernière réponse pour la copier ou l’insérer dans votre application."
        )
        response_window_info.setWordWrap(True)
        response_window_layout.addWidget(response_window_info)

        self.open_response_window_button = QPushButton("Ouvrir la fenêtre de correction")
        self.open_response_window_button.clicked.connect(self.open_response_window)
        self.open_response_window_button.setEnabled(self.context_menu_manager is not None)
        response_window_layout.addWidget(self.open_response_window_button)

        from supermenu_core.ui.application_settings import ApplicationSettings, FeatureModeSettings
        self.application_settings = ApplicationSettings(self.settings, self.check_for_updates)
        self.feature_mode_settings = FeatureModeSettings(
            self.settings, screen_capture=True, text_model_retention=True
        )
        self.feature_mode_settings.modes_changed.connect(self.apply_feature_modes)
        self.theme_combo = self.application_settings.theme_combo
        self.update_channel_combo = self.application_settings.channel_combo
        self.update_channel_description = self.application_settings.channel_hint
        self.app_save_button = self.settings_panel.set_save_action(
            "app", self.save_theme_selection, "Appliquer"
        )

        text_page.addWidget(models_widget)
        voice_page.addWidget(microphone_group)
        from supermenu_core.ui.dictation_settings import DictationBehaviorSettings
        self.dictation_behavior = DictationBehaviorSettings(self.settings)
        voice_page.addWidget(self.dictation_behavior)
        self.text_save_button = self.settings_panel.set_save_action("text", self.save_api_key)
        self.settings_panel.set_footer("voice", self.speech_settings.actions_widget)
        shortcuts_page.addWidget(hotkey_group)
        from supermenu_core.ui.dictation_settings import DictationShortcutSettings
        self.dictation_shortcut_settings = DictationShortcutSettings(self.settings, self.dictation_hotkey_manager)
        self.dictation_shortcut_settings.record_requested.connect(self.record_dictation_hotkey)
        shortcuts_page.insertWidget(2, self.dictation_shortcut_settings)
        shortcuts_page.addWidget(screenshot_group)
        app_page.insertWidget(2, self.application_settings)
        app_page.insertWidget(3, self.feature_mode_settings)
        app_page.addWidget(response_window_group)
        transfer = Disclosure("Importer ou exporter les prompts")
        transfer.content_layout.addWidget(import_export_group)
        app_page.addWidget(transfer)
        self.tab_widget.addTab(self.settings_panel, "Réglages")

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

    def toggle_custom_endpoint(self):
        """Afficher les réglages du fournisseur sélectionné."""
        provider = self.ai_provider_combo.currentData()
        use_custom = provider == "custom"
        
        # Afficher/masquer les sections appropriées
        self.openai_group.setVisible(provider == "openai")
        self.custom_group.setVisible(use_custom)
        self.foundry_group.setVisible(provider == "foundry")
        if provider == "foundry" and not self.foundry_group.probed:
            self.foundry_group.probe()
        if use_custom and self.custom_endpoint_input.text().strip():
            self._custom_models_refresh_timer.start()
        else:
            self._custom_models_refresh_timer.stop()

    def update_reasoning_effort_ui(self):
        """Mettre à jour la liste des efforts de raisonnement selon le modèle choisi."""
        model = self.model_combo.currentText() if self.model_combo else ""
        allowed = get_reasoning_efforts_for_model(model)

        self.reasoning_effort_combo.blockSignals(True)
        self.reasoning_effort_combo.clear()
        if allowed:
            self.reasoning_effort_combo.addItems(allowed)
            saved_effort = self.settings.get_openai_reasoning_effort(model)
            normalized = normalize_reasoning_effort(model, saved_effort)
            self.reasoning_effort_combo.setCurrentText(normalized)
            self.reasoning_effort_combo.setEnabled(True)
        else:
            self.reasoning_effort_combo.addItem("none")
            self.reasoning_effort_combo.setCurrentIndex(0)
            self.reasoning_effort_combo.setEnabled(False)
        self.reasoning_effort_combo.blockSignals(False)

    def refresh_custom_models(self, _checked=False, *, silent=False):
        """Récupérer la liste des modèles disponibles depuis l'endpoint personnalisé"""
        if self._custom_models_worker and self._custom_models_worker.isRunning():
            return

        endpoint = self.custom_endpoint_input.text().strip()

        if not endpoint:
            if not silent:
                QMessageBox.warning(
                    self,
                    "Endpoint manquant",
                    "Veuillez d'abord entrer l'URL de l'endpoint personnalisé.",
                )
            return

        # Valider l'URL
        is_valid, error_msg = Validators.validate_url(endpoint)
        if not is_valid:
            if not silent:
                QMessageBox.warning(self, "URL invalide", error_msg)
            return

        self._custom_models_silent = silent
        if not silent:
            from PySide6.QtWidgets import QProgressDialog

            self._custom_models_progress = QProgressDialog(
                "Récupération des modèles disponibles...", "Annuler", 0, 0, self
            )
            self._custom_models_progress.setWindowModality(Qt.WindowModal)
            self._custom_models_progress.setMinimumDuration(0)
            self._custom_models_progress.setValue(0)
            self._custom_models_progress.show()
            QApplication.processEvents()

        # Use only the credential explicitly dedicated to this endpoint.
        api_key = self.custom_endpoint_api_key_input.text().strip() or None
        endpoint_type = self.custom_endpoint_type_combo.currentData() if self.custom_endpoint_type_combo else "ollama"
        self._custom_models_worker = _CustomModelsWorker(endpoint, api_key, endpoint_type)
        self._custom_models_worker.finished_ok.connect(self._on_custom_models_ok)
        self._custom_models_worker.failed.connect(self._on_custom_models_failed)
        self._custom_models_worker.start()

    def _on_custom_models_ok(self, model_details: list):
        if self._custom_models_progress:
            self._custom_models_progress.close()
            self._custom_models_progress = None

        silent = self._custom_models_silent
        self._custom_models_silent = False
        worker = self._custom_models_worker
        current_endpoint = self.custom_endpoint_input.text().strip()
        current_type = self.custom_endpoint_type_combo.currentData()
        if worker and (
            worker.endpoint != current_endpoint or worker.endpoint_type != current_type
        ):
            self._custom_models_refresh_timer.start()
            return

        self._custom_model_details = populate_model_catalog(
            self.custom_model_combo, model_details,
            lmstudio=current_type == "lmstudio",
            endpoint=self.custom_endpoint_input.text().strip(), settings=self.settings,
        )
        self.update_custom_reasoning_effort_ui()

        if not silent:
            QMessageBox.information(
                self,
                "Modèles récupérés",
                f"{len(self._custom_model_details)} modèle(s) trouvé(s) sur le serveur.",
            )

    def _on_custom_models_failed(self, error: str):
        if self._custom_models_progress:
            self._custom_models_progress.close()
            self._custom_models_progress = None
        silent = self._custom_models_silent
        self._custom_models_silent = False
        self.update_custom_reasoning_effort_ui()
        if not silent:
            QMessageBox.warning(
                self,
                "Erreur",
                f"Impossible de récupérer les modèles:\n\n{error}",
            )

    def save_api_key(self):
        """Save the API key and configuration"""
        api_key = self.api_key_input.text().strip()
        model = self.model_combo.currentText()
        provider = self.ai_provider_combo.currentData()
        use_custom = provider == "custom"
        custom_endpoint = self.custom_endpoint_input.text().strip()
        custom_endpoint_api_key = self.custom_endpoint_api_key_input.text().strip()
        custom_endpoint_type = self.custom_endpoint_type_combo.currentData() if self.custom_endpoint_type_combo else "ollama"
        custom_model = selected_model_id(self.custom_model_combo)
        openai_reasoning_effort = self.reasoning_effort_combo.currentText().strip()
        custom_reasoning_effort = normalize_reasoning_option(
            self.custom_reasoning_effort_combo.currentData(), "none"
        )
        
        # Validation
        if provider == "openai" and api_key:
            is_valid, error_msg = Validators.validate_api_key(api_key)
            if not is_valid:
                QMessageBox.warning(self, "Clé API invalide", error_msg)
                return
        
        if use_custom:
            if not custom_endpoint:
                QMessageBox.warning(
                    self,
                    "Endpoint manquant",
                    "L'URL de l'endpoint personnalisé est obligatoire.",
                )
                return
            is_valid, error_msg = Validators.validate_url(custom_endpoint)
            if not is_valid:
                QMessageBox.warning(self, "URL invalide", error_msg)
                return

            if not custom_model:
                QMessageBox.warning(
                    self,
                    "Modèle manquant",
                    "Le modèle personnalisé est obligatoire.",
                )
                return
            is_valid, error_msg = Validators.validate_model_name(custom_model)
            if not is_valid:
                QMessageBox.warning(self, "Nom de modèle invalide", error_msg)
                return
        
        normalized_openai_effort = normalize_reasoning_effort(
            model,
            openai_reasoning_effort,
        )
        normalized_custom_effort = normalize_reasoning_option(
            custom_reasoning_effort, "none"
        )

        # Save settings
        self.settings.set_api_key(api_key)
        self.settings.set_model(model)
        self.settings.set_openai_reasoning_effort(
            normalized_openai_effort,
            model,
        )
        self.settings.set_custom_reasoning_effort(normalized_custom_effort)
        self.settings.set_ai_provider(provider)
        self.settings.set_foundry_model(self.foundry_group.selected_model())
        self.settings.set_foundry_device(self.foundry_group.selected_device())
        self.settings.set_custom_endpoint(custom_endpoint)
        self.settings.set_custom_endpoint_api_key(custom_endpoint_api_key)
        self.settings.set_custom_endpoint_type(custom_endpoint_type)
        self.settings.set_custom_model(custom_model)
        self.settings.set_custom_model_target(selected_model_target(self.custom_model_combo))
        self.settings.sync()

        self.reasoning_effort_combo.blockSignals(True)
        self.reasoning_effort_combo.setCurrentText(normalized_openai_effort)
        self.reasoning_effort_combo.blockSignals(False)
        self.custom_reasoning_effort_combo.blockSignals(True)
        custom_effort_index = self.custom_reasoning_effort_combo.findData(
            normalized_custom_effort
        )
        if custom_effort_index >= 0:
            self.custom_reasoning_effort_combo.setCurrentIndex(custom_effort_index)
        self.custom_reasoning_effort_combo.blockSignals(False)

        # Mettre à jour la configuration du client API sans redémarrage
        if self.context_menu_manager:
            self.context_menu_manager.update_client_config()

        QMessageBox.information(
            self,
            "Configuration enregistrée",
            "La configuration a été enregistrée avec succès.\n\n"
            "Les modifications sont actives immédiatement.",
        )

    def _on_custom_endpoint_configuration_changed(self, *_args):
        """Invalidate stale capabilities and refresh them without blocking the UI."""
        self._custom_model_details = {}
        clear_model_provenance(self.custom_model_combo)
        self.update_custom_reasoning_effort_ui()
        if (
            self.ai_provider_combo.currentData() == "custom"
            and self.custom_endpoint_input.text().strip()
        ):
            self._custom_models_refresh_timer.start()

    def _get_custom_model_details(self, model):
        selected = selected_model_details(self.custom_model_combo, self._custom_model_details)
        if selected and selected["id"] == model:
            return selected
        details = self._custom_model_details.get(model)
        if details:
            return details
        for candidate in self._custom_model_details.values():
            if model in candidate.get("identifiers", []):
                return candidate
        return None

    def _apply_custom_reasoning_setting(self, *_args):
        """Apply a local reasoning choice as soon as the user selects it."""
        option = normalize_reasoning_option(
            self.custom_reasoning_effort_combo.currentData()
        )
        if not option or option == self.settings.get_custom_reasoning_effort():
            return

        self.settings.set_custom_reasoning_effort(option)
        self.settings.sync()
        if (
            self.context_menu_manager
            and self.ai_provider_combo.currentData() == "custom"
        ):
            self.context_menu_manager.update_client_config()

    def update_custom_reasoning_effort_ui(self, *_args):
        """Adapt reasoning choices to the selected local model at runtime."""
        if not hasattr(self, "custom_reasoning_effort_combo"):
            return

        combo = self.custom_reasoning_effort_combo
        previous = normalize_reasoning_option(combo.currentData())
        if not previous:
            previous = normalize_reasoning_option(combo.currentText())
        preferred = previous or self.settings.get_custom_reasoning_effort()
        model = selected_model_id(self.custom_model_combo)
        endpoint_type = self.custom_endpoint_type_combo.currentData()
        details = self._get_custom_model_details(model)
        self.custom_model_provenance.setText(
            selection_summary(self.custom_model_combo, self._custom_model_details, lmstudio=endpoint_type == "lmstudio")
        )
        self.custom_model_provenance.setVisible(endpoint_type == "lmstudio")
        self.device_name_button.refresh()

        combo.blockSignals(True)
        combo.clear()

        if endpoint_type == "lmstudio" and details:
            options = details.get("reasoning_options", [])
            if details.get("reasoning_supported") is False:
                combo.addItem("Non pris en charge", "none")
                combo.setEnabled(False)
                self.custom_reasoning_label.setText(
                    "Raisonnement / think (non pris en charge) :"
                )
                combo.setToolTip(
                    "LM Studio n'annonce aucune option de raisonnement pour ce modèle."
                )
                combo.blockSignals(False)
                return

            if options:
                selected = choose_reasoning_option(
                    options,
                    preferred=preferred,
                    default=details.get("reasoning_default"),
                )
                for option in options:
                    combo.addItem(option, option)
                selected_index = combo.findData(selected)
                combo.setCurrentIndex(max(0, selected_index))
                combo.setEnabled(len(options) > 1)
                self.custom_reasoning_label.setText(
                    "Raisonnement / think (détecté) :"
                )
                combo.setToolTip(
                    "Options annoncées par LM Studio pour ce modèle : "
                    + ", ".join(options)
                )
                combo.blockSignals(False)
                return

        fallback_options = list(CUSTOM_REASONING_EFFORTS)
        if preferred in {"off", "on"}:
            fallback_options = ["off", "on"]
        for option in fallback_options:
            combo.addItem(option, option)
        selected = choose_reasoning_option(fallback_options, preferred=preferred)
        selected_index = combo.findData(selected)
        combo.setCurrentIndex(max(0, selected_index))
        combo.setEnabled(True)
        self.custom_reasoning_label.setText("Raisonnement / think :")
        if endpoint_type == "lmstudio":
            combo.setToolTip(
                "Détection en attente ou indisponible. Cliquez sur Actualiser pour "
                "lire les options annoncées par LM Studio."
            )
        else:
            combo.setToolTip(
                "Ollama adapte think aux capacités disponibles lors de la requête."
            )
        combo.blockSignals(False)
