#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module de gestion moderne des thèmes avec pyqtdarktheme
"""

import qdarktheme
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor

class ThemeManager:
    """Gestionnaire centralisé des thèmes de l'application"""
    
    # Thèmes disponibles
    THEMES = {
        "dark": "dark",
        "light": "light",
        "auto": "auto"
    }
    
    # Couleurs personnalisées pour SuperMenu
    ACCENT_COLORS = {
        "primary": "#3498db",      # Bleu
        "success": "#2ecc71",      # Vert
        "warning": "#f39c12",      # Orange
        "danger": "#e74c3c",       # Rouge
        "info": "#9b59b6"          # Violet
    }
    
    @staticmethod
    def apply_theme(app: QApplication, theme: str = "dark"):
        """
        Applique un thème moderne à l'application
        
        Args:
            app: Instance de QApplication
            theme: "dark", "light" ou "auto"
        """
        if theme not in ThemeManager.THEMES:
            theme = "dark"
        
        # Pour pyqtdarktheme 0.1.x, on utilise load_stylesheet
        # "auto" n'est pas supporté dans cette version, on utilise "dark" par défaut
        if theme == "auto":
            theme = "dark"
        
        # Charger le stylesheet de base
        stylesheet = qdarktheme.load_stylesheet(theme)
        
        # Ajouter nos styles personnalisés
        stylesheet += ThemeManager._get_custom_styles()
        
        # Appliquer le stylesheet
        app.setStyleSheet(stylesheet)
        
        # Appliquer les couleurs personnalisées
        if theme == "dark":
            ThemeManager._apply_dark_palette(app)
        elif theme == "light":
            ThemeManager._apply_light_palette(app)
    
    @staticmethod
    def _get_custom_styles() -> str:
        """Retourne les styles CSS personnalisés pour SuperMenu"""
        return f"""
        /* Amélioration des boutons */
        QPushButton {{
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 500;
            min-width: 80px;
            background-color: rgba(52, 152, 219, 0.15);
            border: 1px solid rgba(52, 152, 219, 0.3);
        }}
        
        QPushButton:hover {{
            background-color: rgba(52, 152, 219, 0.25);
            border: 2px solid {ThemeManager.ACCENT_COLORS["primary"]};
        }}
        
        QPushButton:pressed {{
            background-color: rgba(52, 152, 219, 0.35);
        }}
        
        QPushButton:default {{
            background-color: {ThemeManager.ACCENT_COLORS["primary"]};
            color: white;
            border: 1px solid {ThemeManager.ACCENT_COLORS["primary"]};
        }}
        
        QPushButton:default:hover {{
            background-color: #2980b9;
            border: 2px solid #2980b9;
        }}
        
        /* Amélioration des champs de saisie */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            padding: 8px;
            border-radius: 6px;
            border: 1px solid rgba(52, 152, 219, 0.3);
        }}
        
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border: 2px solid {ThemeManager.ACCENT_COLORS["primary"]};
        }}
        
        /* Amélioration des ComboBox */
        QComboBox {{
            padding: 6px 12px;
            border-radius: 6px;
            min-width: 150px;
        }}
        
        QComboBox:hover {{
            border: 2px solid {ThemeManager.ACCENT_COLORS["primary"]};
        }}
        
        /* Amélioration des GroupBox */
        QGroupBox {{
            font-weight: 600;
            border: 2px solid rgba(52, 152, 219, 0.2);
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 12px;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 4px 8px;
            border-radius: 4px;
            background-color: {ThemeManager.ACCENT_COLORS["primary"]};
            color: white;
        }}
        
        /* Amélioration des onglets */
        QTabWidget::pane {{
            border: 1px solid rgba(52, 152, 219, 0.3);
            border-radius: 8px;
            top: -1px;
        }}
        
        QTabBar::tab {{
            padding: 10px 20px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 4px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {ThemeManager.ACCENT_COLORS["primary"]};
            color: white;
            font-weight: 600;
        }}
        
        QTabBar::tab:hover:!selected {{
            background-color: rgba(52, 152, 219, 0.2);
        }}
        
        /* Amélioration des ScrollBars */
        QScrollBar:vertical {{
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {ThemeManager.ACCENT_COLORS["primary"]};
            min-height: 30px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: #2980b9;
        }}
        
        /* Amélioration des CheckBox */
        QCheckBox::indicator {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
        }}
        
        QCheckBox::indicator:checked {{
            background-color: {ThemeManager.ACCENT_COLORS["primary"]};
            border: 2px solid {ThemeManager.ACCENT_COLORS["primary"]};
        }}
        
        /* Amélioration des SpinBox */
        QSpinBox {{
            padding: 6px;
            border-radius: 6px;
        }}
        
        /* Amélioration des menus contextuels */
        QMenu {{
            border-radius: 8px;
            padding: 4px;
        }}
        
        QMenu::item {{
            padding: 8px 24px;
            border-radius: 4px;
            margin: 2px 4px;
        }}
        
        QMenu::item:selected {{
            background-color: {ThemeManager.ACCENT_COLORS["primary"]};
            color: white;
        }}
        
        QMenu::separator {{
            height: 1px;
            margin: 6px 10px;
        }}
        
        /* Style pour les fenêtres de dialogue */
        QDialog {{
            border-radius: 10px;
        }}
        
        /* Style pour les frames d'images */
        QFrame#imageFrame {{
            border-radius: 8px;
            padding: 5px;
        }}
        
        /* Style pour les messages d'état */
        QLabel[status="success"] {{
            color: {ThemeManager.ACCENT_COLORS["success"]};
            font-weight: 600;
        }}
        
        QLabel[status="warning"] {{
            color: {ThemeManager.ACCENT_COLORS["warning"]};
            font-weight: 600;
        }}
        
        QLabel[status="error"] {{
            color: {ThemeManager.ACCENT_COLORS["danger"]};
            font-weight: 600;
        }}
        
        QLabel[status="info"] {{
            color: {ThemeManager.ACCENT_COLORS["info"]};
            font-weight: 600;
        }}
        """
    
    @staticmethod
    def _apply_dark_palette(app: QApplication):
        """Applique une palette sombre personnalisée"""
        palette = app.palette()
        palette.setColor(QPalette.Highlight, QColor(ThemeManager.ACCENT_COLORS["primary"]))
        palette.setColor(QPalette.HighlightedText, QColor(Qt.white))
        app.setPalette(palette)
    
    @staticmethod
    def _apply_light_palette(app: QApplication):
        """Applique une palette claire personnalisée"""
        palette = app.palette()
        palette.setColor(QPalette.Highlight, QColor(ThemeManager.ACCENT_COLORS["primary"]))
        palette.setColor(QPalette.HighlightedText, QColor(Qt.white))
        app.setPalette(palette)
    
    @staticmethod
    def get_theme_names():
        """Retourne la liste des noms de thèmes disponibles"""
        return {
            "dark": "Sombre",
            "light": "Clair",
            "auto": "Automatique (Système)"
        }
    
    @staticmethod
    def get_accent_color(color_name: str = "primary") -> str:
        """Retourne une couleur d'accentuation"""
        return ThemeManager.ACCENT_COLORS.get(color_name, ThemeManager.ACCENT_COLORS["primary"])
