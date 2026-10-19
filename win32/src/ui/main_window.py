#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import sys
import tempfile
import ctypes
import threading
from datetime import date
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton,
    QGroupBox,
    QMessageBox, QSystemTrayIcon, QApplication, QDialog,
    QStyle, QInputDialog, QFileDialog, QListWidgetItem, QAbstractItemView, QSplitter
)
from PySide6.QtCore import Qt, Signal, QTimer, QObject
from PySide6.QtGui import QIcon, QAction
from supermenu_core.ui.prompt_restore import restore_library, restore_previous_library
from supermenu_core.ui.controls import ChoiceBox, Menu, SidebarList, SIDEBAR_WIDTH

from src.config.build_info import APP_VERSION
from supermenu_core.config.openai_models import (
    AVAILABLE_MODELS,
    get_reasoning_efforts_for_model,
    normalize_reasoning_effort,
)
from src.config.settings import CUSTOM_REASONING_EFFORTS
from supermenu_core.api.model_capabilities import (
    choose_reasoning_option,
    normalize_reasoning_option,
)
from supermenu_core.ui.model_catalog import (
    selected_model_id, populate_model_catalog, selection_summary, clear_model_provenance,
    configure_model_combo, selected_model_target, selected_model_details, restore_model_target, DeviceNameButton,
)
from supermenu_core.utils.validators import Validators
from supermenu_core.config.feature_modes import (
    advanced_enabled,
    effective_speech_idle_seconds,
    effective_text_idle_seconds,
    experimental_enabled,
)
from src.utils import updater as app_updater
from supermenu_core.ui.loading_indicator import SimpleLoadingIndicator
from supermenu_core.ui.settings_panel import scrollable_form
from supermenu_core.ui.voice_prompt_editor import VoicePromptEditor
from src.utils.hotkey_manager import HotkeyRecorderDialog
from src.utils.paths import resource_path


# ShellExecuteW returns this code when Windows refuses to start the file
# (UAC prompt declined, policy block): nothing was launched.
_SE_ERR_ACCESSDENIED = 5


def _running_app_version(installed_version):
    """Version compared with the release: the running build when it is known.

    The portable executable has no Inno registry entry, and the registry may
    describe another copy than the one running. Source runs ("dev") keep the
    installed version.
    """
    if APP_VERSION and APP_VERSION != "dev":
        return APP_VERSION
    return installed_version


def _installed_app_locations(app_id_guid):
    """Folders where the Inno installer put SuperMenu, read from Uninstall."""
    try:
        import winreg
    except Exception:
        return []

    uninstall_subkey = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{{{app_id_guid}}}_is1"
    locations = []
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view_flag in (
            getattr(winreg, "KEY_WOW64_64KEY", 0),
            getattr(winreg, "KEY_WOW64_32KEY", 0),
        ):
            try:
                with winreg.OpenKey(root, uninstall_subkey, 0, winreg.KEY_READ | view_flag) as key:
                    for value_name in ("InstallLocation", "Inno Setup: App Path"):
                        try:
                            value, _ = winreg.QueryValueEx(key, value_name)
                        except OSError:
                            continue
                        if isinstance(value, str) and value.strip():
                            locations.append(value.strip())
            except OSError:
                continue
    return locations


def _comparable_path(path):
    try:
        path = os.path.realpath(path)
    except (OSError, ValueError):
        path = os.path.abspath(path)
    return os.path.normcase(os.path.normpath(path)).rstrip("\\/")


def _is_portable_build(app_id_guid, executable=None, frozen=None):
    """True for the portable executable: a packaged build outside {app}.

    The installer cannot update that file, it only adds a second copy under
    Program Files. Source runs are never portable.
    """
    if frozen is None:
        frozen = getattr(sys, "frozen", False)
    if not frozen:
        return False
    running_folder = _comparable_path(os.path.dirname(executable or sys.executable))
    return all(
        _comparable_path(location) != running_folder
        for location in _installed_app_locations(app_id_guid)
    )


# Same prefix as the private folder of updater.download_verified_installer.
_UPDATE_FOLDER_PREFIX = "SuperMenu_update_"


def _remove_update_folder(installer_path):
    """Delete the private folder of a downloaded installer that will not run.

    Each download gets a new folder of about 100 MB: one declined or refused
    at launch would otherwise stay in %TEMP%.
    """
    if not installer_path:
        return
    folder = os.path.dirname(os.path.abspath(installer_path))
    temp_dir = os.path.abspath(tempfile.gettempdir())
    if os.path.basename(folder).startswith(_UPDATE_FOLDER_PREFIX) and (
        os.path.normcase(os.path.dirname(folder)) == os.path.normcase(temp_dir)
    ):
        shutil.rmtree(folder, ignore_errors=True)


