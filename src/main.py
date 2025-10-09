#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QIcon

from src.ui.main_window import MainWindow
from src.utils.context_menu import ContextMenuManager
from src.utils.hotkey_manager import HotkeyManager
from src.config.settings import Settings

class SuperMenu:
    def __init__(self):
        # Vérifier si le répertoire des icônes existe
        icons_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons")
        if not os.path.exists(icons_dir):
            os.makedirs(icons_dir, exist_ok=True)
        
        # Set application attributes
        QCoreApplication.setOrganizationName("SuperMenu")
        QCoreApplication.setApplicationName("SuperMenu")
        
        # Create application
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # Keep app running when windows are closed
        
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
        
        # Initialize screenshot hotkey manager
        self.screenshot_hotkey_manager = HotkeyManager(self.settings, screenshot_hotkey=True)
        self.screenshot_hotkey_manager.screenshot_hotkey_triggered.connect(self.take_screenshot)

        # Initialize main window and pass all managers
        self.main_window = MainWindow(
            settings=self.settings, 
            context_menu_manager=self.context_menu_manager,
            hotkey_manager=self.hotkey_manager,
            voice_hotkey_manager=self.voice_hotkey_manager,
            screenshot_hotkey_manager=self.screenshot_hotkey_manager
        )
        
        # Apply theme
        self.apply_theme()
    
    def apply_theme(self):
        # Importer la fonction apply_style depuis le module style
        from src.ui.style import apply_style
        
        # Appliquer le style unifié
        apply_style(self.app)
    
    def show_context_menu(self):
        """Show the context menu at the current cursor position"""
        try:
            self.context_menu_manager.show_menu()
        except Exception as e:
            import logging
            logging.error(f"Erreur lors de l'affichage du menu contextuel: {e}")
    
    def show_voice_menu(self):
        """Show only the voice interaction menu at the current cursor position"""
        try:
            self.context_menu_manager.show_voice_menu()
        except Exception as e:
            import logging
            logging.error(f"Erreur lors de l'affichage du menu vocal: {e}")
    
    def take_screenshot(self):
        """Take a screenshot"""
        self.context_menu_manager._handle_screenshot_action()
    
    def run(self):
        """Run the application"""
        # Show system tray icon
        self.main_window.setup_tray_icon()
        
        # Run the application
        return self.app.exec()

if __name__ == "__main__":
    app = SuperMenu()
    sys.exit(app.run())
