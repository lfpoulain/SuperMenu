"""Application bootstrap for SuperMenu on macOS."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Slot
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from src.config.build_info import APP_VERSION
from src.config.settings import Settings
from src.ui.main_window import MainWindow
from src.ui.theme_manager import ThemeManager
from src.utils.context_menu import ContextMenuManager
from src.utils.hotkey_manager import (
    HotkeyManager,
    HotkeyService,
    PromptHotkeyManager,
)
from src.utils.logger import LOG_FILE, install_crash_reporting, log, logger
from src.utils.permissions import automation_permissions_are_trusted


class SuperMenu(QObject):
    def __init__(self):
        install_crash_reporting()
        log(f"Démarrage de SuperMenu macOS {APP_VERSION} — journal : {LOG_FILE}")
        QCoreApplication.setOrganizationName("SuperMenu")
        QCoreApplication.setApplicationName("SuperMenu")

        self.app = QApplication(sys.argv)
        super().__init__()
        self.app.setQuitOnLastWindowClosed(False)
        self.main_window = None
        self._instance_server = None
        self._should_exit = False
        self._services_closed = False

        if not self._ensure_single_instance():
            self._should_exit = True
            return

        self.settings = Settings()
        self.context_menu_manager = ContextMenuManager(self.settings)
        self.hotkey_service = HotkeyService()
        self.hotkey_manager = HotkeyManager(
            self.settings,
            service=self.hotkey_service,
        )
        self.custom_hotkey_manager = HotkeyManager(
            self.settings,
            custom_hotkey=True,
            service=self.hotkey_service,
        )
        self.prompt_hotkey_manager = PromptHotkeyManager(
            self.settings,
            service=self.hotkey_service,
        )

        self.hotkey_manager.hotkey_triggered.connect(self.show_context_menu)
        self.custom_hotkey_manager.custom_hotkey_triggered.connect(
            self.show_custom_mode
        )
        self.prompt_hotkey_manager.prompt_hotkey_triggered.connect(
            self.run_prompt_hotkey
        )

        self.main_window = MainWindow(
            settings=self.settings,
            context_menu_manager=self.context_menu_manager,
            hotkey_manager=self.hotkey_manager,
            custom_hotkey_manager=self.custom_hotkey_manager,
            prompt_hotkey_manager=self.prompt_hotkey_manager,
        )
        ThemeManager.apply_theme(self.app, self.settings.get_theme())
        self.app.aboutToQuit.connect(self._close_services)

    def run(self):
        if self._should_exit:
            return 0
        QTimer.singleShot(200, self._finish_startup)
        return self.app.exec()

    def _finish_startup(self):
        if self.main_window is None:
            return
        if not self.main_window.setup_tray_icon():
            logger.warning("La barre des menus est indisponible.")
            self.main_window.show_main_window()
        elif not automation_permissions_are_trusted():
            self.main_window.show_permission_setup()
        else:
            self.main_window.hide()
        self.main_window.schedule_startup_update_check()

    @Slot()
    def show_context_menu(self):
        log(
            "Raccourci délivré au thread Qt : menu principal "
            f"({self.hotkey_manager.hotkey})"
        )
        try:
            # Activating SuperMenu is required for a reliable Qt popup on
            # macOS, but AppKit also orders the application's main/key window
            # to the front. Remove the configuration window from the screen
            # first so the global shortcut presents only the prompt menu.
            if self.main_window is not None and self.main_window.isVisible():
                self.main_window.hide()
                log(
                    "Fenêtre de configuration masquée avant le menu global"
                )
            self.context_menu_manager.show_menu()
        except Exception as exc:
            logger.exception("Ouverture du menu impossible : %s", exc)

    @Slot()
    def show_custom_mode(self):
        log(
            "Raccourci délivré au thread Qt : mode personnalisé "
            f"({self.custom_hotkey_manager.hotkey})"
        )
        try:
            self.context_menu_manager.show_custom_mode()
        except Exception as exc:
            logger.exception("Ouverture du mode personnalisé impossible : %s", exc)

    @Slot(str)
    def run_prompt_hotkey(self, prompt_id):
        log("Raccourci délivré au thread Qt : prompt direct")
        try:
            self.context_menu_manager.run_prompt_hotkey(prompt_id)
        except Exception as exc:
            logger.exception("Exécution du prompt impossible : %s", exc)

    def _ensure_single_instance(self):
        server_name = "SuperMenuMacSingleInstance"
        socket = QLocalSocket()
        socket.connectToServer(server_name)
        if socket.waitForConnected(200):
            try:
                socket.write(b"show")
                socket.flush()
                socket.waitForBytesWritten(200)
            finally:
                socket.disconnectFromServer()
            return False

        self._instance_server = QLocalServer()
        if not self._instance_server.listen(server_name):
            QLocalServer.removeServer(server_name)
            if not self._instance_server.listen(server_name):
                log(
                    "Impossible de garantir l’instance unique ; démarrage annulé.",
                    logging.ERROR,
                )
                return False
        self._instance_server.newConnection.connect(self._on_instance_connection)
        return True

    def _on_instance_connection(self):
        if self.main_window is None:
            return
        socket = self._instance_server.nextPendingConnection()
        if socket is None:
            return
        try:
            if socket.waitForReadyRead(200):
                message = bytes(socket.readAll()).decode(errors="ignore").strip()
                if message == "show":
                    self.main_window.show_main_window()
        finally:
            socket.disconnectFromServer()

    def _close_services(self):
        if self._services_closed:
            return
        self._services_closed = True
        if self.context_menu_manager:
            self.context_menu_manager.close()
        for manager in (
            self.hotkey_manager,
            self.custom_hotkey_manager,
            self.prompt_hotkey_manager,
        ):
            manager.close()
        self.hotkey_service.close()


if __name__ == "__main__":
    application = SuperMenu()
    sys.exit(application.run())
