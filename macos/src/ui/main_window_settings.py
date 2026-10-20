"""Pages de réglages de la fenêtre principale : fournisseur, modèles et application."""

from __future__ import annotations

import logging
from supermenu_core.config.openai_models import (
    AVAILABLE_MODELS,
    get_reasoning_efforts_for_model,
)
from supermenu_core.config.provider_settings import CUSTOM_REASONING_EFFORTS
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
from src.api.apple_foundation_client import FoundationModelsRequest
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
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl, Qt, Signal
from supermenu_core.ui.theme_manager import ThemeManager
from supermenu_core.utils.validators import Validators
from supermenu_core.ui.verification_status import VerificationStatus
from src.ui.background_worker import _BackgroundWorker
from supermenu_core.api.model_capabilities import (
    choose_reasoning_option,
    normalize_reasoning_option,
)
from datetime import datetime
from supermenu_core.config.feature_modes import experimental_enabled
from src.utils.logger import log
from src.utils.paths import user_config_dir, user_log_dir


class CustomModelsWorker(_BackgroundWorker):
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
        except Exception as exc:
            self.failed.emit(str(exc))


class SettingsPageMixin:
    """Provider, model and application settings pages of the main window."""

    def _create_settings_tab(self):
        from supermenu_core.ui.settings_panel import SettingsPanel, Disclosure

        container = self.settings_panel = SettingsPanel()
        pages = container.add_standard_pages()
        layout, voice_page = pages["text"], pages["voice"]
        shortcuts_page, app_page = pages["shortcuts"], pages["app"]

        layout.addWidget(QLabel("Moteur de texte"))
        self.provider_combo = ChoiceBox()
        self.provider_combo.addItem("OpenAI", "openai")
        self.provider_combo.addItem("Ollama / LM Studio", "custom")
        self.provider_combo.addItem("Apple Intelligence — local", "apple")
        self.provider_combo.setCurrentIndex(
            self.provider_combo.findData(self.settings.get_ai_provider())
        )
        layout.addWidget(self.provider_combo)

        api_group = QGroupBox("OpenAI")
        api_layout = QVBoxLayout(api_group)
        self.openai_group = api_group
        api_layout.addWidget(QLabel("Clé API"))
        self.api_key = QLineEdit(self.settings.get_api_key())
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("sk-…")
        api_layout.addWidget(self.api_key)
        api_layout.addWidget(QLabel("Modèle"))
        self.model_combo = ChoiceBox()
        self.model_combo.addItems(AVAILABLE_MODELS)
        self.model_combo.setCurrentText(self.settings.get_model())
        self.model_combo.currentTextChanged.connect(self._refresh_reasoning_options)
        api_layout.addWidget(self.model_combo)
        openai_advanced = Disclosure()
        openai_advanced.content_layout.addWidget(QLabel("Raisonnement"))
        self.reasoning_combo = ChoiceBox()
        openai_advanced.content_layout.addWidget(self.reasoning_combo)
        api_layout.addWidget(openai_advanced)
        layout.addWidget(api_group)

        endpoint_group = QGroupBox("Endpoint personnalisé (Ollama, etc.)")
        endpoint_layout = QVBoxLayout(endpoint_group)
        self.custom_group = endpoint_group
        endpoint_layout.addWidget(
            QLabel("URL de l’endpoint (ex: http://localhost:11434) :")
        )
        self.custom_endpoint = QLineEdit(self.settings.get_custom_endpoint())
        self.custom_endpoint.setPlaceholderText("http://localhost:11434")
        endpoint_layout.addWidget(self.custom_endpoint)
        endpoint_advanced = Disclosure()
        endpoint_options = endpoint_advanced.content_layout
        endpoint_options.addWidget(QLabel("Jeton de l’endpoint (optionnel) :"))
        self.custom_endpoint_api_key = QLineEdit(
            self.settings.get_custom_endpoint_api_key()
        )
        self.custom_endpoint_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.custom_endpoint_api_key.setPlaceholderText(
            "Jeton distinct de la clé OpenAI"
        )
        endpoint_options.addWidget(self.custom_endpoint_api_key)
        endpoint_options.addWidget(QLabel("Type d’endpoint"))
        self.endpoint_type = ChoiceBox()
        self.endpoint_type.addItem("Ollama", "ollama")
        self.endpoint_type.addItem("LM Studio / Bionic", "lmstudio")
        type_index = self.endpoint_type.findData(
            self.settings.get_custom_endpoint_type()
        )
        self.endpoint_type.setCurrentIndex(max(0, type_index))
        endpoint_options.addWidget(self.endpoint_type)
        endpoint_layout.addWidget(QLabel("Modèle"))
        custom_model_row = QHBoxLayout()
        self.custom_model = ChoiceBox()
        configure_model_combo(self.custom_model)
        self.custom_model.setPlaceholderText("Sélectionnez ou entrez un modèle")
        saved_custom_model = self.settings.get_custom_model()
        if saved_custom_model:
            self.custom_model.addItem(saved_custom_model)
            self.custom_model.setCurrentText(saved_custom_model)
            restore_model_target(self.custom_model, self.settings.get_custom_model_target())
        custom_model_row.addWidget(self.custom_model, 1)
        refresh_models = QPushButton("Actualiser")
        refresh_models.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_models.clicked.connect(self.refresh_custom_models)
        custom_model_row.addWidget(refresh_models)
        endpoint_layout.addLayout(custom_model_row)
        self.custom_model_provenance = QLabel()
        self.custom_model_provenance.setTextFormat(Qt.TextFormat.PlainText)
        self.custom_model_provenance.setWordWrap(True)
        endpoint_layout.addWidget(self.custom_model_provenance)
        self.device_name_button = DeviceNameButton(self.custom_model, self.settings, lambda: self.custom_endpoint.text().strip())
        endpoint_layout.addWidget(self.device_name_button)
        self.custom_reasoning_label = QLabel("Raisonnement / think :")
        endpoint_options.addWidget(self.custom_reasoning_label)
        self.custom_reasoning = ChoiceBox()
        endpoint_options.addWidget(self.custom_reasoning)
        self.custom_endpoint.textChanged.connect(
            self._invalidate_custom_model_details
        )
        self.endpoint_type.currentIndexChanged.connect(
            self._invalidate_custom_model_details
        )
        self.custom_model.currentTextChanged.connect(
            self._update_custom_reasoning_options
        )
        self._update_custom_reasoning_options()
        endpoint_layout.addWidget(endpoint_advanced)
        layout.addWidget(endpoint_group)

        self.apple_group = QGroupBox("Apple Intelligence")
        apple_layout = QVBoxLayout(self.apple_group)
        apple_description = QLabel(
            "Le modèle Apple traite votre texte sur ce Mac, sans clé API ni serveur "
            "à configurer. Nécessite macOS 26+, un Mac Apple Silicon et Apple "
            "Intelligence activé avec son modèle téléchargé.\n\n"
            "Privilégiez les passages courts : correction, "
            "reformulation et résumé. Les textes longs peuvent dépasser la "
            "capacité du modèle."
        )
        apple_description.setWordWrap(True)
        apple_layout.addWidget(apple_description)
        self.apple_verification = VerificationStatus()
        self.apple_verification.set_status(
            "idle", "Disponibilité à vérifier",
            "Vérifiez que le modèle Apple est prêt sur ce Mac.",
        )
        self.apple_status = self.apple_verification.detail
        apple_layout.addWidget(self.apple_verification)
        self.apple_refresh = QPushButton("Vérifier la disponibilité")
        self.apple_refresh.clicked.connect(self.refresh_apple_availability)
        apple_layout.addWidget(self.apple_refresh)
        apple_settings = QPushButton("Ouvrir les réglages Apple Intelligence")
        apple_settings.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("x-apple.systempreferences:com.apple.Siri-Settings.extension")
            )
        )
        apple_layout.addWidget(apple_settings)
        layout.addWidget(self.apple_group)
        self.provider_combo.currentIndexChanged.connect(self.toggle_provider)
        QApplication.instance().aboutToQuit.connect(self._cancel_apple_probe)

        from supermenu_core.ui.shortcut_settings import ShortcutSettings
        shortcuts_group = ShortcutSettings()
        self.main_hotkey = shortcuts_group.add_shortcut("Menu principal", self.settings.get_hotkey(), self.record_main_hotkey)
        self.custom_hotkey = shortcuts_group.add_shortcut("Mode personnalisé", self.settings.get_custom_hotkey(), self.record_custom_hotkey)
        shortcuts_group.add_test(self.show_prompt_menu)
        shortcuts_page.addWidget(shortcuts_group)
        from supermenu_core.ui.dictation_settings import DictationShortcutSettings
        self.dictation_shortcut_settings = DictationShortcutSettings(self.settings, self.dictation_hotkey_manager)
        self.dictation_shortcut_settings.record_requested.connect(self.record_dictation_hotkey)
        # The field changes only once the new shortcut is registered.
        self.dictation_shortcut_settings.shortcut.textChanged.connect(
            self._retry_prompt_hotkeys
        )
        shortcuts_page.insertWidget(2, self.dictation_shortcut_settings)

        permissions_group = QGroupBox("Autorisations macOS")
        permissions_layout = QVBoxLayout(permissions_group)
        explanation = QLabel(
            "SuperMenu utilise Accessibilité pour détecter ses raccourcis "
            "globaux et exécuter Copier/Coller. Aucune autre autorisation "
            "de saisie n’est nécessaire."
        )
        explanation.setWordWrap(True)
        permissions_layout.addWidget(explanation)

        accessibility_row = QHBoxLayout()
        self.accessibility_status = QLabel()
        accessibility_row.addWidget(self.accessibility_status)
        accessibility_row.addStretch()
        self.accessibility_button = QPushButton("Configurer Accessibilité…")
        self.accessibility_button.clicked.connect(
            self.request_accessibility_permission
        )
        accessibility_row.addWidget(self.accessibility_button)
        permissions_layout.addLayout(accessibility_row)

        status_row = QHBoxLayout()
        self.hotkey_service_status = QLabel()
        self.hotkey_service_status.setWordWrap(True)
        status_row.addWidget(self.hotkey_service_status, 1)
        recheck_button = QPushButton("Revérifier")
        recheck_button.clicked.connect(
            lambda: self.refresh_permission_status(force_reload=True)
        )
        status_row.addWidget(recheck_button)
        quit_button = QPushButton("Quitter pour appliquer")
        quit_button.clicked.connect(self.quit_application)
        status_row.addWidget(quit_button)
        permissions_layout.addLayout(status_row)
        app_page.addWidget(permissions_group)

        from supermenu_core.ui.application_settings import (
            ApplicationSettings,
            FeatureModeSettings,
        )
        self.application_settings = ApplicationSettings(
            self.settings, lambda: self.check_for_updates(silent=False)
        )
        self.theme_combo = self.application_settings.theme_combo
        self.channel_combo = self.application_settings.channel_combo
        app_page.insertWidget(2, self.application_settings)
        # No screen capture on macOS: the switches describe voice only.
        self.feature_mode_settings = FeatureModeSettings(self.settings)
        self.feature_mode_settings.modes_changed.connect(self.apply_feature_modes)
        app_page.insertWidget(3, self.feature_mode_settings)
        diagnostics = Disclosure("Dossiers et diagnostic")
        for label, path in (
            ("Ouvrir le dossier de configuration", user_config_dir),
            ("Ouvrir le dossier des journaux", user_log_dir),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, path=path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path()))))
            diagnostics.content_layout.addWidget(button)
        app_page.addWidget(diagnostics)
        from supermenu_core.ui.speech_settings import SpeechSettingsWidget
        from src.audio.speech_backend import create_speech_backend

        self.speech_settings = SpeechSettingsWidget(
            self.settings, lambda options: create_speech_backend(self.settings, options),
            platform="darwin",
        )
        self.speech_settings.dictation_requested.connect(self.start_dictation)
        if self.context_menu_manager:
            self.speech_settings.settings_saved.connect(self.context_menu_manager.update_client_config)
        self.api_key.textChanged.connect(self.speech_settings.api_key_input.setText)
        self.speech_settings.api_key_input.textChanged.connect(self.api_key.setText)
        QApplication.instance().aboutToQuit.connect(lambda: self.speech_settings.cancel(silent=True))
        voice_page.addWidget(self.speech_settings)
        from supermenu_core.ui.dictation_settings import DictationBehaviorSettings
        self.dictation_behavior = DictationBehaviorSettings(self.settings)
        voice_page.addWidget(self.dictation_behavior)
        self.settings_panel.set_footer("voice", self.speech_settings.actions_widget)
        self.text_save_button = container.set_save_action("text", self.save_text_settings)
        self.app_save_button = container.set_save_action("app", self.save_application_settings, "Appliquer")
        self._refresh_reasoning_options(self.settings.get_model())
        self.toggle_provider()
        self.refresh_permission_status()
        return container

    def _refresh_reasoning_options(self, model):
        current = self.settings.get_openai_reasoning_effort(model)
        self.reasoning_combo.clear()
        self.reasoning_combo.addItems(get_reasoning_efforts_for_model(model))
        self.reasoning_combo.setCurrentText(current)

    def toggle_provider(self, *_args):
        provider = self.provider_combo.currentData()
        self.openai_group.setVisible(provider == "openai")
        self.custom_group.setVisible(provider == "custom")
        self.apple_group.setVisible(provider == "apple")
        if provider == "apple":
            self.refresh_apple_availability()
        else:
            self._cancel_apple_probe()

    def refresh_apple_availability(self, _checked=False):
        if self._apple_probe is not None:
            return
        probe = FoundationModelsRequest(self)
        self._apple_probe = probe
        self.apple_refresh.setEnabled(False)
        self.apple_refresh.setText("Vérification en cours…")
        self.apple_verification.set_status(
            "busy", "Vérification en cours…",
            "Nous vérifions la disponibilité du modèle Apple sur ce Mac.",
        )

        def complete(state, title, message):
            if self._apple_probe is not probe:
                return
            self._apple_probe = None
            self.apple_refresh.setEnabled(True)
            self.apple_refresh.setText(
                "Vérifier à nouveau" if state == "success" else "Réessayer"
            )
            self.apple_verification.set_status(
                state, title, message,
                checked_at=f"Vérifié à {datetime.now():%H:%M:%S}",
            )
            probe.deleteLater()

        probe.succeeded.connect(
            lambda _reply: complete(
                "success", "Prêt à utiliser",
                "Le modèle Apple est disponible sur ce Mac. "
                "Enregistrez la configuration pour l’utiliser.",
            )
        )
        probe.failed.connect(
            lambda message: complete("error", "Modèle Apple indisponible", message)
        )
        probe.start({"action": "availability"}, timeout_ms=15_000)

    def _cancel_apple_probe(self):
        if self._apple_probe is not None:
            probe = self._apple_probe
            self._apple_probe = None
            probe.cancel()
            probe.deleteLater()
            self.apple_verification.set_status(
                "idle", "Vérification annulée",
                "Relancez la vérification pour connaître la disponibilité du modèle.",
            )
            self.apple_refresh.setText("Vérifier la disponibilité")
        self.apple_refresh.setEnabled(True)

    def refresh_custom_models(self, _checked=False):
        if self._custom_models_worker and self._custom_models_worker.isRunning():
            return
        endpoint = self.custom_endpoint.text().strip()
        valid, message = Validators.validate_url(endpoint)
        if not valid:
            QMessageBox.warning(self, "Endpoint invalide", message)
            return
        self._custom_model_details = {}
        self._update_custom_reasoning_options()
        self._custom_models_worker = CustomModelsWorker(
            endpoint,
            self.custom_endpoint_api_key.text().strip() or None,
            self.endpoint_type.currentData(),
        )
        self._custom_models_worker.finished_ok.connect(
            self._on_custom_models_loaded
        )
        self._custom_models_worker.failed.connect(
            self._on_custom_models_failed
        )
        worker = self._custom_models_worker
        worker.finished.connect(
            lambda current=worker: self._custom_models_worker_finished(current)
        )
        worker.start()

    def _on_custom_models_loaded(self, model_details):
        worker = self._custom_models_worker
        if worker is None or (
            worker.endpoint != self.custom_endpoint.text().strip()
            or worker.endpoint_type != self.endpoint_type.currentData()
        ):
            return
        self._custom_model_details = populate_model_catalog(
            self.custom_model, model_details,
            lmstudio=self.endpoint_type.currentData() == "lmstudio",
            endpoint=self.custom_endpoint.text().strip(), settings=self.settings,
        )
        self._update_custom_reasoning_options()
        QMessageBox.information(
            self,
            "Modèles récupérés",
            f"{len(self._custom_model_details)} modèle(s) trouvé(s) sur le serveur.",
        )

    def _invalidate_custom_model_details(self, *_args):
        self._custom_model_details = {}
        clear_model_provenance(self.custom_model)
        self._update_custom_reasoning_options()

    def _get_custom_model_details(self, model):
        selected = selected_model_details(self.custom_model, self._custom_model_details)
        if selected and selected["id"] == model:
            return selected
        details = self._custom_model_details.get(model)
        if details:
            return details
        for candidate in self._custom_model_details.values():
            if model in candidate.get("identifiers", []):
                return candidate
        return None

    def _update_custom_reasoning_options(self, *_args):
        if not hasattr(self, "custom_reasoning"):
            return

        combo = self.custom_reasoning
        previous = normalize_reasoning_option(combo.currentData())
        if not previous:
            previous = normalize_reasoning_option(combo.currentText())
        preferred = previous or self.settings.get_custom_reasoning_effort()
        endpoint_type = self.endpoint_type.currentData()
        model = selected_model_id(self.custom_model)
        details = self._get_custom_model_details(model)
        self.custom_model_provenance.setText(
            selection_summary(self.custom_model, self._custom_model_details, lmstudio=endpoint_type == "lmstudio")
        )
        self.custom_model_provenance.setVisible(endpoint_type == "lmstudio")
        self.device_name_button.refresh()

        combo.blockSignals(True)
        try:
            combo.clear()
            if endpoint_type == "lmstudio" and details:
                options = details.get("reasoning_options", [])
                if details.get("reasoning_supported") is False:
                    combo.addItem("Non pris en charge", "none")
                    combo.setEnabled(False)
                    self.custom_reasoning_label.setText(
                        "Raisonnement / think (non pris en charge) :"
                    )
                    return
                if options:
                    selected = choose_reasoning_option(
                        options,
                        preferred=preferred,
                        default=details.get("reasoning_default"),
                    )
                    for option in options:
                        combo.addItem(option, option)
                    combo.setCurrentIndex(max(0, combo.findData(selected)))
                    combo.setEnabled(len(options) > 1)
                    self.custom_reasoning_label.setText(
                        "Raisonnement / think (détecté) :"
                    )
                    return

            fallback_options = list(CUSTOM_REASONING_EFFORTS)
            if preferred in {"off", "on"}:
                fallback_options = ["off", "on"]
            elif preferred and preferred not in fallback_options:
                fallback_options.append(preferred)
            for option in fallback_options:
                combo.addItem(option, option)
            selected = choose_reasoning_option(
                fallback_options,
                preferred=preferred,
            )
            combo.setCurrentIndex(max(0, combo.findData(selected)))
            combo.setEnabled(True)
            self.custom_reasoning_label.setText("Raisonnement / think :")
        finally:
            combo.blockSignals(False)

    def _on_custom_models_failed(self, message):
        worker = self._custom_models_worker
        if worker is None or (
            worker.endpoint != self.custom_endpoint.text().strip()
            or worker.endpoint_type != self.endpoint_type.currentData()
        ):
            return
        QMessageBox.warning(self, "Récupération impossible", str(message))

    def _custom_models_worker_finished(self, worker):
        if self._custom_models_worker is worker:
            self._custom_models_worker = None
        worker.deleteLater()

    def _validate_endpoint_settings(self):
        if self.provider_combo.currentData() != "custom":
            return True
        valid, message = Validators.validate_url(self.custom_endpoint.text())
        if not valid:
            QMessageBox.warning(self, "Endpoint invalide", message)
            return False
        valid, message = Validators.validate_model_name(
            selected_model_id(self.custom_model)
        )
        if not valid:
            QMessageBox.warning(self, "Modèle invalide", message)
            return False
        return True

    def save_settings(self):
        """Compatibility entry point for saving the complete configuration."""
        if self.tabs.currentWidget() is self.voice_prompt_editor:
            return self.voice_prompt_editor.save()
        if not self._validate_endpoint_settings():
            return False
        # The dictation settings are hidden without the experimental features.
        if experimental_enabled(self.settings) and not self.speech_settings.save():
            return False
        current_prompt = self.prompt_list.currentItem()
        if current_prompt is not None and not self.save_current_prompt(False):
            return False
        if not self.save_text_settings(show_confirmation=False):
            return False
        return self.save_application_settings()

    def save_text_settings(self, _checked=False, *, show_confirmation=True):
        if not self._validate_endpoint_settings():
            return False
        self.settings.set_api_key(self.api_key.text())
        model = self.model_combo.currentText()
        self.settings.set_model(model)
        self.settings.set_openai_reasoning_effort(
            self.reasoning_combo.currentText(), model
        )
        self.settings.set_ai_provider(self.provider_combo.currentData())
        self.settings.set_custom_endpoint(self.custom_endpoint.text())
        self.settings.set_custom_endpoint_api_key(
            self.custom_endpoint_api_key.text()
        )
        self.settings.set_custom_endpoint_type(self.endpoint_type.currentData())
        self.settings.set_custom_model(selected_model_id(self.custom_model))
        self.settings.set_custom_model_target(selected_model_target(self.custom_model))
        self.settings.set_custom_reasoning_effort(
            self.custom_reasoning.currentData()
            or self.custom_reasoning.currentText()
        )
        self.settings.sync()
        if self.context_menu_manager:
            self.context_menu_manager.update_client_config()
        if show_confirmation:
            QMessageBox.information(self, "Configuration enregistrée", "Le moteur de texte est prêt à utiliser.")
        return True

    def save_application_settings(self, _checked=False):
        self.settings.set_theme(self.theme_combo.currentData())
        self.settings.set_update_channel(self.channel_combo.currentData())
        # Filled by apply_feature_modes, which modes_changed calls from save().
        self._feature_mode_problems = []
        try:
            self.feature_mode_settings.save()
        except Exception as exc:
            log(f"Application des fonctions impossible : {exc}", logging.WARNING)
        self.settings.sync()
        ThemeManager.apply_theme(QApplication.instance(), self.settings.get_theme())
        problems = list(self._feature_mode_problems)
        if problems:
            QMessageBox.warning(
                self,
                "Raccourcis inactifs",
                "Les modifications sont actives, mais ces raccourcis restent "
                "inactifs :\n"
                + "\n".join(problems)
                + "\n\nChoisissez-en un autre dans Réglages > Raccourcis ou "
                "dans l’onglet Prompts.",
            )
        else:
            QMessageBox.information(self, "Réglages enregistrés", "Les modifications sont actives.")
        return True
