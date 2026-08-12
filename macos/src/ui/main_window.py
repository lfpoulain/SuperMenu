"""Configuration window for the independent macOS application."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QThread, QUrl, Qt, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
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
    QScrollArea,
    QSplitter,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.config.build_info import APP_VERSION
from src.config.openai_models import (
    AVAILABLE_MODELS,
    get_reasoning_efforts_for_model,
)
from src.config.settings import CUSTOM_REASONING_EFFORTS
from src.ui.theme_manager import ThemeManager
from src.utils import updater as app_updater
from src.utils.hotkey_manager import HotkeyRecorderDialog
from src.utils.paths import resource_path, user_config_dir, user_log_dir
from src.utils.permissions import (
    accessibility_is_trusted,
    input_monitoring_is_trusted,
    open_accessibility_settings,
    open_input_monitoring_settings,
)
from src.utils.validators import Validators


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
        self._quitting = False
        self._loading_prompt = False
        self._update_worker = None

        self.setWindowTitle("SuperMenu - Configuration")
        self.setMinimumSize(880, 680)
        self.resize(980, 760)
        self.setWindowIcon(QIcon(resource_path("resources", "icons", "icon.png")))

        root = QWidget()
        root_layout = QVBoxLayout(root)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_prompts_tab(), "Prompts")
        self.tabs.addTab(self._create_settings_tab(), "Réglages")
        self.tabs.addTab(self._create_about_tab(), "À propos")
        root_layout.addWidget(self.tabs)

        buttons = QHBoxLayout()
        buttons.addStretch()
        save_button = QPushButton("Enregistrer")
        save_button.setDefault(True)
        save_button.clicked.connect(self.save_settings)
        buttons.addWidget(save_button)
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.hide)
        buttons.addWidget(close_button)
        root_layout.addLayout(buttons)
        self.setCentralWidget(root)

    def _create_prompts_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left.setMinimumWidth(260)
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
        self.prompt_list.currentItemChanged.connect(self._load_selected_prompt)
        self.prompt_list.model().rowsMoved.connect(self._save_prompt_order)
        left_layout.addWidget(self.prompt_list)
        prompt_buttons = QHBoxLayout()
        add_button = QPushButton("Ajouter")
        add_button.clicked.connect(self.add_prompt)
        prompt_buttons.addWidget(add_button)
        delete_button = QPushButton("Supprimer")
        delete_button.clicked.connect(self.delete_prompt)
        prompt_buttons.addWidget(delete_button)
        left_layout.addLayout(prompt_buttons)
        transfer_buttons = QHBoxLayout()
        import_button = QPushButton("Importer")
        import_button.clicked.connect(self.import_prompts)
        transfer_buttons.addWidget(import_button)
        export_button = QPushButton("Exporter")
        export_button.clicked.connect(self.export_prompts)
        transfer_buttons.addWidget(export_button)
        left_layout.addLayout(transfer_buttons)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        form_group = QGroupBox("Édition du prompt")
        form = QFormLayout(form_group)
        self.prompt_name = QLineEdit()
        form.addRow("Nom affiché", self.prompt_name)
        self.prompt_instruction = QTextEdit()
        self.prompt_instruction.setMinimumHeight(180)
        form.addRow("Instruction", self.prompt_instruction)
        self.prompt_status = QLineEdit()
        form.addRow("Message d’attente", self.prompt_status)
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
        form.addRow("Raccourci direct", hotkey_row)
        right_layout.addWidget(form_group)
        save_prompt_button = QPushButton("Enregistrer le prompt")
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
        container = QWidget()
        container_layout = QVBoxLayout(container)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        api_group = QGroupBox("OpenAI")
        api_form = QFormLayout(api_group)
        self.api_key = QLineEdit(self.settings.get_api_key())
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("sk-…")
        api_form.addRow("Clé API", self.api_key)
        self.model_combo = NoWheelComboBox()
        self.model_combo.addItems(AVAILABLE_MODELS)
        self.model_combo.setCurrentText(self.settings.get_model())
        self.model_combo.currentTextChanged.connect(self._refresh_reasoning_options)
        api_form.addRow("Modèle", self.model_combo)
        self.reasoning_combo = NoWheelComboBox()
        api_form.addRow("Effort de raisonnement", self.reasoning_combo)
        layout.addWidget(api_group)

        endpoint_group = QGroupBox("Modèle local ou endpoint personnalisé")
        endpoint_form = QFormLayout(endpoint_group)
        self.use_custom_endpoint = QCheckBox("Utiliser cet endpoint")
        self.use_custom_endpoint.setChecked(self.settings.get_use_custom_endpoint())
        endpoint_form.addRow("", self.use_custom_endpoint)
        self.endpoint_type = NoWheelComboBox()
        self.endpoint_type.addItem("Ollama", "ollama")
        self.endpoint_type.addItem("LM Studio", "lmstudio")
        type_index = self.endpoint_type.findData(
            self.settings.get_custom_endpoint_type()
        )
        self.endpoint_type.setCurrentIndex(max(0, type_index))
        endpoint_form.addRow("Type", self.endpoint_type)
        self.custom_endpoint = QLineEdit(self.settings.get_custom_endpoint())
        self.custom_endpoint.setPlaceholderText("http://localhost:11434")
        endpoint_form.addRow("Adresse", self.custom_endpoint)
        self.custom_model = QLineEdit(self.settings.get_custom_model())
        endpoint_form.addRow("Modèle", self.custom_model)
        self.custom_reasoning = NoWheelComboBox()
        self.custom_reasoning.addItems(CUSTOM_REASONING_EFFORTS)
        self.custom_reasoning.setCurrentText(
            self.settings.get_custom_reasoning_effort()
        )
        endpoint_form.addRow("Effort de raisonnement", self.custom_reasoning)
        layout.addWidget(endpoint_group)

        shortcuts_group = QGroupBox("Raccourcis et autorisation")
        shortcuts_form = QFormLayout(shortcuts_group)
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
        permission_row = QHBoxLayout()
        self.permission_status = QLabel()
        permission_row.addWidget(self.permission_status)
        permission_row.addStretch()
        request_button = QPushButton("Demander")
        request_button.clicked.connect(self.request_accessibility_permission)
        permission_row.addWidget(request_button)
        open_button = QPushButton("Accessibilité…")
        open_button.clicked.connect(open_accessibility_settings)
        permission_row.addWidget(open_button)
        input_button = QPushButton("Entrée…")
        input_button.clicked.connect(open_input_monitoring_settings)
        permission_row.addWidget(input_button)
        shortcuts_form.addRow("Autorisations macOS", permission_row)
        layout.addWidget(shortcuts_group)

        general_group = QGroupBox("Interface et mises à jour")
        general_form = QFormLayout(general_group)
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
        layout.addWidget(general_group)
        layout.addStretch()

        scroll.setWidget(content)
        container_layout.addWidget(scroll)
        self._refresh_reasoning_options(self.settings.get_model())
        self.refresh_permission_status()
        return container

    def _create_about_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        title = QLabel("SuperMenu")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: 600; padding: 20px;")
        layout.addWidget(title)
        version = QLabel(f"Version {APP_VERSION} — application macOS indépendante")
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

    def add_prompt(self):
        prompt_id = self.settings.add_prompt(
            None,
            "Nouveau prompt",
            "",
            "Traitement en cours…",
            position=(self.prompt_list.count() + 1) * 10,
        )
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
        try:
            count = self.settings.import_prompts(path)
        except Exception as exc:
            QMessageBox.warning(self, "Import impossible", str(exc))
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
        dialog = HotkeyRecorderDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.prompt_hotkey.setText(dialog.recorded_hotkey)

    def _refresh_reasoning_options(self, model):
        current = self.settings.get_openai_reasoning_effort(model)
        self.reasoning_combo.clear()
        self.reasoning_combo.addItems(get_reasoning_efforts_for_model(model))
        self.reasoning_combo.setCurrentText(current)

    def record_main_hotkey(self):
        if self.hotkey_manager and self.hotkey_manager.show_hotkey_recorder(self):
            self.main_hotkey.setText(self.settings.get_hotkey())

    def record_custom_hotkey(self):
        if (
            self.custom_hotkey_manager
            and self.custom_hotkey_manager.show_hotkey_recorder(self)
        ):
            self.custom_hotkey.setText(self.settings.get_custom_hotkey())

    def request_accessibility_permission(self):
        accessibility_is_trusted(prompt=True)
        input_monitoring_is_trusted(prompt=True)
        self.refresh_permission_status()
        if accessibility_is_trusted() and input_monitoring_is_trusted():
            if self.hotkey_manager:
                self.hotkey_manager.register_hotkey()
            if self.custom_hotkey_manager:
                self.custom_hotkey_manager.register_hotkey()
            self._refresh_prompt_hotkeys()

    def refresh_permission_status(self):
        accessibility = accessibility_is_trusted()
        input_monitoring = input_monitoring_is_trusted()
        trusted = accessibility and input_monitoring
        self.permission_status.setText(
            "Accessibilité : "
            f"{'OK' if accessibility else 'à autoriser'} · Entrée : "
            f"{'OK' if input_monitoring else 'à autoriser'}"
        )
        self.permission_status.setProperty("status", "success" if trusted else "warning")
        self.permission_status.style().unpolish(self.permission_status)
        self.permission_status.style().polish(self.permission_status)

    def _validate_endpoint_settings(self):
        if not self.use_custom_endpoint.isChecked():
            return True
        valid, message = Validators.validate_url(self.custom_endpoint.text())
        if not valid:
            QMessageBox.warning(self, "Endpoint invalide", message)
            return False
        valid, message = Validators.validate_model_name(self.custom_model.text())
        if not valid:
            QMessageBox.warning(self, "Modèle invalide", message)
            return False
        return True

    def save_settings(self):
        if not self._validate_endpoint_settings():
            return False
        current_prompt = self.prompt_list.currentItem()
        if current_prompt is not None and not self.save_current_prompt(False):
            return False
        try:
            self.settings.set_api_key(self.api_key.text())
        except Exception as exc:
            QMessageBox.warning(self, "Trousseau macOS", str(exc))
            return False
        model = self.model_combo.currentText()
        self.settings.set_model(model)
        self.settings.set_openai_reasoning_effort(
            self.reasoning_combo.currentText(), model
        )
        self.settings.set_use_custom_endpoint(self.use_custom_endpoint.isChecked())
        self.settings.set_custom_endpoint(self.custom_endpoint.text())
        self.settings.set_custom_endpoint_type(self.endpoint_type.currentData())
        self.settings.set_custom_model(self.custom_model.text())
        self.settings.set_custom_reasoning_effort(
            self.custom_reasoning.currentText()
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
            self.prompt_hotkey_manager.refresh_hotkeys()

    def setup_tray_icon(self):
        if self.tray_icon is not None:
            return True
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        icon = QIcon(resource_path("resources", "icons", "icon.png"))
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("SuperMenu")
        menu = QMenu()
        open_action = QAction("Ouvrir SuperMenu", self)
        open_action.triggered.connect(self.show_main_window)
        menu.addAction(open_action)
        response_action = QAction("Afficher la dernière réponse", self)
        response_action.triggered.connect(
            lambda: self.context_menu_manager
            and self.context_menu_manager.show_response_window()
        )
        menu.addAction(response_action)
        update_action = QAction("Rechercher une mise à jour", self)
        update_action.triggered.connect(lambda: self.check_for_updates(False))
        menu.addAction(update_action)
        menu.addSeparator()
        quit_action = QAction("Quitter", self)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_activated)
        tray.show()
        self.tray_icon = tray
        return True

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_main_window()

    def show_main_window(self):
        self.refresh_permission_status()
        self.show()
        self.raise_()
        self.activateWindow()

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
                f"La version {version} est disponible. Ouvrir la page de téléchargement ?",
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

    def closeEvent(self, event):
        if self._quitting:
            event.accept()
        else:
            event.ignore()
            self.hide()
