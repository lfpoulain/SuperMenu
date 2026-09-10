"""Configuration window for the macOS application composition."""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.config.build_info import APP_VERSION
from src.api.apple_foundation_client import FoundationModelsRequest
from supermenu_core.config.openai_models import (
    AVAILABLE_MODELS,
    get_reasoning_efforts_for_model,
)
from supermenu_core.api.model_capabilities import (
    choose_reasoning_option,
    normalize_reasoning_option,
)
from supermenu_core.config.provider_settings import CUSTOM_REASONING_EFFORTS
from supermenu_core.ui.theme_manager import ThemeManager
from supermenu_core.ui.verification_status import VerificationStatus
from src.utils import updater as app_updater
from src.utils.hotkey_manager import HotkeyRecorderDialog
from src.utils.key_events import KeyEventPoster
from src.utils.paths import resource_path, user_config_dir, user_log_dir
from src.utils.logger import log
from src.utils.window_target import PasteTarget, activate_current_application
from src.utils.permissions import (
    current_permission_status,
    open_accessibility_settings,
    request_accessibility_permission,
)
from supermenu_core.utils.validators import Validators


def _create_form_layout(parent):
    """Build a form whose fields use the width available, as on Windows.

    QFormLayout reads its growth policy from the active style. QMacStyle asks
    for FieldsStayAtSizeHint, so every line edit and text area stayed at its
    minimum width with dead space beside it, while the Windows styles default
    to AllNonFixedFieldsGrow. Setting it explicitly makes both compositions
    lay out the same way.
    """
    form = QFormLayout(parent)
    form.setFieldGrowthPolicy(
        QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
    )
    return form


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class UpdateCheckWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, channel: str):
        super().__init__()
        self.channel = channel

    def run(self):
        try:
            self.finished_ok.emit(app_updater.check_latest_release(self.channel))
        except Exception as exc:
            self.failed.emit(str(exc))


class CustomModelsWorker(QThread):
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