def _process_is_elevated():
    """True when SuperMenu itself runs with an administrator token."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _open_through_user_shell(path, cwd):
    """Start a file through the user's Explorer, with its standard token.

    An elevated process passes its token to what it starts: the Inno loader
    would skip the UAC prompt and relaunch SuperMenu as administrator again.
    Returns False when Explorer cannot be used.
    """
    # Explorer reads commas as argument separators.
    if "," in path:
        return False
    windows_folder = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows"
    try:
        subprocess.Popen([os.path.join(windows_folder, "explorer.exe"), path], cwd=cwd)
    except OSError:
        return False
    return True


def _log_warning(message):
    import logging
    from src.utils.logger import log
    log(message, logging.WARNING)


def _hotkey_error(manager):
    """Registration error of a shortcut Windows refused, "" when it is active."""
    if manager is None:
        return ""
    error = getattr(manager, "last_error", "")
    if error and not getattr(manager, "registered", False):
        return error
    return ""


class _BackgroundWorker(QObject):
    """Run one blocking request on a daemon thread and report through signals.

    A QThread still running when Python destroys it aborts the whole process
    ("QThread: Destroyed while thread is still running"): quitting during the
    startup update check, a download or a model refresh was enough. A daemon
    thread is simply abandoned at exit instead, as CatalogWorker already does.
    The QThread-like start, isRunning and finished surface is kept for callers.
    """

    finished = Signal()

    def __init__(self):
        super().__init__()
        self._thread = None

    def isRunning(self):
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self.run()
        except RuntimeError:
            # The window owning this worker was destroyed during exit.
            pass
        finally:
            try:
                self.finished.emit()
            except RuntimeError:
                pass

    def run(self):
        raise NotImplementedError


class _UpdateCheckWorker(_BackgroundWorker):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, owner: str, repo: str, channel: str, app_id_guid: str):
        super().__init__()
        self.owner = owner
        self.repo = repo
        self.channel = app_updater.normalize_update_channel(channel)
        self.app_id_guid = app_id_guid

    def run(self):
        try:
            release = app_updater.get_release_for_update_channel(
                self.owner,
                self.repo,
                self.channel,
            )
            latest_version = app_updater.extract_version_from_release(release)
            asset_name = app_updater.installer_asset_name(self.channel)
            asset_url = app_updater.find_asset_download_url(
                release,
                asset_name,
            )
            asset_sha256 = app_updater.find_asset_sha256(release, asset_name)
            installed_version = app_updater.get_installed_app_version(self.app_id_guid)
            portable = _is_portable_build(self.app_id_guid)

            self.finished_ok.emit(
                {
                    "channel": self.channel,
                    "installed_version": installed_version,
                    "portable": portable,
                    "latest_version": latest_version,
                    "asset_name": asset_name,
                    "asset_url": asset_url,
                    "asset_sha256": asset_sha256,
                    "release_url": release.get("html_url"),
                }
            )
        except Exception as e:
            self.failed.emit(f"Canal {self.channel} : {e}")


class _UpdateDownloadWorker(_BackgroundWorker):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, file_name: str, expected_sha256: str | None = None):
        super().__init__()
        self.url = url
        self.file_name = file_name
        self.expected_sha256 = expected_sha256

    def run(self):
        try:
            # Private mkdtemp folder, checked against the published SHA-256.
            installer_path = app_updater.download_verified_installer(
                self.url,
                self.file_name,
                self.expected_sha256,
            )
            self.finished_ok.emit(installer_path)
        except Exception as e:
            self.failed.emit(str(e))


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


class MainWindow(QMainWindow):
    """Main application window for settings and configuration"""

    def __init__(
        self,
        settings,
        context_menu_manager=None,
        hotkey_manager=None,
        voice_hotkey_manager=None,
        screenshot_hotkey_manager=None,
        custom_hotkey_manager=None,
        prompt_hotkey_manager=None,
        dictation_hotkey_manager=None,
    ):
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
        self.prompt_hotkey_manager = prompt_hotkey_manager
        self.dictation_hotkey_manager = dictation_hotkey_manager
        
        self._update_check_worker = None
        self._update_download_worker = None
        self._update_expected_sha256 = None
        self._update_loading = None
        self._update_check_silent = False
        self._custom_models_worker = None
        self._custom_models_progress = None
        self._custom_models_silent = False
        self._custom_model_details = {}
        self._custom_models_refresh_timer = QTimer(self)
        self._custom_models_refresh_timer.setSingleShot(True)
        self._custom_models_refresh_timer.setInterval(400)
        self._custom_models_refresh_timer.timeout.connect(
            lambda: self.refresh_custom_models(silent=True)
        )

        from supermenu_core.ui.configuration_shell import ConfigurationShell

        self.shell = ConfigurationShell(
            self, QIcon(resource_path("resources", "icons", "icon.png"))
        )
        self.central_widget = self.shell
        self.main_layout = self.shell.content_layout
        self.tab_widget = self.shell.tabs

        # Create tabs
        self.create_prompts_tab()
        self.create_voice_prompts_tab()
        self.create_settings_tab()
        self.create_about_tab()
        
        # Create bottom buttons
        self.create_bottom_buttons()

        # Advanced and experimental features: shown only when switched on.
        # The managers gate their own shortcuts when they register.
        self._feature_mode_problems = []
        self._applied_feature_modes = self._current_feature_modes()
        self._apply_feature_visibility()

    def create_prompts_tab(self):
        """Create the prompts settings tab"""
        prompts_tab = QWidget()
        layout = QVBoxLayout(prompts_tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.prompt_combo = ChoiceBox()
        self.populate_prompt_combo()
        self.prompt_combo.hide()

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(12)
        splitter.setChildrenCollapsible(False)

        left_panel = QWidget()
        left_panel.setFixedWidth(SIDEBAR_WIDTH)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.prompt_search_input = QLineEdit()
        self.prompt_search_input.setPlaceholderText("Rechercher un prompt…")
        self.prompt_search_input.textChanged.connect(self._apply_prompt_filter)
        left_layout.addWidget(self.prompt_search_input)

        self.prompt_order_list = SidebarList()
        self.prompt_order_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.prompt_order_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.prompt_order_list.setDefaultDropAction(Qt.MoveAction)
        self.prompt_order_list.setDropIndicatorShown(True)
        self.prompt_order_list.model().rowsMoved.connect(self.on_prompt_order_changed)
        self.prompt_order_list.currentItemChanged.connect(self._on_prompt_list_current_changed)
        left_layout.addWidget(self.prompt_order_list)

        left_buttons = QHBoxLayout()
        add_prompt_button = QPushButton("Ajouter")
        add_prompt_button.clicked.connect(self.add_prompt)
        left_buttons.addWidget(add_prompt_button)

        delete_prompt_button = QPushButton("Supprimer")
        delete_prompt_button.setProperty("variant", "danger")
        delete_prompt_button.clicked.connect(self.delete_prompt)
        left_buttons.addWidget(delete_prompt_button)

        left_layout.addLayout(left_buttons)
        transfer_buttons = QHBoxLayout()
        for label, callback in (("Importer", self.import_all_prompts), ("Exporter", self.export_all_prompts)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            transfer_buttons.addWidget(button)
        left_layout.addLayout(transfer_buttons)


        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        
        from supermenu_core.ui.text_prompt_form import TextPromptForm
        from supermenu_core.ui.page_actions import PromptActions

        self.text_prompt_form = TextPromptForm(settings=self.settings)
        self.prompt_name_input = self.text_prompt_form.name
        self.prompt_text_input = self.text_prompt_form.instruction
        self.prompt_status_input = self.text_prompt_form.status
        self.prompt_insert_directly = self.text_prompt_form.insert_directly
        self.prompt_hotkey_input = self.text_prompt_form.hotkey
        self.text_prompt_form.record_requested.connect(self.record_prompt_hotkey)
        self.text_prompt_form.clear_requested.connect(self.clear_prompt_hotkey)
        right_layout.addWidget(scrollable_form(self.text_prompt_form), 1)
        self.prompt_actions = PromptActions(self.reset_prompt, self.save_prompt)
        self.prompt_actions.restore_requested.connect(self.restore_prompt_library)
        # Offered by the shared actions once they expose the kept copies.
        restore_previous = getattr(self.prompt_actions, "restore_previous_requested", None)
        if restore_previous is not None:
            restore_previous.connect(self.restore_previous_prompt_library)
        right_layout.addWidget(self.prompt_actions)

        # Connect prompt selection change
        self.prompt_combo.currentIndexChanged.connect(self.load_prompt)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)
        
        # Add the tab
        self.tab_widget.addTab(prompts_tab, "Prompts")
        
        # Load the first prompt
        if self.prompt_combo.count() > 0:
            self.load_prompt(0)

        self.populate_prompt_order_list()

    def create_voice_prompts_tab(self):
        self.voice_prompt_editor = VoicePromptEditor(self.settings, self, list_factory=SidebarList, sidebar_width=SIDEBAR_WIDTH)
        self.voice_prompt_editor.run_button.hide()
        self.voice_prompt_editor.import_requested.connect(self.import_all_prompts)
        self.voice_prompt_editor.export_requested.connect(self.export_all_prompts)
        self.tab_widget.addTab(self.voice_prompt_editor, "Voix")

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

    def create_about_tab(self):
        from supermenu_core.ui.about_page import AboutPage
        from supermenu_core.ui.settings_panel import Disclosure

        diagnostics = Disclosure("Dossiers et diagnostic")
        self.app_settings_layout.addWidget(diagnostics)
        for label, callback in (
            ("Ouvrir le dossier de configuration", self.open_settings_folder),
            ("Ouvrir le dossier des journaux", self.open_logs_folder),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            diagnostics.content_layout.addWidget(button)
        self.tab_widget.addTab(AboutPage(
            self._get_installed_version_display(), self.open_releases_page
        ), "À propos")

    def _get_installed_version_display(self):
        # The running build comes first: the registry describes an installed
        # copy, absent for the portable executable and possibly older.
        if APP_VERSION != "dev":
            return APP_VERSION
        version = app_updater.get_installed_app_version("C8F9E2A0-1F3A-4E5D-B6A9-D5C8E4E0F2A1")
        if version:
            return version
        return "dev"

    def _refresh_update_channel_ui(self):
        self.update_channel_combo.setCurrentIndex(
            self.update_channel_combo.findData(self.settings.get_update_channel())
        )
        self.application_settings.refresh_channel()

    def schedule_startup_update_check(self):
        """Planifie une verification automatique discrete des mises a jour."""
        QTimer.singleShot(5000, self.check_for_updates_silently)

    def check_for_updates_silently(self):
        """Verifie les mises a jour une fois par jour sans bruit si rien n'est disponible."""
        today = date.today().isoformat()
        if self.settings.get_last_update_check_date() == today:
            return
        self.settings.set_last_update_check_date(today)
        self.settings.sync()
        self.check_for_updates(silent=True)

    def check_for_updates(self, silent=False):
        if self._update_check_worker and self._update_check_worker.isRunning():
            return

        self._update_check_silent = bool(silent)
        if not self._update_check_silent:
            self._update_loading = SimpleLoadingIndicator("Vérification des mises à jour...")
            self._update_loading.show()

        self._update_check_worker = _UpdateCheckWorker(
            owner="lfpoulain",
            repo="supermenu",
            channel=self.settings.get_update_channel(),
            app_id_guid="C8F9E2A0-1F3A-4E5D-B6A9-D5C8E4E0F2A1",
        )
        self._update_check_worker.finished_ok.connect(self._on_update_check_ok)
        self._update_check_worker.failed.connect(self._on_update_check_failed)
        self._update_check_worker.start()

    def _on_update_check_ok(self, data: dict):
        if self._update_loading:
            self._update_loading.close()
            self._update_loading = None

        installed_version = _running_app_version(data.get("installed_version"))
        latest_version = data.get("latest_version")
        channel = app_updater.normalize_update_channel(data.get("channel"))
        channel_label = "Beta" if channel == "beta" else "Stable"
        asset_name = data.get("asset_name") or app_updater.installer_asset_name(
            channel
        )
        asset_url = data.get("asset_url")
        silent = self._update_check_silent
        portable = bool(data.get("portable"))

        if not latest_version:
            if not silent:
                QMessageBox.warning(self, "Mise à jour", "Impossible de déterminer la version de la release.")
            return

        if not asset_url:
            if not silent:
                QMessageBox.warning(
                    self,
                    "Mise à jour",
                    "Aucun installateur compatible avec le canal "
                    f"{channel_label} n'a été trouvé ({asset_name}).",
                )
            return

        # Only an installed copy is notified in the background: the installer
        # cannot update the portable executable nor a source run.
        if silent and (portable or not data.get("installed_version")):
            return

        if not app_updater.is_newer_version(installed_version, latest_version):
            if not silent:
                QMessageBox.information(
                    self,
                    "Mise à jour",
                    f"Vous êtes déjà à jour sur le canal {channel_label}.\n\n"
                    f"Version actuelle : {installed_version or 'inconnue'}\n"
                    f"Dernière version : {latest_version}",
                )
            return

        if portable:
            # The installer would add a second copy under Program Files and
            # leave this executable as it is: point to the downloads instead.
            reply = QMessageBox.question(
                self,
                f"Mise à jour {channel_label} disponible",
                f"Une mise à jour du canal {channel_label} est disponible.\n\n"
                f"Version actuelle : {installed_version or 'inconnue'}\n"
                f"Nouvelle version : {latest_version}\n\n"
                "Cette version portable ne peut pas être mise à jour par l'installateur. "
                "Ouvrir la page des téléchargements ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                self.open_releases_page()
            return

        reply = QMessageBox.question(
            self,
            f"Mise à jour {channel_label} disponible",
            f"Une mise à jour du canal {channel_label} est disponible.\n\n"
            f"Version actuelle : {installed_version or 'inconnue'}\n"
            f"Nouvelle version : {latest_version}\n\n"
            "Télécharger et installer maintenant ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        asset_stem, asset_extension = os.path.splitext(asset_name)
        file_name = f"{asset_stem}_{latest_version}{asset_extension}"
        self._start_download_installer(asset_url, file_name, data.get("asset_sha256"))

    def _on_update_check_failed(self, error: str):
        if self._update_loading:
            self._update_loading.close()
            self._update_loading = None
        if self._update_check_silent:
            return
        QMessageBox.warning(self, "Mise à jour", f"Erreur lors de la vérification des mises à jour :\n\n{error}")

    def _start_download_installer(self, url: str, file_name: str, expected_sha256: str | None = None):
        if self._update_download_worker and self._update_download_worker.isRunning():
            return

        # Checked again right before the launch (see _launch_installer_and_quit).
        self._update_expected_sha256 = expected_sha256
        self._update_loading = SimpleLoadingIndicator("Téléchargement de l'installateur...")
        self._update_loading.show()

        self._update_download_worker = _UpdateDownloadWorker(url, file_name, expected_sha256)
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
            # A later update downloads it again: do not keep a copy in %TEMP%.
            _remove_update_folder(installer_path)
            return

        self._launch_installer_and_quit(installer_path)

    def _on_download_failed(self, error: str):
        if self._update_loading:
            self._update_loading.close()
            self._update_loading = None
        QMessageBox.warning(self, "Mise à jour", f"Erreur lors du téléchargement :\n\n{error}")

    def _launch_installer_and_quit(self, installer_path: str):
        try:
            # The file may have been replaced while the confirmation was shown.
            app_updater.verify_installer_sha256(installer_path, self._update_expected_sha256)
        except app_updater.UpdateIntegrityError as e:
            _remove_update_folder(installer_path)
            QMessageBox.warning(self, "Mise à jour", str(e))
            return
        except OSError as e:
            _remove_update_folder(installer_path)
            QMessageBox.warning(self, "Mise à jour", f"Impossible de lancer l'installateur :\n\n{e}")
            return

        try:
            params = ""
            cwd = os.path.dirname(installer_path)
            # Already elevated (relaunched by an earlier "runas" update), any
            # direct start would keep that token: go through the user's shell.
            launched = _process_is_elevated() and _open_through_user_shell(installer_path, cwd)
            if not launched:
                # "open", not "runas": the Inno loader asks for elevation itself and
                # relaunches SuperMenu with the user's rights. Started already
                # elevated, it would relaunch SuperMenu as administrator.
                rc = ctypes.windll.shell32.ShellExecuteW(None, "open", installer_path, params, cwd, 1)
                if rc == _SE_ERR_ACCESSDENIED:
                    # Retrying would only show a second prompt: keep SuperMenu open.
                    _remove_update_folder(installer_path)
                    QMessageBox.warning(
                        self,
                        "Mise à jour",
                        "Windows n'a pas lancé l'installateur. SuperMenu reste ouvert ; "
                        "vous pourrez relancer la mise à jour plus tard.",
                    )
                    return
                if rc <= 32:
                    subprocess.Popen([installer_path], cwd=cwd)
        except Exception:
            try:
                os.startfile(installer_path)
            except Exception as e:
                _remove_update_folder(installer_path)
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
        from supermenu_core.ui.configuration_shell import close_footer
        from supermenu_core.ui.settings_panel import Disclosure

        reset_section = Disclosure("Réinitialisation")
        reset_all_button = QPushButton("Réinitialiser tous les paramètres")
        reset_all_button.clicked.connect(self.reset_all_settings)
        reset_section.content_layout.addWidget(reset_all_button)
        self.app_settings_layout.addWidget(reset_section)
        
        self.main_layout.addLayout(close_footer(self.close))

    def load_prompt(self, index):
        """Load the selected prompt into the editing fields"""
        self.prompt_actions.reset_button.setEnabled(
            self.prompt_combo.currentData() in self.settings.default_prompts
        )
        if index < 0 or self.prompt_combo.count() == 0:
            return
            
        prompt_id = self.prompt_combo.currentData()
        prompt_data = self.settings.get_prompt(prompt_id)
        
        if prompt_data:
            self.prompt_name_input.setText(prompt_data["name"])
            self.prompt_text_input.setPlainText(prompt_data["prompt"])
            self.prompt_status_input.setText(prompt_data["status"])
            self.prompt_insert_directly.setChecked(prompt_data.get("insert_directly", False))
            self.text_prompt_form.reasoning.set_mode(prompt_data.get("reasoning_mode", "default"))
            self.text_prompt_form.model_choice.set_target(prompt_data.get("model_target", {}))
            self.prompt_hotkey_input.setText(prompt_data.get("hotkey", ""))


    def start_dictation(self):
        if self.context_menu_manager is not None:
            from src.utils.window_target import PasteTarget
            self.context_menu_manager._handle_voice_action(target=PasteTarget.capture())

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

    def open_response_window(self):
        if self.context_menu_manager:
            self.context_menu_manager.show_response_window()

    def change_hotkey(self):
        """Modifier le raccourci clavier"""
        if not self.hotkey_manager:
            # Cette situation ne devrait plus se produire si HotkeyManager est toujours passé
            QMessageBox.warning(self, "Erreur", "HotkeyManager non initialisé.")
            return

        if self._change_core_hotkey(self.hotkey_manager):
            QMessageBox.information(
                self,
                "Raccourci modifié",
                f"Le raccourci a été modifié avec succès en {self.settings.get_hotkey()}.\n\n"
                "Le nouveau raccourci est maintenant actif."
            )

    def _record_hotkey_with_shortcuts_released(self):
        """Show the recorder with every SuperMenu shortcut released.

        Windows consumes a registered shortcut before the dialog sees it: the
        combination would trigger its feature instead of being recorded.
        Returns the recorded shortcut, or None when the dialog is cancelled.
        """
        managers = [manager for manager in (
            self.hotkey_manager, self.voice_hotkey_manager,
            self.custom_hotkey_manager, self.screenshot_hotkey_manager,
            self.dictation_hotkey_manager,
        ) if manager is not None]
        for manager in managers:
            manager.unregister_hotkey()
        if self.prompt_hotkey_manager is not None:
            self.prompt_hotkey_manager.unregister_hotkeys()
        try:
            dialog = HotkeyRecorderDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.recorded_hotkey:
                return dialog.recorded_hotkey
            return None
        finally:
            for manager in managers:
                manager.register_hotkey()
            if self.prompt_hotkey_manager is not None:
                self.prompt_hotkey_manager.refresh_hotkeys()

    def _change_core_hotkey(self, manager):
        """Record and apply a main shortcut; True once the new one is active."""
        try:
            hotkey = self._record_hotkey_with_shortcuts_released()
            if not hotkey:
                return False
            # Every other shortcut is registered again at this point, so a
            # combination already used by SuperMenu is refused and rolled back.
            if manager.set_hotkey(hotkey):
                return True
            QMessageBox.warning(
                self,
                "Erreur",
                f"Impossible d'enregistrer le raccourci '{hotkey}'.\n\n"
                f"{getattr(manager, 'last_error', '')}",
            )
            return False
        finally:
            self._refresh_hotkey_states()

    def record_dictation_hotkey(self):
        shortcut = self._record_hotkey_with_shortcuts_released()
        if shortcut:
            self.dictation_shortcut_settings.set_shortcut(shortcut)

    def record_prompt_hotkey(self):
        """Capture a shortcut for the selected prompt without saving it yet."""
        if self.prompt_combo.count() == 0:
            return

        shortcut = self._record_hotkey_with_shortcuts_released()
        if shortcut:
            self.prompt_hotkey_input.setText(shortcut)

    def clear_prompt_hotkey(self):
        """Clear the shortcut editor; the change is applied when saving."""
        self.prompt_hotkey_input.clear()

    def change_voice_hotkey(self):
        """Modifier le raccourci vocal"""
        if not self.voice_hotkey_manager:
            # Cette situation ne devrait plus se produire
            QMessageBox.warning(self, "Erreur", "VoiceHotkeyManager non initialisé.")
            return

        if self._change_core_hotkey(self.voice_hotkey_manager):
            QMessageBox.information(
                self,
                "Raccourci modifié",
                f"Le raccourci vocal a été modifié avec succès en {self.settings.get_voice_hotkey()}.\n\n"
                "Le nouveau raccourci est maintenant actif."
            )

    def change_custom_hotkey(self):
        """Modifier le raccourci du mode personnalisé"""
        if not self.custom_hotkey_manager:
            QMessageBox.warning(self, "Erreur", "CustomHotkeyManager non initialisé.")
            return

        if self._change_core_hotkey(self.custom_hotkey_manager):
            QMessageBox.information(
                self,
                "Raccourci modifié",
                f"Le raccourci du mode personnalisé a été modifié avec succès en {self.settings.get_custom_hotkey()}.\n\n"
                "Le nouveau raccourci est maintenant actif."
            )

    def change_screenshot_hotkey(self):
        """Modifier le raccourci de capture d'écran"""
        if not self.screenshot_hotkey_manager:
            # Cette situation ne devrait plus se produire
            QMessageBox.warning(self, "Erreur", "ScreenshotHotkeyManager non initialisé.")
            return

        if self._change_core_hotkey(self.screenshot_hotkey_manager):
            QMessageBox.information(
                self,
                "Raccourci modifié",
                f"Le raccourci de capture d'écran a été modifié avec succès en {self.settings.get_screenshot_hotkey()}.\n\n"
                "Le nouveau raccourci est maintenant actif."
            )

    def _core_hotkey_rows(self):
        """(manager, field, configured shortcut) of the Shortcuts tab rows."""
        return (
            (self.hotkey_manager, self.hotkey_label, self.settings.get_hotkey),
            (self.custom_hotkey_manager, self.custom_hotkey_label, self.settings.get_custom_hotkey),
            (self.voice_hotkey_manager, self.voice_hotkey_label, self.settings.get_voice_hotkey),
            (self.screenshot_hotkey_manager, self.screenshot_hotkey_label, self.settings.get_screenshot_hotkey),
        )

    def _refresh_hotkey_states(self):
        """Show the configured shortcuts, marking those Windows refused."""
        for manager, field, configured_hotkey in self._core_hotkey_rows():
            hotkey = configured_hotkey()
            error = _hotkey_error(manager)
            if error:
                field.setText(f"{hotkey} (inactif)" if hotkey else "Inactif")
                field.setToolTip(f"Inactif : {error}")
            else:
                field.setText(hotkey)
                field.setToolTip("")

    def _on_hotkey_registration_failed(self, _error):
        self._refresh_hotkey_states()

    def _inactive_core_hotkeys(self):
        """Main shortcuts Windows refused: list of (feature, shortcut, error)."""
        failures = []
        for manager in (
            self.hotkey_manager,
            self.custom_hotkey_manager,
            self.voice_hotkey_manager,
            self.screenshot_hotkey_manager,
            self.dictation_hotkey_manager,
        ):
            error = _hotkey_error(manager)
            if error:
                failures.append((
                    getattr(manager, "feature_name", "Raccourci"),
                    getattr(manager, "hotkey", "") or "aucun",
                    error,
                ))
        return failures

    def restart_application(self):
        """Redémarrer l'application"""
        import os
        import sys
        import subprocess
        
        # Lancer un nouveau processus pour redémarrer l'application
        if getattr(sys, 'frozen', False):
            # A restarted app must own its extraction directory. Otherwise the
            # old onefile parent deletes its native libraries while it runs.
            environment = os.environ.copy()
            environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
            subprocess.Popen([sys.executable], env=environment)
        else:
            # Si l'application est en mode développement
            script_path = os.path.abspath(sys.argv[0])
            subprocess.Popen([sys.executable, script_path])
        QApplication.quit()

    def save_prompt(self):
        """Save the prompt"""
        # A model choice hidden with the advanced features is not saved.
        if not self.text_prompt_form.model_choice_is_valid():
            return False
        if self.prompt_combo.count() == 0:
            return

        prompt_id = self.prompt_combo.currentData()
        name = self.prompt_name_input.text().strip()
        prompt = self.prompt_text_input.toPlainText()
        status = self.prompt_status_input.text()
        insert_directly = self.prompt_insert_directly.isChecked()
        if self.text_prompt_form.is_advanced_visible():
            prompt_hotkey = self.prompt_hotkey_input.text().strip()
        else:
            # Hidden with the advanced features: the stored shortcut is kept.
            stored_prompt = self.settings.get_prompt(prompt_id) or {}
            prompt_hotkey = str(stored_prompt.get("hotkey", "") or "").strip()

        position = 999
        previous_prompts = self.settings.get_prompts()
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
        try:
            self.settings.update_prompt(
                prompt_id,
                name,
                prompt,
                status,
                insert_directly,
                position,
                hotkey=prompt_hotkey,
                reasoning_mode=self.text_prompt_form.reasoning.currentData(),
                # None keeps the stored model while the choice is hidden.
                model_target=self.text_prompt_form.model_target_for_save(),
            )
        except ValueError as e:
            QMessageBox.warning(self, "Raccourci invalide", str(e))
            return

        if self.prompt_hotkey_manager is not None:
            _success, errors = self.prompt_hotkey_manager.refresh_hotkeys()
            current_error = errors.get(prompt_id)
            if current_error:
                self.settings.set_prompts(previous_prompts)
                self.prompt_hotkey_manager.refresh_hotkeys()
                self.prompt_hotkey_input.setText(
                    previous_prompts.get(prompt_id, {}).get("hotkey", "")
                )
                QMessageBox.warning(
                    self,
                    "Raccourci indisponible",
                    f"Le raccourci '{prompt_hotkey}' n'a pas été enregistré.\n\n"
                    f"{current_error}",
                )
                return
        
        # Mettre à jour le nom dans le combo
        self.prompt_combo.setItemText(self.prompt_combo.currentIndex(), name)

        self.populate_prompt_order_list()
        
        QMessageBox.information(self, "Prompt enregistré", 
                              f"Le prompt '{name}' a été enregistré avec succès.")

    def reset_prompt(self):
        from supermenu_core.ui.text_prompt_form import reset_text_prompt
        reset_text_prompt(self.settings, self.prompt_combo.currentData(), self, self._prompts_restored)

    def _prompts_restored(self):
        self.populate_prompt_combo()
        self.populate_prompt_order_list()
        if self.prompt_hotkey_manager is not None:
            self.prompt_hotkey_manager.refresh_hotkeys()

    def restore_prompt_library(self):
        restore_library(self, self.settings, self._prompts_restored)

    def restore_previous_prompt_library(self):
        """Go back to the copy kept by the last restore, import or repair."""
        restore_previous_library(self, self.settings, self._prompts_restored)

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
            previous_hotkeys = {
                "hotkey": self.settings.get_hotkey(),
                "voice_hotkey": self.settings.get_voice_hotkey(),
                "dictation_hotkey": self.settings.get_dictation_hotkey(),
                "screenshot_hotkey": self.settings.get_screenshot_hotkey(),
                "custom_hotkey": self.settings.get_custom_hotkey(),
            }

            # Reset settings
            self.settings.reset_to_defaults()
            if self.prompt_hotkey_manager is not None:
                # A prompt may hold a default combination: release them first,
                # otherwise the default shortcuts are refused and rolled back.
                self.prompt_hotkey_manager.unregister_hotkeys()
            hotkeys_restored = self._reregister_all_hotkeys(previous_hotkeys)
            if self.prompt_hotkey_manager is not None:
                self.prompt_hotkey_manager.refresh_hotkeys()
            
            # Update the UI
            self.populate_prompt_combo()
            # The visible sidebar list, not only the hidden combo.
            self.populate_prompt_order_list()
            self.voice_prompt_editor.reload()
            
            # Reload the API configuration
            self.api_key_input.setText(self.settings.get_api_key())
            self.model_combo.setCurrentText(self.settings.get_model())
            self.update_reasoning_effort_ui()
            # Reload custom endpoint configuration
            self.ai_provider_combo.setCurrentIndex(self.ai_provider_combo.findData(self.settings.get_ai_provider()))
            self.foundry_group.model_combo.setCurrentIndex(
                self.foundry_group.model_combo.findData(self.settings.get_foundry_model())
            )
            self.foundry_group.device_combo.setCurrentIndex(
                self.foundry_group.device_combo.findData(self.settings.get_foundry_device())
            )
            self.custom_endpoint_input.setText(self.settings.get_custom_endpoint())
            self.custom_model_combo.clear()
            current_custom_model = self.settings.get_custom_model()
            if current_custom_model:
                self.custom_model_combo.addItem(current_custom_model)
                self.custom_model_combo.setCurrentText(current_custom_model)
            self._custom_model_details = {}
            self.update_custom_reasoning_effort_ui()
            
            # Update the display based on endpoint type
            self.toggle_custom_endpoint()
            
            # Reload the hotkeys
            self._refresh_hotkey_states()

            screenshot_mode = self.settings.get_screenshot_capture_mode()
            for i in range(self.screenshot_capture_mode_combo.count()):
                if self.screenshot_capture_mode_combo.itemData(i) == screenshot_mode:
                    self.screenshot_capture_mode_combo.setCurrentIndex(i)
                    break
            self._update_screenshot_capture_mode_ui_state()
            self._refresh_update_channel_ui()

            self.dictation_shortcut_settings.shortcut.setText(self.settings.get_dictation_hotkey())
            self.dictation_shortcut_settings.mode.setCurrentIndex(0)
            self.dictation_behavior.auto_insert.setChecked(False)
            self.dictation_behavior.correct_before_insert.setChecked(False)
            self.foundry_group.idle_combo.setCurrentIndex(self.foundry_group.idle_combo.findData(300))
            self.foundry_group.service.set_idle_seconds(300)
            self.speech_settings.idle_combo.setCurrentIndex(self.speech_settings.idle_combo.findData(300))
            self.speech_settings.resident.set_idle_seconds(300)
            self.speech_settings.refresh_microphones()
            self.speech_settings.provider_combo.setCurrentIndex(0)
            self.speech_settings.device_combo.setCurrentIndex(0)
            self.speech_settings.microphone_combo.setCurrentIndex(0)
            self.speech_settings.languages_input.setText(
                self.settings.get_transcription_languages()
            )
            self.speech_settings.keywords_input.setText(
                self.settings.get_transcription_keywords()
            )
            self.speech_settings.prompt_input.setPlainText(
                self.settings.get_transcription_prompt()
            )
            self.speech_settings._changed()

            # Load the first prompts
            if self.prompt_combo.count() > 0:
                self.load_prompt(0)
                
            
            if hotkeys_restored:
                QMessageBox.information(
                    self,
                    "Succès",
                    "Tous les paramètres ont été réinitialisés avec succès.",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Raccourcis conservés",
                    "Les paramètres ont été réinitialisés, mais les raccourcis par défaut "
                    "n'ont pas pu être enregistrés. Les anciens raccourcis ont été restaurés.",
                )
            # Mettre à jour la configuration du client API dans ContextMenuManager après réinitialisation
            if self.context_menu_manager:
                self.context_menu_manager.update_client_config()

    def _reregister_all_hotkeys(self, previous_hotkeys):
        """Apply all reset hotkeys together and roll them back on conflict."""
        managers = [
            self.hotkey_manager,
            self.voice_hotkey_manager,
            self.screenshot_hotkey_manager,
            self.custom_hotkey_manager,
            getattr(self, "dictation_hotkey_manager", None),
        ]
        active_managers = [manager for manager in managers if manager is not None]

        for manager in active_managers:
            manager.unregister_hotkey()

        try:
            for manager in active_managers:
                if not manager.register_hotkey():
                    raise RuntimeError(
                        getattr(manager, "_last_register_error", "")
                        or "échec d'enregistrement du raccourci"
                    )
            return True
        except Exception:
            for manager in active_managers:
                manager.unregister_hotkey()

            self.settings.set_hotkey(previous_hotkeys["hotkey"])
            self.settings.set_voice_hotkey(previous_hotkeys["voice_hotkey"])
            self.settings.set_screenshot_hotkey(
                previous_hotkeys["screenshot_hotkey"]
            )
            self.settings.set_custom_hotkey(previous_hotkeys["custom_hotkey"])
            if "dictation_hotkey" in previous_hotkeys:
                self.settings.set_dictation_hotkey(previous_hotkeys["dictation_hotkey"])
            self.settings.sync()

            for manager in active_managers:
                manager.register_hotkey()
            return False

    def setup_tray_icon(self):
        """Set up the system tray icon"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False

        # Create the tray icon
        self.tray_icon = QSystemTrayIcon(self)
        
        # Set the icon
        icon_path = resource_path("resources", "icons", "icon.png")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            # Utiliser une icône standard de Qt qui existe
            self.tray_icon.setIcon(QIcon.fromTheme("computer", QIcon.fromTheme("application-x-executable")))
        
        # Create the tray menu
        tray_menu = Menu()
        
        # Add actions to the tray menu
        open_action = QAction("Ouvrir SuperMenu", self)
        open_action.triggered.connect(self.show)
        tray_menu.addAction(open_action)

        update_action = QAction("Vérifier les mises à jour", self)
        update_action.triggered.connect(self.check_for_updates)
        tray_menu.addAction(update_action)

        response_window_action = QAction("Afficher la dernière réponse", self)
        response_window_action.triggered.connect(self.open_response_window)
        response_window_action.setEnabled(self.context_menu_manager is not None)
        tray_menu.addAction(response_window_action)
        
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
        self._refresh_hotkey_states()
        failures = self._inactive_core_hotkeys()
        if failures:
            name, hotkey, detail = failures[0]
            self.statusBar().showMessage(f"Raccourci inactif — {name} ({hotkey}) : {detail}")
        elif self.prompt_hotkey_manager is not None and self.prompt_hotkey_manager.errors:
            errors = self.prompt_hotkey_manager.errors
            prompt_id, detail = next(iter(errors.items()))
            prompt = self.settings.get_prompt(prompt_id) or {}
            self.statusBar().showMessage(
                f"Raccourci inactif — {prompt.get('name', prompt_id)} : {detail}"
            )

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
            999,
            hotkey="",
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
            if self.prompt_hotkey_manager is not None:
                self.prompt_hotkey_manager.refresh_hotkeys()
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
                item.setToolTip(item.text())
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
        changed = False
        for row in range(self.prompt_order_list.count()):
            item = self.prompt_order_list.item(row)
            prompt_id = item.data(Qt.UserRole)
            if prompt_id not in prompts:
                continue
            prompt_data = prompts[prompt_id]
            new_position = (row + 1) * 10
            if prompt_data.get("position", 999) == new_position:
                continue
            prompt_data["position"] = new_position
            changed = True

        if changed:
            self.settings.set_prompts(prompts)

        self.populate_prompt_combo()
        self.populate_prompt_order_list()


    def save_theme_selection(self):
        """Save the selected theme"""
        selected_index = self.theme_combo.currentIndex()
        theme = self.theme_combo.itemData(selected_index)
        
        # Update settings
        self.settings.set_theme(theme)

        # Saving the switches emits modes_changed, applied by apply_feature_modes.
        self._feature_mode_problems = []
        feature_mode_settings = getattr(self, "feature_mode_settings", None)
        if feature_mode_settings is not None:
            try:
                feature_mode_settings.save()
            except Exception as e:
                _log_warning(f"Fonctions avancées/expérimentales non appliquées: {e}")
        problems = list(getattr(self, "_feature_mode_problems", []) or [])
        self._feature_mode_problems = []

        self.settings.sync()
        from supermenu_core.ui.theme_manager import ThemeManager
        ThemeManager.apply_theme(QApplication.instance(), theme)
        if problems:
            QMessageBox.warning(
                self,
                "Raccourcis inactifs",
                "Les modifications sont actives, mais ces raccourcis n’ont pas pu "
                "être enregistrés :\n\n"
                + "\n".join(problems)
                + "\n\nChoisissez-en un autre dans Réglages > Raccourcis ou dans "
                "l’onglet Prompts.",
            )
        else:
            QMessageBox.information(self, "Réglages enregistrés", "Les modifications sont actives.")

    def _current_feature_modes(self):
        """(advanced, experimental) as saved; read at each use, never cached."""
        return (
            bool(advanced_enabled(self.settings)),
            bool(experimental_enabled(self.settings)),
        )

    def _apply_feature_visibility(self):
        """Show the enabled features and hide the others; nothing is deleted.

        Only the interface changes here: the shortcut managers are left alone.
        """
        advanced, experimental = self._current_feature_modes()
        steps = (
            ("onglet Voix", lambda: self._set_voice_tab_visible(experimental)),
            ("rubrique Dictée", lambda: self.settings_panel.set_page_visible("voice", experimental)),
            ("raccourcis expérimentaux", lambda: self._set_experimental_shortcuts_visible(experimental)),
            ("options du prompt", lambda: self.text_prompt_form.set_advanced_visible(advanced)),
            ("options du prompt vocal", lambda: self.voice_prompt_editor.set_advanced_visible(advanced)),
            ("mémoire du modèle texte", lambda: self.foundry_group.set_retention_visible(advanced)),
            ("note du moteur vocal", lambda: self.foundry_group.set_voice_note_visible(experimental)),
            ("mémoire du modèle vocal", lambda: self.speech_settings.set_retention_visible(advanced)),
            ("aide de la dictée", lambda: self.dictation_behavior.set_prompt_model_hint(advanced)),
            ("interrupteurs", lambda: self.feature_mode_settings.refresh()),
        )
        for name, step in steps:
            try:
                step()
            except Exception as e:
                _log_warning(f"Affichage des fonctions ({name}) non mis à jour: {e}")

    def _set_voice_tab_visible(self, visible):
        index = self.tab_widget.indexOf(self.voice_prompt_editor)
        if index < 0:
            return
        # A hidden current tab would stay displayed: leave it first.
        if not visible and self.tab_widget.currentIndex() == index:
            self.tab_widget.setCurrentIndex(0)
        self.tab_widget.setTabVisible(index, visible)

    def _set_experimental_shortcuts_visible(self, visible):
        self.shortcut_settings.set_shortcut_visible(self.voice_hotkey_label, visible)
        self.shortcut_settings.set_shortcut_visible(self.screenshot_hotkey_label, visible)
        self.dictation_shortcut_settings.setVisible(visible)
        self.screenshot_group.setVisible(visible)

    def apply_feature_modes(self, *_args):
        """Apply the saved switches without restarting SuperMenu.

        Updates the interface, registers or releases the affected shortcuts
        in the startup order (core shortcuts before prompt shortcuts) and the
        model retention of the running local services. Returns the lines
        describing the shortcuts left inactive, also kept for the Apply box.
        """
        advanced, experimental = self._current_feature_modes()
        previous_advanced, previous_experimental = getattr(
            self, "_applied_feature_modes", (advanced, experimental)
        )
        advanced_changed = advanced != previous_advanced
        experimental_changed = experimental != previous_experimental
        self._apply_feature_visibility()

        prompt_errors = {}
        if advanced_changed or experimental_changed:
            prompt_hotkey_manager = self.prompt_hotkey_manager
            try:
                if prompt_hotkey_manager is not None:
                    # A prompt must never take a core shortcut that comes back.
                    prompt_hotkey_manager.unregister_hotkeys()
                if experimental_changed:
                    for manager in (
                        self.voice_hotkey_manager,
                        self.screenshot_hotkey_manager,
                        self.dictation_hotkey_manager,
                    ):
                        if manager is not None:
                            manager.register_hotkey()
            except Exception as e:
                _log_warning(f"Raccourcis des fonctions non mis à jour: {e}")
            try:
                if prompt_hotkey_manager is not None:
                    _registered, prompt_errors = prompt_hotkey_manager.refresh_hotkeys()
            except Exception as e:
                _log_warning(f"Raccourcis des prompts non mis à jour: {e}")
            try:
                self._refresh_hotkey_states()
            except Exception as e:
                _log_warning(f"État des raccourcis non mis à jour: {e}")

        # Without the advanced features the local models use the default delay.
        try:
            self.foundry_group.service.set_idle_seconds(
                effective_text_idle_seconds(self.settings)
            )
        except Exception as e:
            _log_warning(f"Délai du modèle texte non appliqué: {e}")
        speech_settings = self.speech_settings
        try:
            # Without the experimental features no voice model stays loaded:
            # a dictation in progress ends normally, then its model unloads.
            speech_settings.resident.set_idle_seconds(
                effective_speech_idle_seconds(self.settings) if experimental else 0
            )
        except Exception as e:
            _log_warning(f"Délai du modèle vocal non appliqué: {e}")
        if experimental_changed and not experimental:
            # Nothing keeps the microphone or an idle voice model for a
            # disabled feature; a dictation in progress is not interrupted.
            # Only what is running stops: an interrupted check or download
            # says so instead of staying "in progress" when the features come
            # back, and an idle page keeps its last result.
            def stop_voice_check():
                if speech_settings.backend is not None:
                    speech_settings.cancel()

            def stop_microphone_test():
                if speech_settings.microphone_test.active:
                    speech_settings.microphone_test.cancel(silent=True)

            for name, step in (
                ("vérification vocale", stop_voice_check),
                ("test du micro", stop_microphone_test),
                ("modèle vocal", speech_settings.resident.unload_idle),
            ):
                try:
                    step()
                except Exception as e:
                    _log_warning(f"Arrêt ({name}) impossible: {e}")

        problems = [
            f"- {name} ({hotkey}) : {error}"
            for name, hotkey, error in self._inactive_core_hotkeys()
        ]
        for prompt_id, error in (prompt_errors or {}).items():
            prompt = self.settings.get_prompt(prompt_id) or {}
            problems.append(f"- {prompt.get('name', prompt_id)} : {error}")
        self._feature_mode_problems = problems
        self._applied_feature_modes = (advanced, experimental)
        return problems

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
                    shortcut_errors = {}
                    prompt_hotkey_manager = getattr(
                        self,
                        "prompt_hotkey_manager",
                        None,
                    )
                    if prompt_hotkey_manager is not None:
                        _registered, shortcut_errors = (
                            prompt_hotkey_manager.refresh_hotkeys()
                        )
                    QMessageBox.information(self, "Importation Réussie", message)
                    # Rafraîchir les listes de prompts dans l'UI
                    self.populate_prompt_combo()
                    self.voice_prompt_editor.reload()
                    # Optionnellement, sélectionner le premier prompt ou aucun
                    if self.prompt_combo.count() > 0:
                        self.prompt_combo.setCurrentIndex(0)
                        self.load_prompt(0)
                    else:
                        self.clear_prompt_editor()
                    # The sidebar list is the visible selector: rebuild it too.
                    populate_prompt_order_list = getattr(
                        self,
                        "populate_prompt_order_list",
                        None,
                    )
                    if populate_prompt_order_list is not None:
                        populate_prompt_order_list()
                    
                    if shortcut_errors:
                        QMessageBox.warning(
                            self,
                            "Certains raccourcis sont indisponibles",
                            "\n".join(
                                f"- {prompt_id}: {error}"
                                for prompt_id, error in shortcut_errors.items()
                            ),
                        )
                else:
                    QMessageBox.warning(self, "Erreur d'Importation", message)

    def clear_prompt_editor(self):
        self.prompt_name_input.clear()
        self.prompt_text_input.clear()
        self.prompt_status_input.clear()
        self.prompt_insert_directly.setChecked(False)
        self.text_prompt_form.reasoning.set_mode("default")
        self.text_prompt_form.model_choice.set_target({})
        self.prompt_hotkey_input.clear()


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
