#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ctypes
import ctypes.wintypes
import os
import sys
import logging
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from src.ui.main_window import MainWindow
from src.utils.context_menu import ContextMenuManager
from src.utils.hotkey_manager import HotkeyManager, PromptHotkeyManager
from src.utils.logger import log, logger
from src.config.settings import Settings

# Instance unique : un mutex nommé (atomique) désigne l'instance principale de
# la session Windows ; le canal local sert seulement à lui demander de
# s'afficher. QLocalServer seul ne suffit pas : sous Windows, deux processus
# peuvent écouter sur le même nom de canal.
_INSTANCE_MUTEX_NAME = "Local\\SuperMenuSingleInstance"
_INSTANCE_SERVER_NAME = "SuperMenuSingleInstance"
# Délai laissé à une instance qui se ferme (redémarrage, mise à jour) pour
# libérer le verrou avant que la nouvelle ne renonce à démarrer.
_INSTANCE_WAIT_MS = 5000
_ERROR_ACCESS_DENIED = 5
_ERROR_ALREADY_EXISTS = 183
_WAIT_OBJECT_0 = 0x00000000
_WAIT_ABANDONED = 0x00000080

_KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True) if sys.platform.startswith("win") else None

if _KERNEL32 is not None:
    _KERNEL32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]
    _KERNEL32.CreateMutexW.restype = ctypes.wintypes.HANDLE
    _KERNEL32.WaitForSingleObject.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD]
    _KERNEL32.WaitForSingleObject.restype = ctypes.wintypes.DWORD
    _KERNEL32.ReleaseMutex.argtypes = [ctypes.wintypes.HANDLE]
    _KERNEL32.ReleaseMutex.restype = ctypes.wintypes.BOOL
    _KERNEL32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
    _KERNEL32.CloseHandle.restype = ctypes.wintypes.BOOL
    _KERNEL32.ProcessIdToSessionId.argtypes = [ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.wintypes.DWORD)]
    _KERNEL32.ProcessIdToSessionId.restype = ctypes.wintypes.BOOL


def _instance_server_name():
    """Nom du canal « show », propre à la session (les canaux nommés sont globaux)."""
    if _KERNEL32 is not None:
        session_id = ctypes.wintypes.DWORD()
        try:
            if _KERNEL32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session_id)):
                return f"{_INSTANCE_SERVER_NAME}-{session_id.value}"
        except Exception:
            pass
    return _INSTANCE_SERVER_NAME


def _create_instance_mutex(name=None):
    """Crée ou ouvre le verrou d'instance.

    Renvoie ``(handle, already_running)``. ``handle`` vaut None quand le verrou
    est indisponible ; l'appelant retombe alors sur le seul canal local.
    """
    if _KERNEL32 is None:
        return None, False
    try:
        ctypes.set_last_error(0)
        handle = _KERNEL32.CreateMutexW(None, True, name or _INSTANCE_MUTEX_NAME)
        error = ctypes.get_last_error()
    except Exception:
        return None, False
    if not handle:
        # Verrou créé par une instance d'un autre niveau de privilège.
        return None, error == _ERROR_ACCESS_DENIED
    return handle, error == _ERROR_ALREADY_EXISTS


def _wait_instance_mutex(handle, timeout_ms):
    """Attend que l'instance précédente libère le verrou (ou se termine)."""
    try:
        result = _KERNEL32.WaitForSingleObject(handle, int(timeout_ms))
    except Exception:
        return False
    return result in (_WAIT_OBJECT_0, _WAIT_ABANDONED)


def _close_instance_mutex(handle, owned):
    if _KERNEL32 is None or not handle:
        return
    try:
        if owned:
            _KERNEL32.ReleaseMutex(handle)
    finally:
        _KERNEL32.CloseHandle(handle)


def _inactive_hotkeys(managers):
    """Raccourcis principaux refusés : liste de (fonction, raccourci, erreur)."""
    failures = []
    for manager in managers:
        if manager is None:
            continue
        error = getattr(manager, "last_error", "")
        if error and not getattr(manager, "registered", False):
            failures.append((manager.feature_name, manager.hotkey or "aucun", error))
    return failures


