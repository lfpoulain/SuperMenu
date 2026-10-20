#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import sys
import tempfile
import ctypes
from datetime import date
from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QMessageBox,
    QSystemTrayIcon,
    QApplication,
    QDialog,
)
from PySide6.QtWidgets import QFileDialog  # noqa: F401 - patched through this module by tests.
from PySide6.QtCore import Signal, QTimer
from PySide6.QtGui import QIcon, QAction
from supermenu_core.ui.prompt_restore import restore_previous_library
from supermenu_core.ui.controls import Menu

from src.config.build_info import APP_VERSION
from supermenu_core.config.feature_modes import (
    advanced_enabled,
    effective_speech_idle_seconds,
    effective_text_idle_seconds,
    experimental_enabled,
)
from src.utils import updater as app_updater
from supermenu_core.ui.loading_indicator import SimpleLoadingIndicator
from src.utils.hotkey_manager import HotkeyRecorderDialog
from src.utils.paths import resource_path
from src.ui.background_worker import _BackgroundWorker
from src.ui.main_window_settings import SettingsPageMixin
from src.ui.main_window_settings import _CustomModelsWorker  # noqa: F401 - read through this module by tests.
from src.ui.main_window_prompts import PromptPageMixin
from src.ui.main_window_hotkeys import HotkeyActionsMixin


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


class MainWindow(HotkeyActionsMixin, PromptPageMixin, SettingsPageMixin, QMainWindow):
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

        # "Ouvrir les réglages" after a missing or refused API key.
        response_window = getattr(self.context_menu_manager, "response_window", None)
        if response_window is not None and hasattr(response_window, "settings_requested"):
            response_window.settings_requested.connect(lambda: self.show_settings_page("text"))

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
            self._update_loading = SimpleLoadingIndicator("Vérification des mises à jour…")
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
        self._update_loading = SimpleLoadingIndicator("Téléchargement de l’installateur…")
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

    def start_dictation(self):
        if self.context_menu_manager is not None:
            from src.utils.window_target import PasteTarget
            self.context_menu_manager._handle_voice_action(target=PasteTarget.capture())

    def open_response_window(self):
        if self.context_menu_manager:
            self.context_menu_manager.show_response_window()

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

    def show_settings_page(self, key):
        """Show the main window on one settings page ("text", "app"…)."""
        self.tab_widget.setCurrentWidget(self.settings_panel)
        self.settings_panel.select_page(key)
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