class MainWindow(QMainWindow):
    """Edit prompts and settings while the app lives in the menu bar."""

    def __init__(
        self,
        settings,
        context_menu_manager=None,
        hotkey_manager=None,
        custom_hotkey_manager=None,
        prompt_hotkey_manager=None,
    ):
        super().__init__()
        self.settings = settings
        self.context_menu_manager = context_menu_manager
        self.hotkey_manager = hotkey_manager
        self.custom_hotkey_manager = custom_hotkey_manager
        self.prompt_hotkey_manager = prompt_hotkey_manager
        self.tray_icon = None
        self.tray_menu = None
        self._quitting = False
        self._loading_prompt = False
        self._update_worker = None
        self._custom_models_worker = None
        self._apple_probe = None
        self._custom_model_details = {}
        self._hotkey_dialog = None
        self._last_permission_state = None
        self._accessibility_request_attempted = False
        self._keys = KeyEventPoster()

        self.setWindowTitle("SuperMenu - Configuration")
        self.setMinimumSize(860, 700)
        self.resize(1000, 780)
        self.setWindowIcon(QIcon(resource_path("resources", "icons", "icon.png")))

        root = QWidget()
        root_layout = QVBoxLayout(root)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_prompts_tab(), "📝 Prompts")
        self.tabs.addTab(self._create_settings_tab(), "⚙️ Paramètres")
        self.tabs.addTab(self._create_about_tab(), "ℹ️ À propos")
        root_layout.addWidget(self.tabs)

        buttons = QHBoxLayout()
        buttons.addStretch()
        save_button = QPushButton("💾 Enregistrer")
        save_button.setDefault(True)
        save_button.clicked.connect(self.save_settings)
        buttons.addWidget(save_button)
        close_button = QPushButton("❌ Fermer")
        close_button.clicked.connect(self.hide)
        buttons.addWidget(close_button)
        root_layout.addLayout(buttons)
        self.setCentralWidget(root)

        # Only polled while the configuration window is on screen. SuperMenu
        # lives in the menu bar and is hidden most of the time; a permanent
        # 1.5 s wake-up costs battery for a panel nobody is looking at.
        self._permission_timer = QTimer(self)
        self._permission_timer.setInterval(1500)
        self._permission_timer.timeout.connect(self.refresh_permission_status)

    def _create_prompts_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(0)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left.setFixedWidth(300)
        left_layout = QVBoxLayout(left)
        self.prompt_search = QLineEdit()
        self.prompt_search.setPlaceholderText("Rechercher un prompt…")
        self.prompt_search.textChanged.connect(self._filter_prompts)
        left_layout.addWidget(self.prompt_search)
        self.prompt_list = QListWidget()
        self.prompt_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.prompt_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.prompt_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.prompt_list.setDropIndicatorShown(True)
        self.prompt_list.setSpacing(6)
        self.prompt_list.setStyleSheet(
            "QListWidget { border-radius: 6px; border: 1px solid rgba(52, 152, 219, 0.3); }"
            "QListWidget:focus { border: 2px solid #3498db; }"
            "QListWidget::item { padding: 8px; border-left: 3px solid transparent; }"
            "QListWidget::item:hover { border-left: 3px solid #64B5F6; background-color: rgba(100, 181, 246, 0.10); }"
            "QListWidget::item:selected { border-left: 3px solid #64B5F6; background-color: rgba(100, 181, 246, 0.18); }"
        )
        self.prompt_list.currentItemChanged.connect(self._load_selected_prompt)
        self.prompt_list.model().rowsMoved.connect(self._save_prompt_order)
        left_layout.addWidget(self.prompt_list)
        prompt_buttons = QHBoxLayout()
        add_button = QPushButton("➕ Ajouter")
        add_button.clicked.connect(self.add_prompt)
        prompt_buttons.addWidget(add_button)
        delete_button = QPushButton("🗑️ Supprimer")
        delete_button.clicked.connect(self.delete_prompt)
        prompt_buttons.addWidget(delete_button)
        left_layout.addLayout(prompt_buttons)
        transfer_buttons = QHBoxLayout()
        import_button = QPushButton("📥 Importer")
        import_button.clicked.connect(self.import_prompts)
        transfer_buttons.addWidget(import_button)
        export_button = QPushButton("📤 Exporter")
        export_button.clicked.connect(self.export_prompts)
        transfer_buttons.addWidget(export_button)
        left_layout.addLayout(transfer_buttons)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        form_group = QGroupBox("✏️ Éditer le prompt")
        form = _create_form_layout(form_group)
        self.prompt_name = QLineEdit()
        form.addRow("🏷️ Nom affiché :", self.prompt_name)
        self.prompt_instruction = QTextEdit()
        self.prompt_instruction.setMinimumHeight(180)
        form.addRow("📝 Prompt :", self.prompt_instruction)
        self.prompt_status = QLineEdit()
        form.addRow("⏳ Message d’attente :", self.prompt_status)
        self.prompt_direct = QCheckBox(
            "Insérer directement la réponse dans l’application cible"
        )
        form.addRow("", self.prompt_direct)
        hotkey_row = QHBoxLayout()
        self.prompt_hotkey = QLineEdit()
        self.prompt_hotkey.setReadOnly(True)
        hotkey_row.addWidget(self.prompt_hotkey)
        record_button = QPushButton("Définir")
        record_button.clicked.connect(self.record_prompt_hotkey)
        hotkey_row.addWidget(record_button)
        clear_button = QPushButton("Effacer")
        clear_button.clicked.connect(self.prompt_hotkey.clear)
        hotkey_row.addWidget(clear_button)
        form.addRow("⌨️ Raccourci direct :", hotkey_row)
        right_layout.addWidget(form_group)
        save_prompt_button = QPushButton("💾 Enregistrer le prompt")
        save_prompt_button.clicked.connect(self.save_current_prompt)
        right_layout.addWidget(save_prompt_button)
        right_layout.addStretch()

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        self._reload_prompts()
        return tab

    def _create_settings_tab(self):
        from supermenu_core.ui.settings_panel import SettingsPanel, Disclosure

        container = self.settings_panel = SettingsPanel()
        layout = container.add_page("text", "Texte", "Choisissez l’IA pour corriger, reformuler et traduire vos textes.")
        voice_page = container.add_page("voice", "Dictée", "Testez votre microphone, puis choisissez où transcrire votre voix.")
        shortcuts_page = container.add_page("shortcuts", "Raccourcis", "Accédez à SuperMenu depuis vos applications.")
        app_page = container.add_page("app", "Application", "Gérez l’apparence, les mises à jour et les autorisations du Mac.")

        layout.addWidget(QLabel("Moteur de texte"))
        self.provider_combo = NoWheelComboBox()
        self.provider_combo.addItem("OpenAI", "openai")
        self.provider_combo.addItem("Ollama / LM Studio", "custom")
        self.provider_combo.addItem("Apple Intelligence — local (bêta)", "apple")
        self.provider_combo.setCurrentIndex(
            self.provider_combo.findData(self.settings.get_ai_provider())
        )
        layout.addWidget(self.provider_combo)

        api_group = QGroupBox("OpenAI")
        api_layout = QVBoxLayout(api_group)
        self.openai_group = api_group
        api_layout.addWidget(QLabel("Clé API :"))
        self.api_key = QLineEdit(self.settings.get_api_key())
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("sk-…")
        api_layout.addWidget(self.api_key)
        api_layout.addWidget(QLabel("Modèle :"))
        self.model_combo = NoWheelComboBox()
        self.model_combo.addItems(AVAILABLE_MODELS)
        self.model_combo.setCurrentText(self.settings.get_model())
        self.model_combo.currentTextChanged.connect(self._refresh_reasoning_options)
        api_layout.addWidget(self.model_combo)
        openai_advanced = Disclosure()
        openai_advanced.content_layout.addWidget(QLabel("Raisonnement"))
        self.reasoning_combo = NoWheelComboBox()
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
        endpoint_options.addWidget(QLabel("Type d’endpoint :"))
        self.endpoint_type = NoWheelComboBox()
        self.endpoint_type.addItem("Ollama", "ollama")
        self.endpoint_type.addItem("LM Studio", "lmstudio")
        type_index = self.endpoint_type.findData(
            self.settings.get_custom_endpoint_type()
        )
        self.endpoint_type.setCurrentIndex(max(0, type_index))
        endpoint_options.addWidget(self.endpoint_type)
        endpoint_layout.addWidget(QLabel("Modèle :"))
        custom_model_row = QHBoxLayout()
        self.custom_model = NoWheelComboBox()
        self.custom_model.setEditable(True)
        self.custom_model.setPlaceholderText("Sélectionnez ou entrez un modèle")
        saved_custom_model = self.settings.get_custom_model()
        if saved_custom_model:
            self.custom_model.addItem(saved_custom_model)
            self.custom_model.setCurrentText(saved_custom_model)
        custom_model_row.addWidget(self.custom_model, 1)
        refresh_models = QPushButton("Actualiser")
        refresh_models.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_models.clicked.connect(self.refresh_custom_models)
        custom_model_row.addWidget(refresh_models)
        endpoint_layout.addLayout(custom_model_row)
        self.custom_reasoning_label = QLabel("Raisonnement / think :")
        endpoint_options.addWidget(self.custom_reasoning_label)
        self.custom_reasoning = NoWheelComboBox()
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
            "Pour cette bêta, privilégiez les passages courts : correction, "
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

        shortcuts_group = QGroupBox("⌨️ Raccourcis clavier")
        shortcuts_form = _create_form_layout(shortcuts_group)
        main_row = QHBoxLayout()
        self.main_hotkey = QLineEdit(self.settings.get_hotkey())
        self.main_hotkey.setReadOnly(True)
        main_row.addWidget(self.main_hotkey)
        main_record = QPushButton("Définir")
        main_record.clicked.connect(self.record_main_hotkey)
        main_row.addWidget(main_record)
        shortcuts_form.addRow("Menu principal", main_row)
        custom_row = QHBoxLayout()
        self.custom_hotkey = QLineEdit(self.settings.get_custom_hotkey())
        self.custom_hotkey.setReadOnly(True)
        custom_row.addWidget(self.custom_hotkey)
        custom_record = QPushButton("Définir")
        custom_record.clicked.connect(self.record_custom_hotkey)
        custom_row.addWidget(custom_record)
        shortcuts_form.addRow("Mode personnalisé", custom_row)
        test_menu_button = QPushButton("Afficher le menu des prompts")
        test_menu_button.clicked.connect(self.show_prompt_menu)
        shortcuts_form.addRow("Test sans raccourci", test_menu_button)
        shortcuts_page.addWidget(shortcuts_group)

        permissions_group = QGroupBox("🔐 Autorisations macOS")
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
        recheck_button = QPushButton("🔄 Revérifier")
        recheck_button.clicked.connect(
            lambda: self.refresh_permission_status(force_reload=True)
        )
        status_row.addWidget(recheck_button)
        quit_button = QPushButton("Quitter pour appliquer")
        quit_button.clicked.connect(self.quit_application)
        status_row.addWidget(quit_button)
        permissions_layout.addLayout(status_row)
        app_page.addWidget(permissions_group)

        general_group = QGroupBox("🎨 Interface et mises à jour")
        general_form = _create_form_layout(general_group)
        self.theme_combo = NoWheelComboBox()
        for key, label in ThemeManager.get_theme_names().items():
            self.theme_combo.addItem(label, key)
        theme_index = self.theme_combo.findData(self.settings.get_theme())
        self.theme_combo.setCurrentIndex(max(0, theme_index))
        general_form.addRow("Thème", self.theme_combo)
        self.channel_combo = NoWheelComboBox()
        self.channel_combo.addItem("Stable", "stable")
        self.channel_combo.addItem("Bêta", "beta")
        channel_index = self.channel_combo.findData(
            self.settings.get_update_channel()
        )
        self.channel_combo.setCurrentIndex(max(0, channel_index))
        general_form.addRow("Canal de mise à jour", self.channel_combo)
        app_page.insertWidget(2, general_group)
        from supermenu_core.ui.speech_settings import SpeechSettingsWidget
        from src.audio.speech_backend import create_speech_backend

        self.speech_settings = SpeechSettingsWidget(
            self.settings, lambda options: create_speech_backend(self.settings, options),
            platform="darwin",
        )
        self.speech_settings.dictation_requested.connect(self.start_dictation)
        self.api_key.textChanged.connect(self.speech_settings.api_key_input.setText)
        self.speech_settings.api_key_input.textChanged.connect(self.api_key.setText)
        QApplication.instance().aboutToQuit.connect(lambda: self.speech_settings.cancel(silent=True))
        self.speech_settings.save_button.hide()
        voice_page.addWidget(self.speech_settings)
        self.settings_panel.set_footer("voice", self.speech_settings.actions_widget)
        self._refresh_reasoning_options(self.settings.get_model())
        self.toggle_provider()
        self.refresh_permission_status()
        return container

    def _create_about_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        title = QLabel("SuperMenu")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: 600; padding: 20px;")
        layout.addWidget(title)
        version = QLabel(f"Version {APP_VERSION} — composition macOS")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)
        layout.addSpacing(20)
        check_button = QPushButton("Rechercher une mise à jour")
        check_button.clicked.connect(lambda: self.check_for_updates(silent=False))
        layout.addWidget(check_button)
        config_button = QPushButton("Ouvrir le dossier de configuration")
        config_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(user_config_dir())))
        )
        layout.addWidget(config_button)
        logs_button = QPushButton("Ouvrir le dossier des journaux")
        logs_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(user_log_dir())))
        )
        layout.addWidget(logs_button)
        releases_button = QPushButton("Voir les versions publiées")
        releases_button.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl(app_updater.REPOSITORY_RELEASES_URL)
            )
        )
        layout.addWidget(releases_button)
        layout.addStretch()
        return tab

    def _ordered_prompts(self):
        return sorted(
            self.settings.get_prompts().items(),
            key=lambda item: (item[1].get("position", 999), item[0]),
        )

    def _reload_prompts(self, selected_id=None):
        current = selected_id
        if current is None and self.prompt_list.currentItem() is not None:
            current = self.prompt_list.currentItem().data(Qt.ItemDataRole.UserRole)
        self.prompt_list.clear()
        selected_item = None
        for prompt_id, prompt in self._ordered_prompts():
            item = QListWidgetItem(prompt.get("name") or prompt_id)
            item.setData(Qt.ItemDataRole.UserRole, prompt_id)
            self.prompt_list.addItem(item)
            if prompt_id == current:
                selected_item = item
        self._filter_prompts(self.prompt_search.text())
        if selected_item is not None:
            self.prompt_list.setCurrentItem(selected_item)
        elif self.prompt_list.count():
            self.prompt_list.setCurrentRow(0)

    def _filter_prompts(self, text):
        query = str(text or "").strip().casefold()
        for index in range(self.prompt_list.count()):
            item = self.prompt_list.item(index)
            item.setHidden(query not in item.text().casefold())

    def _load_selected_prompt(self, current, _previous=None):
        if current is None:
            return
        prompt_id = current.data(Qt.ItemDataRole.UserRole)
        prompt = self.settings.get_prompt(prompt_id)
        if prompt is None:
            return
        self._loading_prompt = True
        self.prompt_name.setText(prompt.get("name", ""))
        self.prompt_instruction.setPlainText(prompt.get("prompt", ""))
        self.prompt_status.setText(prompt.get("status", ""))
        self.prompt_direct.setChecked(bool(prompt.get("insert_directly", False)))
        self.prompt_hotkey.setText(prompt.get("hotkey", ""))
        self._loading_prompt = False

    def _save_prompt_order(self, *_args):
        prompts = self.settings.get_prompts()
        for index in range(self.prompt_list.count()):
            prompt_id = self.prompt_list.item(index).data(Qt.ItemDataRole.UserRole)
            if prompt_id in prompts:
                prompts[prompt_id]["position"] = (index + 1) * 10
        self.settings.set_prompts(prompts)
        self.settings.sync()

    def add_prompt(self):
        prompt_id = self.settings.add_prompt(
            None,
            "Nouveau prompt",
            "",
            "Traitement en cours…",
            position=(self.prompt_list.count() + 1) * 10,
        )
        self.settings.sync()
        self._reload_prompts(prompt_id)
        self.prompt_name.selectAll()
        self.prompt_name.setFocus()

    def delete_prompt(self):
        item = self.prompt_list.currentItem()
        if item is None:
            return
        if QMessageBox.question(
            self,
            "Supprimer le prompt",
            f"Supprimer « {item.text()} » ?",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.settings.delete_prompt(item.data(Qt.ItemDataRole.UserRole))
        self.settings.sync()
        self._reload_prompts()
        self._refresh_prompt_hotkeys()

    def import_prompts(self):
        from PySide6.QtWidgets import QFileDialog

        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Importer des prompts",
            "",
            "Fichiers JSON (*.json)",
        )
        if not path:
            return
        previous_prompts = self.settings.get_prompts()
        try:
            count = self.settings.import_prompts(path)
        except Exception as exc:
            QMessageBox.warning(self, "Import impossible", str(exc))
            return
        if self.prompt_hotkey_manager is not None:
            valid, errors = self.prompt_hotkey_manager.validate_prompts(
                self.settings.get_prompts()
            )
            if not valid:
                self.settings.set_prompts(previous_prompts)
                self.settings.sync()
                message = next(iter(errors.values()), "Conflit de raccourci")
                QMessageBox.warning(self, "Import impossible", message)
                return
        self._reload_prompts()
        self._refresh_prompt_hotkeys()
        QMessageBox.information(
            self,
            "Import terminé",
            f"{count} prompt(s) importé(s).",
        )

    def export_prompts(self):
        from PySide6.QtWidgets import QFileDialog

        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exporter les prompts",
            "SuperMenu-prompts.json",
            "Fichiers JSON (*.json)",
        )
        if not path:
            return
        if not path.casefold().endswith(".json"):
            path += ".json"
        try:
            self.settings.export_prompts(path)
        except Exception as exc:
            QMessageBox.warning(self, "Export impossible", str(exc))
            return
        QMessageBox.information(self, "Export terminé", "Les prompts ont été exportés.")

    def save_current_prompt(self, show_confirmation=True):
        item = self.prompt_list.currentItem()
        if item is None:
            return False
        name = self.prompt_name.text().strip()
        instruction = self.prompt_instruction.toPlainText().strip()
        if not name or not instruction:
            QMessageBox.warning(
                self,
                "Prompt incomplet",
                "Le nom et l’instruction sont obligatoires.",
            )
            return False
        prompt_id = item.data(Qt.ItemDataRole.UserRole)
        prompt = self.settings.get_prompt(prompt_id) or {}
        candidate_prompts = self.settings.get_prompts()
        candidate_prompts[prompt_id] = {
            "name": name,
            "prompt": instruction,
            "status": self.prompt_status.text().strip()
            or "Traitement en cours…",
            "insert_directly": self.prompt_direct.isChecked(),
            "position": prompt.get("position", 999),
            "hotkey": self.prompt_hotkey.text().strip(),
        }
        if self.prompt_hotkey_manager is not None:
            valid, errors = self.prompt_hotkey_manager.validate_prompts(
                candidate_prompts
            )
            if not valid:
                message = next(iter(errors.values()), "Conflit de raccourci")
                QMessageBox.warning(self, "Raccourci invalide", message)
                return False
        try:
            self.settings.update_prompt(
                prompt_id,
                name,
                instruction,
                self.prompt_status.text().strip() or "Traitement en cours…",
                self.prompt_direct.isChecked(),
                position=prompt.get("position", 999),
                hotkey=self.prompt_hotkey.text().strip(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Raccourci invalide", str(exc))
            return False
        self.settings.sync()
        self._reload_prompts(prompt_id)
        self._refresh_prompt_hotkeys()
        if show_confirmation:
            QMessageBox.information(self, "Prompt enregistré", "Le prompt a été enregistré.")
        return True

    def record_prompt_hotkey(self):
        self._open_hotkey_recorder(self.prompt_hotkey.setText)

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
        self._custom_model_details = {
            str(details["id"]): details
            for details in model_details
            if isinstance(details, dict) and details.get("id")
        }
        models = list(self._custom_model_details)
        current = self.custom_model.currentText().strip()
        self.custom_model.clear()
        self.custom_model.addItems(models)
        if current:
            self.custom_model.setCurrentText(current)
        elif models:
            self.custom_model.setCurrentIndex(0)
        self._update_custom_reasoning_options()
        QMessageBox.information(
            self,
            "Modèles récupérés",
            f"{len(models)} modèle(s) trouvé(s) sur le serveur.",
        )

    def _invalidate_custom_model_details(self, *_args):
        self._custom_model_details = {}
        self._update_custom_reasoning_options()

    def _get_custom_model_details(self, model):
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
        model = self.custom_model.currentText().strip()
        details = self._get_custom_model_details(model)

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

    def record_main_hotkey(self):
        if self.hotkey_manager:
            self._open_hotkey_recorder(
                lambda hotkey: self._apply_recorded_hotkey(
                    self.hotkey_manager,
                    self.main_hotkey,
                    hotkey,
                )
            )

    def record_custom_hotkey(self):
        if self.custom_hotkey_manager:
            self._open_hotkey_recorder(
                lambda hotkey: self._apply_recorded_hotkey(
                    self.custom_hotkey_manager,
                    self.custom_hotkey,
                    hotkey,
                )
            )

    def _open_hotkey_recorder(self, on_recorded):
        if self._hotkey_dialog is not None:
            self._hotkey_dialog.raise_()
            self._hotkey_dialog.activateWindow()
            return
        service = None
        for manager in (
            self.hotkey_manager,
            self.custom_hotkey_manager,
            self.prompt_hotkey_manager,
        ):
            if manager is not None:
                service = manager.service
                break
        if service is not None:
            service.suspend()
        dialog = HotkeyRecorderDialog(self)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._hotkey_dialog = dialog

        def finish_recording(result):
            recorded = dialog.recorded_hotkey
            self._hotkey_dialog = None
            if (
                result == HotkeyRecorderDialog.DialogCode.Accepted
                and recorded
            ):
                on_recorded(recorded)
            dialog.deleteLater()
            if service is not None:
                # Listening again while the just-recorded combination is still
                # held would fire it immediately. The condition is the user's
                # fingers, not a delay: wait for the modifiers to come up, and
                # resume at once when nothing is held.
                self._keys.when_modifiers_released(
                    QTimer.singleShot,
                    service.resume,
                )

        dialog.finished.connect(finish_recording)
        dialog.open()

    def _apply_recorded_hotkey(self, manager, field, hotkey):
        if manager.set_hotkey(hotkey):
            field.setText(hotkey)
            self.settings.sync()
            return
        QMessageBox.warning(
            self,
            "Raccourci non enregistré",
            manager.last_register_error,
        )

    def request_accessibility_permission(self):
        """Show native consent first; reveal Settings only on a later attempt."""
        if self._accessibility_request_attempted:
            open_accessibility_settings()
        else:
            self._accessibility_request_attempted = True
            if not request_accessibility_permission():
                open_accessibility_settings()
        self.accessibility_button.setText("Ouvrir les réglages…")
        QTimer.singleShot(
            800,
            lambda: self.refresh_permission_status(force_reload=True),
        )

    @staticmethod
    def _set_status_label(label, text, granted):
        label.setText(text)
        label.setProperty("status", "success" if granted else "warning")
        label.style().unpolish(label)
        label.style().polish(label)

    def _reload_all_hotkeys(self):
        results = []
        for manager in (self.hotkey_manager, self.custom_hotkey_manager):
            if manager is not None:
                results.append(manager.register_hotkey())
        if self.prompt_hotkey_manager is not None:
            prompt_ok, _errors = self.prompt_hotkey_manager.refresh_hotkeys()
            results.append(prompt_ok)
        return all(results) if results else True

    def refresh_permission_status(self, force_reload=False):
        status = current_permission_status()
        state = status.accessibility

        accessibility_text = (
            "✅ Accessibilité autorisée"
            if status.accessibility
            else "⚠️ Accessibilité manquante"
        )
        if not status.accessibility_check_available:
            accessibility_text = "⚠️ État Accessibilité non lisible"
        self._set_status_label(
            self.accessibility_status,
            accessibility_text,
            status.accessibility,
        )
        self.accessibility_button.setEnabled(not status.accessibility)
        if status.accessibility:
            self.accessibility_button.setText("Accessibilité configurée")
        elif self._accessibility_request_attempted:
            self.accessibility_button.setText("Ouvrir les réglages…")
        else:
            self.accessibility_button.setText("Configurer Accessibilité…")

        permissions_changed = (
            self._last_permission_state is not None
            and state != self._last_permission_state
        )
        permission_granted_now = (
            self._last_permission_state is False and state is True
        )
        services = {
            manager.service
            for manager in (
                self.hotkey_manager,
                self.custom_hotkey_manager,
                self.prompt_hotkey_manager,
            )
            if manager is not None and hasattr(manager, "service")
        }
        service_needs_recovery = status.all_granted and any(
            not service.running for service in services
        )
        should_reload = (
            force_reload or permissions_changed or service_needs_recovery
        )
        hotkeys_ok = True
        if permission_granted_now:
            restart_results = [service.restart() for service in services]
            hotkeys_ok = all(restart_results) if restart_results else True
        if should_reload:
            hotkeys_ok = self._reload_all_hotkeys() and hotkeys_ok

        hotkey_managers = [
            manager
            for manager in (self.hotkey_manager, self.custom_hotkey_manager)
            if manager is not None
        ]
        listeners_registered = bool(hotkey_managers) and all(
            manager.registered for manager in hotkey_managers
        )
        prompt_errors = (
            getattr(self.prompt_hotkey_manager, "errors", {})
            if self.prompt_hotkey_manager is not None
            else {}
        )
        if listeners_registered and hotkeys_ok and not prompt_errors:
            message = "✅ Raccourcis globaux actifs"
            if not status.all_granted:
                message += (
                    " — la lecture de l’état macOS reste incomplète ; "
                    "vérifie Accessibilité avant le premier copier-coller."
                )
            granted = True
        elif not status.all_granted:
            missing = " et ".join(status.missing_labels)
            message = (
                f"⚠️ Raccourcis inactifs : autorise {missing}. "
                "Si SuperMenu n’apparaît pas, ajoute SuperMenu.app avec le bouton +."
            )
            granted = False
        else:
            errors = [
                manager.last_register_error
                for manager in (self.hotkey_manager, self.custom_hotkey_manager)
                if manager is not None and manager.last_register_error
            ]
            errors.extend(str(error) for error in prompt_errors.values() if error)
            detail = errors[0] if errors else "redémarrage requis"
            message = (
                "⚠️ Autorisations accordées, mais les raccourcis ne sont "
                f"pas encore actifs ({detail}). Quitte puis relance SuperMenu."
            )
            granted = False
        self._set_status_label(
            self.hotkey_service_status,
            message,
            granted,
        )
        self._last_permission_state = state
        return status

    def _validate_endpoint_settings(self):
        if self.provider_combo.currentData() != "custom":
            return True
        valid, message = Validators.validate_url(self.custom_endpoint.text())
        if not valid:
            QMessageBox.warning(self, "Endpoint invalide", message)
            return False
        valid, message = Validators.validate_model_name(
            self.custom_model.currentText()
        )
        if not valid:
            QMessageBox.warning(self, "Modèle invalide", message)
            return False
        return True

    def save_settings(self):
        if not self._validate_endpoint_settings():
            return False
        if not self.speech_settings.save():
            return False
        current_prompt = self.prompt_list.currentItem()
        if current_prompt is not None and not self.save_current_prompt(False):
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
        self.settings.set_custom_model(self.custom_model.currentText())
        self.settings.set_custom_reasoning_effort(
            self.custom_reasoning.currentData()
            or self.custom_reasoning.currentText()
        )
        self.settings.set_theme(self.theme_combo.currentData())
        self.settings.set_update_channel(self.channel_combo.currentData())
        self.settings.sync()
        if self.context_menu_manager:
            self.context_menu_manager.update_client_config()
        ThemeManager.apply_theme(QApplication.instance(), self.settings.get_theme())
        QMessageBox.information(self, "Réglages enregistrés", "Les modifications sont actives.")
        return True

    def _refresh_prompt_hotkeys(self):
        if self.prompt_hotkey_manager:
            success, errors = self.prompt_hotkey_manager.refresh_hotkeys()
            if not success:
                log(f"Raccourcis de prompts invalides : {errors}")
            return success, errors
        return True, {}

    def setup_tray_icon(self):
        if self.tray_icon is not None:
            return True
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        icon = QIcon(resource_path("resources", "icons", "icon.png"))
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("SuperMenu")
        menu = QMenu(self)
        open_action = QAction("Ouvrir SuperMenu", self)
        open_action.triggered.connect(self.show_main_window)
        menu.addAction(open_action)
        prompt_menu_action = QAction("Afficher le menu des prompts", self)
        prompt_menu_action.triggered.connect(self.show_prompt_menu)
        menu.addAction(prompt_menu_action)
        dictation_action = QAction("Dicter du texte…", self)
        dictation_action.triggered.connect(self.start_dictation)
        menu.addAction(dictation_action)
        response_action = QAction("Afficher la dernière réponse", self)
        response_action.triggered.connect(
            lambda: self.context_menu_manager
            and self.context_menu_manager.show_response_window()
        )
        menu.addAction(response_action)
        update_action = QAction("Rechercher une mise à jour", self)
        update_action.triggered.connect(lambda: self.check_for_updates(False))
        menu.addAction(update_action)
        permission_action = QAction("Autorisations macOS…", self)
        permission_action.triggered.connect(self.show_permission_setup)
        menu.addAction(permission_action)
        menu.addSeparator()
        quit_action = QAction("Quitter", self)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_activated)
        tray.show()
        self.tray_icon = tray
        self.tray_menu = menu
        return True

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # On macOS, clicking a status item already opens the QMenu assigned
            # with setContextMenu(). Showing the configuration window here as
            # well makes both interfaces appear for the same click.
            log("Clic sur l’icône de barre des menus : menu natif affiché")

    def show_main_window(self):
        # Record where the user came from before SuperMenu takes the
        # foreground, so "Afficher le menu des prompts" still has a target.
        PasteTarget.remember_frontmost()
        activate_current_application()
        self.refresh_permission_status()
        self.show()
        self.raise_()
        self.activateWindow()

    def start_dictation(self):
        if self.context_menu_manager:
            self.context_menu_manager.start_dictation(from_ui=True)

    def show_prompt_menu(self):
        """Open the prompt menu from Qt, independently of global hotkeys."""
        if self.context_menu_manager is None:
            log("Test du menu impossible : gestionnaire indisponible")
            return
        log("Ouverture manuelle du menu des prompts")
        self.context_menu_manager.show_menu(from_ui=True)

    def show_permission_setup(self):
        self.tabs.setCurrentIndex(1)
        self.settings_panel.select_page("app")
        self.show_main_window()

    def schedule_startup_update_check(self):
        today = date.today().isoformat()
        if self.settings.get_last_update_check_date() != today:
            self.check_for_updates(silent=True)

    def check_for_updates(self, silent=False):
        if self._update_worker is not None and self._update_worker.isRunning():
            return
        worker = UpdateCheckWorker(self.settings.get_update_channel())
        self._update_worker = worker
        worker.finished_ok.connect(
            lambda release: self._update_finished(release, silent)
        )
        worker.failed.connect(lambda error: self._update_failed(error, silent))
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda: setattr(self, "_update_worker", None))
        worker.start()

    def _update_finished(self, release, silent):
        self.settings.set_last_update_check_date(date.today().isoformat())
        self.settings.sync()
        version = release.get("version", "")
        if app_updater.is_newer_version(APP_VERSION, version):
            if QMessageBox.question(
                self,
                "Mise à jour disponible",
                f"La version {version} est disponible. Télécharger le DMG ?",
            ) == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(release.get("url", "")))
        elif not silent:
            QMessageBox.information(
                self,
                "SuperMenu à jour",
                "Aucune version plus récente n’est disponible.",
            )

    def _update_failed(self, error, silent):
        if not silent:
            QMessageBox.warning(self, "Mise à jour", error)

    def quit_application(self):
        self._quitting = True
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()

    def showEvent(self, event):
        super().showEvent(event)
        self._permission_timer.start()

    def hideEvent(self, event):
        self._permission_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._permission_timer.stop()
        if self._quitting:
            self._cancel_apple_probe()
            event.accept()
        else:
            event.ignore()
            self.hide()