def _hotkey_failure_message(failures, prompt_error_count=0):
    """Titre et texte court de la notification ; None si tout est actif."""
    if not failures and not prompt_error_count:
        return None
    if len(failures) == 1:
        name, hotkey, error = failures[0]
        details = [f"{name} ({hotkey}) : {error}"]
    else:
        details = [f"{name} ({hotkey})" for name, hotkey, _ in failures]
    if prompt_error_count:
        plural = "s" if prompt_error_count > 1 else ""
        details.append(f"{prompt_error_count} raccourci{plural} de prompt")
    total = len(failures) + prompt_error_count
    title = "Raccourcis inactifs" if total > 1 else "Raccourci inactif"
    text = "\n".join(details) + "\nChoisissez-en un autre dans Réglages > Raccourcis."
    return title, text


class SuperMenu:
    def __init__(self):
        # Set application attributes
        QCoreApplication.setOrganizationName("SuperMenu")
        QCoreApplication.setApplicationName("SuperMenu")
        
        # Create application
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # Keep app running when windows are closed

        self._instance_server = None
        self._instance_mutex = None
        self._instance_mutex_owned = False
        self._should_exit = False
        self._services_closed = False
        self._startup_tray_attempts = 0
        if not self._ensure_single_instance():
            self._should_exit = True
            return
        
        # Load settings
        self.settings = Settings()
        
        # Initialize context menu manager first
        self.context_menu_manager = ContextMenuManager(self.settings)
        
        # Initialize hotkey manager
        self.hotkey_manager = HotkeyManager(self.settings)
        self.hotkey_manager.hotkey_triggered.connect(self.show_context_menu)

        # Initialize voice hotkey manager
        self.voice_hotkey_manager = HotkeyManager(self.settings, voice_hotkey=True)
        self.voice_hotkey_manager.voice_hotkey_triggered.connect(self.show_voice_menu)

        # Initialize custom mode hotkey manager
        self.custom_hotkey_manager = HotkeyManager(self.settings, custom_hotkey=True)
        self.custom_hotkey_manager.custom_hotkey_triggered.connect(self.show_custom_mode)
        
        # Initialize screenshot hotkey manager
        self.screenshot_hotkey_manager = HotkeyManager(self.settings, screenshot_hotkey=True)
        self.screenshot_hotkey_manager.screenshot_hotkey_triggered.connect(self.take_screenshot)

        # Prompt shortcuts are registered after the core shortcuts so a
        # conflicting prompt never disables an application-level command.
        self.dictation_hotkey_manager = HotkeyManager(self.settings, dictation_hotkey=True)
        self.dictation_hotkey_manager.dictation_shortcut.started.connect(self.context_menu_manager.start_instant_dictation)
        self.dictation_hotkey_manager.dictation_shortcut.released.connect(self.context_menu_manager.finish_instant_dictation)
        self.prompt_hotkey_manager = PromptHotkeyManager(self.settings)
        self.prompt_hotkey_manager.prompt_hotkey_triggered.connect(
            self.run_prompt_hotkey
        )

        # Initialize main window and pass all managers
        self.main_window = MainWindow(
            settings=self.settings, 
            context_menu_manager=self.context_menu_manager,
            hotkey_manager=self.hotkey_manager,
            voice_hotkey_manager=self.voice_hotkey_manager,
            screenshot_hotkey_manager=self.screenshot_hotkey_manager,
            custom_hotkey_manager=self.custom_hotkey_manager,
            prompt_hotkey_manager=self.prompt_hotkey_manager,
            dictation_hotkey_manager=self.dictation_hotkey_manager,
        )
        
        # Apply theme
        self.apply_theme()
        self.app.aboutToQuit.connect(self._close_services)
    
    def apply_theme(self):
        # Importer le gestionnaire de thèmes moderne
        from supermenu_core.ui.theme_manager import ThemeManager
        
        # Récupérer le thème depuis les paramètres
        theme = self.settings.get_theme()
        
        # Appliquer le thème moderne avec pyqtdarktheme
        ThemeManager.apply_theme(self.app, theme)
    
    def show_context_menu(self):
        """Show the context menu at the current cursor position"""
        try:
            self.context_menu_manager.show_menu()
        except KeyboardInterrupt:
            return
        except Exception as e:
            logger.exception(f"Erreur lors de l'affichage du menu contextuel: {e}")

    def run_prompt_hotkey(self, prompt_id):
        """Run one prompt directly from its own configured hotkey."""
        try:
            self.context_menu_manager.run_prompt_hotkey(prompt_id)
        except KeyboardInterrupt:
            return
        except Exception as e:
            logger.exception(f"Erreur lors du raccourci de prompt: {e}")
    
    def show_voice_menu(self):
        """Show only the voice interaction menu at the current cursor position"""
        try:
            self.context_menu_manager.show_voice_menu()
        except KeyboardInterrupt:
            return
        except Exception as e:
            logger.exception(f"Erreur lors de l'affichage du menu vocal: {e}")

    def show_custom_mode(self):
        """Show the custom mode workflow directly from its dedicated hotkey"""
        try:
            self.context_menu_manager.show_custom_mode()
        except KeyboardInterrupt:
            return
        except Exception as e:
            logger.exception(f"Erreur lors de l'affichage du mode personnalisé: {e}")
    
    def take_screenshot(self):
        """Take a screenshot"""
        self.context_menu_manager._handle_screenshot_action()
    
    def run(self):
        """Run the application"""
        if self._should_exit:
            return 0

        # Attendre que Qt et le shell Windows soient prêts avant d'afficher la zone de notification.
        QTimer.singleShot(250, self._finish_startup)
        
        # Run the application
        return self.app.exec()

    def _finish_startup(self):
        if self._should_exit or self.main_window is None:
            return

        self._startup_tray_attempts += 1
        if not self.main_window.tray_icon:
            if self.main_window.setup_tray_icon():
                # Démarrer réduit dans la zone de notification
                self._show_hidden_or_welcome()
                self.main_window.schedule_startup_update_check()
                self._report_hotkey_failures()
                return

            if self._startup_tray_attempts < 40:
                QTimer.singleShot(500, self._finish_startup)
                return

            log("Zone de notification indisponible au démarrage; affichage de la fenêtre principale.", logging.WARNING)
            self.main_window.show_main_window()
            self.main_window.schedule_startup_update_check()
            self._report_hotkey_failures()
            return

        # Démarrer réduit dans la zone de notification
        self._show_hidden_or_welcome()
        self.main_window.schedule_startup_update_check()
        self._report_hotkey_failures()

    def _show_hidden_or_welcome(self):
        """Start hidden, except on a brand-new installation.

        A first launch shows where to choose the AI engine and says how to
        open the menu, instead of disappearing into the notification area.
        """
        if not getattr(getattr(self, "settings", None), "first_launch", False):
            self.main_window.hide()
            return
        self.main_window.show_settings_page("text")
        tray_icon = getattr(self.main_window, "tray_icon", None)
        if tray_icon is not None:
            hotkey = self.settings.get_hotkey()
            tray_icon.showMessage(
                "SuperMenu est prêt",
                f"Sélectionnez du texte puis appuyez sur {hotkey}. "
                "Choisissez d’abord votre moteur IA dans les réglages.",
                QSystemTrayIcon.Information,
                10000,
            )

    def _report_hotkey_failures(self):
        """Signaler au démarrage les raccourcis que Windows a refusés.

        Sans cela, un raccourci par défaut absent du clavier ou déjà pris par
        une autre application laisse la fonction inactive sans aucun signe.
        """
        try:
            failures = _inactive_hotkeys((
                self.hotkey_manager,
                self.custom_hotkey_manager,
                self.voice_hotkey_manager,
                self.screenshot_hotkey_manager,
                self.dictation_hotkey_manager,
            ))
            prompt_errors = self.prompt_hotkey_manager.errors if self.prompt_hotkey_manager is not None else {}
            message = _hotkey_failure_message(failures, len(prompt_errors))
            if message is None:
                return
            title, text = message
            for name, hotkey, error in failures:
                log(f"Raccourci inactif au démarrage — {name} ({hotkey}) : {error}", logging.WARNING)
            tray_icon = getattr(self.main_window, "tray_icon", None)
            if tray_icon is not None and tray_icon.isVisible():
                tray_icon.showMessage(f"SuperMenu — {title}", text, QSystemTrayIcon.Warning, 10000)
            else:
                self.main_window.statusBar().showMessage(f"{title} — {text.splitlines()[0]}")
        except Exception as e:
            log(f"Impossible de signaler les raccourcis inactifs: {e}", logging.WARNING)

    def _ensure_single_instance(self):
        server_name = _instance_server_name()
        handle, already_running = _create_instance_mutex()
        self._instance_mutex = handle
        self._instance_mutex_owned = handle is not None and not already_running

        if handle is None or already_running:
            # Une instance tourne déjà : lui demander de s'afficher.
            if self._notify_running_instance(server_name):
                self._release_instance_lock()
                return False
            if handle is not None:
                # Elle ne répond pas : elle se ferme peut-être (redémarrage,
                # mise à jour). Attendre qu'elle libère le verrou.
                if not _wait_instance_mutex(handle, _INSTANCE_WAIT_MS):
                    log("Une autre instance de SuperMenu est déjà active.", logging.WARNING)
                    self._notify_running_instance(server_name)
                    self._release_instance_lock()
                    return False
                self._instance_mutex_owned = True
            # Sans verrou utilisable, le canal local reste la seule protection.

        self._instance_server = QLocalServer()
        if not self._instance_server.listen(server_name):
            QLocalServer.removeServer(server_name)
            if not self._instance_server.listen(server_name):
                return True

        self._instance_server.newConnection.connect(self._on_instance_connection)
        return True

    @staticmethod
    def _notify_running_instance(server_name):
        """Demande à l'instance active de s'afficher ; False si elle ne répond pas."""
        socket = QLocalSocket()
        socket.connectToServer(server_name)
        if not socket.waitForConnected(200):
            return False
        try:
            socket.write(b"show")
            socket.flush()
            socket.waitForBytesWritten(200)
        finally:
            socket.disconnectFromServer()
        return True

    def _release_instance_lock(self):
        handle, owned = self._instance_mutex, self._instance_mutex_owned
        self._instance_mutex = None
        self._instance_mutex_owned = False
        try:
            _close_instance_mutex(handle, owned)
        except Exception as e:
            log(f"Impossible de libérer le verrou d'instance: {e}", logging.WARNING)

    def _on_instance_connection(self):
        if self.main_window is None:
            return
        socket = self._instance_server.nextPendingConnection()
        if socket is None:
            return
        try:
            if socket.waitForReadyRead(200):
                data = bytes(socket.readAll()).decode(errors="ignore").strip().lower()
                if data == "show":
                    self.main_window.show_main_window()
        finally:
            socket.disconnectFromServer()

    def _close_services(self):
        if self._services_closed:
            return
        self._services_closed = True
        # Ne plus répondre « show » : une instance relancée doit pouvoir démarrer.
        if self._instance_server is not None:
            self._instance_server.close()
        try:
            for manager in (
                self.hotkey_manager,
                self.voice_hotkey_manager,
                self.screenshot_hotkey_manager,
                self.custom_hotkey_manager,
                self.prompt_hotkey_manager,
                self.dictation_hotkey_manager,
            ):
                manager.close()
        finally:
            # Raccourcis libérés : la nouvelle instance peut prendre le relais.
            self._release_instance_lock()
        self.context_menu_manager.close()

if __name__ == "__main__":
    app = SuperMenu()
    sys.exit(app.run())
