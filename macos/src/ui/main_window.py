"""Configuration window for the macOS application composition."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWidgets import QMessageBox  # noqa: F401 - patched through this module by tests.
from supermenu_core.ui.prompt_restore import restore_previous_library
from supermenu_core.ui.controls import SidebarList, SIDEBAR_WIDTH

from src.config.build_info import APP_VERSION
from supermenu_core.config.feature_modes import (
    advanced_enabled,
    effective_speech_idle_seconds,
    experimental_enabled,
)
from supermenu_core.ui.voice_prompt_editor import VoicePromptEditor
from src.utils import updater as app_updater
from src.utils.key_events import KeyEventPoster
from src.utils.paths import resource_path
from src.utils.logger import log
from src.utils.window_target import PasteTarget, activate_current_application
from src.utils.permissions import (
    current_permission_status,
    open_accessibility_settings,
    request_accessibility_permission,
)
from src.ui.main_window_updates import UpdateActionsMixin
from src.ui.main_window_updates import UpdateCheckWorker  # noqa: F401 - read through this module by tests.
from src.ui.main_window_hotkeys import HotkeyActionsMixin
from src.ui.main_window_prompts import PromptPageMixin
from src.ui.main_window_settings import SettingsPageMixin
from src.ui.main_window_settings import CustomModelsWorker  # noqa: F401 - read through this module by tests.


# Shown or hidden with the experimental features, without rebuilding the menu.
DICTATION_MENU_ENTRY = "Dicter du texte…"


class MainWindow(SettingsPageMixin, PromptPageMixin, HotkeyActionsMixin, UpdateActionsMixin, QMainWindow):
    """Edit prompts and settings while the app lives in the menu bar."""

    def __init__(
        self,
        settings,
        context_menu_manager=None,
        hotkey_manager=None,
        custom_hotkey_manager=None,
        prompt_hotkey_manager=None,
        dictation_hotkey_manager=None,
    ):
        super().__init__()
        self.settings = settings
        self.context_menu_manager = context_menu_manager
        self.hotkey_manager = hotkey_manager
        self.custom_hotkey_manager = custom_hotkey_manager
        self.prompt_hotkey_manager = prompt_hotkey_manager
        self.dictation_hotkey_manager = dictation_hotkey_manager
        self.tray_icon = None
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

        from supermenu_core.ui.configuration_shell import ConfigurationShell, close_footer

        self.shell = ConfigurationShell(
            self, QIcon(resource_path("resources", "icons", "icon.png"))
        )
        self.tabs = self.shell.tabs
        self.tabs.addTab(self._create_prompts_tab(), "Prompts")
        self.voice_prompt_editor = VoicePromptEditor(self.settings, self, list_factory=SidebarList, sidebar_width=SIDEBAR_WIDTH)
        self.voice_prompt_editor.run_requested.connect(self.run_voice_prompt)
        self.voice_prompt_editor.import_requested.connect(self.import_prompts)
        self.voice_prompt_editor.export_requested.connect(self.export_prompts)
        self.tabs.addTab(self.voice_prompt_editor, "Voix")
        self.settings_tab = self._create_settings_tab()
        self.tabs.addTab(self.settings_tab, "Réglages")
        self.tabs.addTab(self._create_about_tab(), "À propos")
        self.shell.content_layout.addLayout(close_footer(self.hide))
        # Startup registered the shortcuts already: only the interface follows
        # the switches here; apply_feature_modes handles later changes.
        self._feature_mode_problems = []
        self._applied_feature_modes = self._feature_modes()
        self._apply_feature_visibility()

        # Polled while the configuration window is on screen. SuperMenu lives
        # in the menu bar and is hidden most of the time; a permanent 1.5 s
        # wake-up costs battery for a panel nobody is looking at. The only
        # exception is a pending Accessibility grant: the monitors created
        # before it must be recreated once macOS grants it, even if the user
        # closed the window before opening System Settings.
        self._permission_timer = QTimer(self)
        self._permission_timer.setInterval(1500)
        self._permission_timer.timeout.connect(self._poll_permission_status)

    def _create_about_tab(self):
        from supermenu_core.ui.about_page import AboutPage
        return AboutPage(APP_VERSION, lambda: QDesktopServices.openUrl(
            QUrl(app_updater.REPOSITORY_RELEASES_URL)
        ))

    def restore_previous_prompt_library(self):
        """Go back to the copy kept by the last restore, import or repair."""
        restore_previous_library(self, self.settings, self._prompts_restored)

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
                getattr(self, "dictation_hotkey_manager", None),
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
        dictation_manager = getattr(self, "dictation_hotkey_manager", None)
        # Instant dictation stays unbound without the experimental features.
        if (
            dictation_manager is not None
            and experimental_enabled(self.settings)
            and self.settings.get_dictation_hotkey()
        ):
            hotkey_managers.append(dictation_manager)
        listeners_registered = bool(hotkey_managers) and all(
            manager.registered for manager in hotkey_managers
        )
        prompt_errors = (
            getattr(self.prompt_hotkey_manager, "errors", {})
            if self.prompt_hotkey_manager is not None
            else {}
        )
        hotkeys_active = listeners_registered and hotkeys_ok and not prompt_errors
        # macOS creates the AppKit monitors even without Accessibility; they
        # just never receive a key. Registered monitors only prove the
        # shortcuts work when the permission is granted or cannot be read.
        if hotkeys_active and (
            status.all_granted or not status.accessibility_check_available
        ):
            message = "✅ Raccourcis globaux actifs"
            if not status.all_granted:
                message += (
                    " — la lecture de l’état macOS reste incomplète ; "
                    "vérifiez Accessibilité avant le premier copier-coller."
                )
            granted = True
        elif not status.all_granted:
            missing = " et ".join(status.missing_labels)
            message = (
                f"⚠️ Raccourcis inactifs : autorisez {missing}. "
                "Si SuperMenu n’apparaît pas, ajoutez SuperMenu.app avec le bouton +."
            )
            granted = False
        else:
            refused = self.refused_hotkey_messages()
            errors = [
                manager.last_register_error
                for manager in hotkey_managers
                if manager is not None and manager.last_register_error
            ]
            errors.extend(str(error) for error in prompt_errors.values() if error)
            detail = errors[0] if errors else "redémarrage requis"
            if refused:
                # A saved shortcut refused by validation: relaunching would
                # refuse it again, recording a new one fixes it.
                message = (
                    f"⚠️ Raccourci inactif — {refused[0].rstrip('.')}. "
                    "Réenregistrez-le avec « Définir »."
                )
            else:
                message = (
                    "⚠️ Autorisations accordées, mais les raccourcis ne sont "
                    f"pas encore actifs ({detail}). Quittez puis relancez SuperMenu."
                )
            granted = False
        self._set_status_label(
            self.hotkey_service_status,
            message,
            granted,
        )
        self._last_permission_state = state
        return status

    def _feature_modes(self):
        """The saved switches as (advanced, experimental), read now."""
        return (
            bool(advanced_enabled(self.settings)),
            bool(experimental_enabled(self.settings)),
        )

    def _apply_feature_visibility(self):
        """Show or hide the switchable features; never touches a shortcut.

        Hidden tabs, pages and rows keep their widgets and stored values, so
        turning a feature back on shows everything exactly as it was.
        """
        advanced, experimental = self._feature_modes()
        voice_index = self.tabs.indexOf(self.voice_prompt_editor)
        if not experimental and self.tabs.currentIndex() == voice_index:
            self.tabs.setCurrentIndex(0)
        self.tabs.setTabVisible(voice_index, experimental)
        self.settings_panel.set_page_visible("voice", experimental)
        self.dictation_shortcut_settings.setVisible(experimental)
        self.text_prompt_form.set_advanced_visible(advanced)
        self.voice_prompt_editor.set_advanced_visible(advanced)
        self.speech_settings.set_retention_visible(advanced)
        self.dictation_behavior.set_prompt_model_hint(advanced)
        self._set_status_entry_visible(experimental)
        self.feature_mode_settings.refresh()

    def _set_status_entry_visible(self, experimental):
        tray = self.tray_icon
        if tray is None or not hasattr(tray, "set_entry_visible"):
            return
        try:
            tray.set_entry_visible(DICTATION_MENU_ENTRY, experimental)
        except Exception as exc:
            log(f"Entrée de dictée de la barre des menus : {exc}", logging.WARNING)

    def apply_feature_modes(self, *_args):
        """Apply the switches without restarting; return the problem lines.

        Shortcuts follow the startup order: prompt shortcuts are released
        before instant dictation registers, then bound again, so the core
        shortcut keeps priority exactly as after a relaunch.
        """
        problems = []
        previous = getattr(self, "_applied_feature_modes", None)
        advanced, experimental = current = self._feature_modes()
        self._applied_feature_modes = current
        advanced_changed = previous is None or previous[0] != advanced
        experimental_changed = previous is None or previous[1] != experimental
        prompt_errors = {}

        def step(description, action):
            try:
                return action()
            except Exception as exc:
                log(f"{description} impossible : {exc}", logging.WARNING)
                return None

        step("Affichage des fonctions", self._apply_feature_visibility)
        if advanced_changed or experimental_changed:
            if self.prompt_hotkey_manager is not None:
                step(
                    "Libération des raccourcis de prompts",
                    self.prompt_hotkey_manager.unregister_hotkeys,
                )
            dictation_manager = self.dictation_hotkey_manager
            if experimental_changed and dictation_manager is not None:
                step(
                    "Raccourci de dictée instantanée",
                    dictation_manager.register_hotkey,
                )
            refreshed = step("Raccourcis de prompts", self._refresh_prompt_hotkeys)
            if refreshed:
                prompt_errors = dict(refreshed[1] or {})
        speech = self.speech_settings
        resident = speech.resident
        # Without the experimental features no voice model stays loaded: a
        # dictation already running is not interrupted, and its model is
        # unloaded as soon as it ends. The saved delay is kept.
        step(
            "Conservation du modèle vocal",
            lambda: resident.set_idle_seconds(
                effective_speech_idle_seconds(self.settings)
                if experimental
                else 0
            ),
        )
        if experimental_changed and not experimental:
            # Nothing keeps the microphone or a voice model for a hidden
            # feature. Only what is running is stopped: an interrupted check
            # or download says so instead of staying "in progress" when the
            # features come back, and an idle page keeps its last result.
            def stop_voice_check():
                if speech.backend is not None:
                    speech.cancel()

            def stop_microphone_test():
                if speech.microphone_test.active:
                    speech.microphone_test.cancel(silent=True)

            step("Arrêt de la vérification vocale", stop_voice_check)
            step("Arrêt du test du micro", stop_microphone_test)
            step("Déchargement du modèle vocal", resident.unload_idle)
        step("État des raccourcis", self.refresh_permission_status)
        dictation_manager = self.dictation_hotkey_manager
        if experimental_changed and experimental and dictation_manager is not None:
            error = getattr(dictation_manager, "last_register_error", "")
            if error:
                hotkey = self.settings.get_dictation_hotkey()
                problems.append(f"- Dictée instantanée ({hotkey}) : {error}")
        if prompt_errors:
            prompts = self.settings.get_prompts()
            for prompt_id, error in prompt_errors.items():
                prompt = prompts.get(prompt_id)
                name = (
                    str(prompt.get("name") or "").strip()
                    if isinstance(prompt, dict)
                    else ""
                ) or (
                    "Raccourcis des prompts"
                    if prompt_id == "registration"
                    else prompt_id
                )
                problems.append(f"- {name} : {error}")
        self._feature_mode_problems = problems
        return problems

    def _status_menu_entries(self):
        """Describe the menu-bar menu once; ``None`` is a separator."""
        return [
            ("Ouvrir SuperMenu", self.show_main_window),
            ("Afficher le menu des prompts", self.show_prompt_menu),
            (DICTATION_MENU_ENTRY, self.start_dictation),
            ("Afficher la dernière réponse", lambda: self.context_menu_manager
             and self.context_menu_manager.show_response_window()),
            ("Vérifier les mises à jour", lambda: self.check_for_updates(False)),
            ("Autorisations macOS…", self.show_permission_setup),
            None,
            ("Quitter", self.quit_application),
        ]

    def setup_tray_icon(self):
        if self.tray_icon is not None:
            return True
        if sys.platform != "darwin":
            # Only the native AppKit status item ships on macOS: Qt's
            # QSystemTrayIcon crashed there and is not used any more.
            log("Barre des menus native indisponible hors macOS")
            return False
        try:
            from src.ui.status_item import NativeStatusItem

            self.tray_icon = NativeStatusItem(
                resource_path("resources", "icons", "icon.png"),
                self._status_menu_entries(),
                self,
            )
            QApplication.instance().aboutToQuit.connect(self.tray_icon.hide)
        except Exception as exc:
            log(f"Barre des menus native indisponible : {exc}")
            return False
        # Outside the try: hiding the dictation entry never fails the setup.
        self._set_status_entry_visible(experimental_enabled(self.settings))
        return True

    def show_main_window(self):
        # Record where the user came from before SuperMenu takes the
        # foreground, so "Afficher le menu des prompts" still has a target.
        PasteTarget.remember_frontmost()
        activate_current_application()
        self.refresh_permission_status()
        self.show()
        self.raise_()
        self.activateWindow()

    def run_voice_prompt(self, prompt_id):
        if self.context_menu_manager:
            self.context_menu_manager.run_voice_prompt(prompt_id, from_ui=True)

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
        self.tabs.setCurrentWidget(self.settings_tab)
        self.settings_panel.select_page("app")
        self.show_main_window()

    def quit_application(self):
        self._quitting = True
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()

    @staticmethod
    def _awaiting_accessibility(status):
        """Whether macOS can still report the Accessibility grant later."""
        return bool(
            status.accessibility_check_available and not status.accessibility
        )

    def _poll_permission_status(self):
        status = self.refresh_permission_status()
        if not self.isVisible() and not self._awaiting_accessibility(status):
            self._permission_timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self._permission_timer.start()

    def hideEvent(self, event):
        if self._quitting or not self._awaiting_accessibility(
            current_permission_status()
        ):
            self._permission_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        if self._quitting:
            self._permission_timer.stop()
            self._cancel_apple_probe()
            event.accept()
        else:
            event.ignore()
            # hideEvent decides whether the permission watch keeps running.
            self.hide()
