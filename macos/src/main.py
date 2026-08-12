"""Application bootstrap for SuperMenu on macOS."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from src.config.settings import Settings
from src.ui.main_window import MainWindow
from src.ui.theme_manager import ThemeManager
from src.utils.context_menu import ContextMenuManager
from src.utils.hotkey_manager import HotkeyManager, PromptHotkeyManager
from src.utils.permissions import automation_permissions_are_trusted


class SuperMenu:
    def __init__(self):
        QCoreApplication.setOrganizationName("SuperMenu")
        QCoreApplication.setApplicationName("SuperMenu")

        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.main_window = None
        self._instance_server = None
        self._should_exit = False

        if not self._ensure_single_instance():
            self._should_exit = True
            return

        self.settings = Settings()
        self.context_menu_manager = ContextMenuManager(self.settings)
        self.hotkey_manager = HotkeyManager(self.settings)
        self.custom_hotkey_manager = HotkeyManager(
            self.settings,
            custom_hotkey=True,
        )
        self.prompt_hotkey_manager = PromptHotkeyManager(self.settings)

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
            logging.warning("La barre des menus est indisponible.")
            self.main_window.show_main_window()
        elif not automation_permissions_are_trusted():
            self.main_window.show_permission_setup()
        else:
            self.main_window.hide()
        self.main_window.schedule_startup_update_check()

    def show_context_menu(self):
        try:
            self.context_menu_manager.show_menu()
        except Exception as exc:
            logging.exception("Ouverture du menu impossible : %s", exc)

    def show_custom_mode(self):
        try:
            self.context_menu_manager.show_custom_mode()
        except Exception as exc:
            logging.exception("Ouverture du mode personnalisé impossible : %s", exc)

    def run_prompt_hotkey(self, prompt_id):
        try:
            self.context_menu_manager.run_prompt_hotkey(prompt_id)
        except Exception as exc:
            logging.exception("Exécution du prompt impossible : %s", exc)

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
                return True
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
        if self.context_menu_manager:
            self.context_menu_manager.close()
        for manager in (
            self.hotkey_manager,
            self.custom_hotkey_manager,
            self.prompt_hotkey_manager,
        ):
            manager.close()


if __name__ == "__main__":
    application = SuperMenu()
    sys.exit(application.run())
