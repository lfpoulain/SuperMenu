#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtGui import QIcon

from src.ui.main_window import MainWindow
from src.utils.context_menu import ContextMenuManager
from src.utils.hotkey_manager import HotkeyManager
from src.config.settings import Settings

class SuperMenu:
    def __init__(self):
        # Vérifier si le répertoire des icônes existe
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(__file__))

        icons_dir = os.path.join(base_dir, "resources", "icons")
        if not os.path.exists(icons_dir):
            try:
                os.makedirs(icons_dir, exist_ok=True)
            except Exception:
                pass
        
        # Set application attributes
        QCoreApplication.setOrganizationName("SuperMenu")
        QCoreApplication.setApplicationName("SuperMenu")
        
        # Create application
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # Keep app running when windows are closed

        self._instance_server = None
        self._should_exit = False
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

        # Initialize main window and pass all managers
        self.main_window = MainWindow(
            settings=self.settings, 
            context_menu_manager=self.context_menu_manager,
            hotkey_manager=self.hotkey_manager,
            voice_hotkey_manager=self.voice_hotkey_manager,
            screenshot_hotkey_manager=self.screenshot_hotkey_manager,
            custom_hotkey_manager=self.custom_hotkey_manager
        )
        
        # Apply theme
        self.apply_theme()
    
    def apply_theme(self):
        # Importer le gestionnaire de thèmes moderne
        from src.ui.theme_manager import ThemeManager
        
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
            import logging
            logging.error(f"Erreur lors de l'affichage du menu contextuel: {e}")
    
    def show_voice_menu(self):
        """Show only the voice interaction menu at the current cursor position"""
        try:
            self.context_menu_manager.show_voice_menu()
        except KeyboardInterrupt:
            return
        except Exception as e:
            import logging
            logging.error(f"Erreur lors de l'affichage du menu vocal: {e}")

    def show_custom_mode(self):
        """Show the custom mode workflow directly from its dedicated hotkey"""
        try:
            self.context_menu_manager.show_custom_mode()
        except KeyboardInterrupt:
            return
        except Exception as e:
            import logging
            logging.error(f"Erreur lors de l'affichage du mode personnalisé: {e}")
    
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
                self.main_window.hide()
                self.main_window.schedule_startup_update_check()
                return

            if self._startup_tray_attempts < 40:
                QTimer.singleShot(500, self._finish_startup)
                return

            logging.warning("Zone de notification indisponible au démarrage; affichage de la fenêtre principale.")
            self.main_window.show_main_window()
            self.main_window.schedule_startup_update_check()
            return

        # Démarrer réduit dans la zone de notification
        self.main_window.hide()
        self.main_window.schedule_startup_update_check()

    def _ensure_single_instance(self):
        server_name = "SuperMenuSingleInstance"

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
                data = bytes(socket.readAll()).decode(errors="ignore").strip().lower()
                if data == "show":
                    self.main_window.show_main_window()
        finally:
            socket.disconnectFromServer()

if __name__ == "__main__":
    app = SuperMenu()
    sys.exit(app.run())
