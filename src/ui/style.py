#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module de gestion des styles et thèmes pour SuperMenu
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt

# Palettes de couleurs
DARK_PALETTE = {
    "primary": "#3498db",      # Bleu
    "secondary": "#2ecc71",    # Vert
    "accent": "#9b59b6",       # Violet
    "background": "#2c3e50",   # Bleu foncé
    "card": "#34495e",         # Bleu-gris
    "text": "#ecf0f1",         # Blanc cassé
    "text_secondary": "#bdc3c7" # Gris clair
}

# Palette de couleurs pour le thème abeille
BEE_PALETTE = {
    "primary": "#FFC107",      # Jaune ambre
    "secondary": "#FFD54F",    # Jaune ambre clair
    "accent": "#FF6F00",       # Ambre foncé
    "background": "#212121",   # Noir
    "card": "#424242",         # Gris foncé
    "text": "#FFFFFF",         # Blanc
    "text_secondary": "#BDBDBD" # Gris clair
}

# Styles CSS pour les différents thèmes
COMMON_STYLE = """
QMainWindow, QDialog {
    font-family: 'Segoe UI', Arial, sans-serif;
}

QPushButton {
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
}

QPushButton:hover {
    opacity: 0.8;
}

QLineEdit, QTextEdit, QComboBox {
    padding: 8px;
    border-radius: 4px;
    border: 1px solid palette(mid);
}

QTabWidget::pane {
    border: 1px solid palette(mid);
    border-radius: 4px;
}

QTabBar::tab {
    padding: 8px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    font-weight: bold;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid palette(mid);
    border-radius: 4px;
    margin-top: 16px;
    padding-top: 16px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 5px;
}
"""

DARK_STYLE = f"""
QMainWindow, QDialog, QWidget {{
    background-color: {DARK_PALETTE["background"]};
    color: {DARK_PALETTE["text"]};
}}

QPushButton {{
    background-color: {DARK_PALETTE["primary"]};
    color: {DARK_PALETTE["text"]};
    border: none;
}}

QPushButton:hover {{
    background-color: #2980b9;
}}

QPushButton:pressed {{
    background-color: #1f6dad;
}}

QPushButton:disabled {{
    background-color: #34495e;
    color: #7f8c8d;
}}

QLineEdit, QTextEdit, QComboBox {{
    background-color: {DARK_PALETTE["card"]};
    color: {DARK_PALETTE["text"]};
    border: 1px solid #546e7a;
}}

QTabWidget::pane {{
    background-color: {DARK_PALETTE["card"]};
    border: 1px solid #546e7a;
}}

QTabBar::tab {{
    background-color: {DARK_PALETTE["background"]};
    color: {DARK_PALETTE["text"]};
}}

QTabBar::tab:selected {{
    background-color: {DARK_PALETTE["primary"]};
    color: {DARK_PALETTE["text"]};
}}

QGroupBox {{
    border: 1px solid #546e7a;
}}

QLabel {{
    color: {DARK_PALETTE["text"]};
}}

QCheckBox {{
    color: {DARK_PALETTE["text"]};
}}

QMenu {{
    background-color: {DARK_PALETTE["card"]};
    color: {DARK_PALETTE["text"]};
    border: 1px solid #546e7a;
    border-radius: 6px;
    padding: 5px;
}}

QMenu::item {{
    padding: 8px 24px;
    border-radius: 4px;
    margin: 2px 4px;
}}

QMenu::item:selected {{
    background-color: {DARK_PALETTE["primary"]};
    color: white;
}}

QMenu::separator {{
    height: 1px;
    background-color: #546e7a;
    margin: 5px 10px;
}}

QScrollBar:vertical {{
    background-color: {DARK_PALETTE["background"]};
    width: 12px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: {DARK_PALETTE["primary"]};
    min-height: 20px;
    border-radius: 6px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""

# Style pour le thème abeille
BEE_STYLE = f"""
QMainWindow, QDialog, QWidget {{
    background-color: {BEE_PALETTE["background"]};
    color: {BEE_PALETTE["text"]};
}}

QPushButton {{
    background-color: {BEE_PALETTE["primary"]};
    color: black;
    border: none;
}}

QPushButton:hover {{
    background-color: {BEE_PALETTE["secondary"]};
}}

QPushButton:pressed {{
    background-color: {BEE_PALETTE["accent"]};
}}

QPushButton:disabled {{
    background-color: #424242;
    color: #757575;
}}

QLineEdit, QTextEdit, QComboBox {{
    background-color: {BEE_PALETTE["card"]};
    color: {BEE_PALETTE["text"]};
    border: 1px solid #757575;
}}

QTabWidget::pane {{
    background-color: {BEE_PALETTE["card"]};
    border: 1px solid #757575;
}}

QTabBar::tab {{
    background-color: {BEE_PALETTE["background"]};
    color: {BEE_PALETTE["text"]};
}}

QTabBar::tab:selected {{
    background-color: {BEE_PALETTE["primary"]};
    color: black;
}}

QGroupBox {{
    border: 1px solid #757575;
}}

QLabel {{
    color: {BEE_PALETTE["text"]};
}}

QCheckBox {{
    color: {BEE_PALETTE["text"]};
}}

QMenu {{
    background-color: {BEE_PALETTE["card"]};
    color: {BEE_PALETTE["text"]};
    border: 1px solid #757575;
    border-radius: 6px;
    padding: 5px;
}}

QMenu::item {{
    padding: 8px 24px;
    border-radius: 4px;
    margin: 2px 4px;
}}

QMenu::item:selected {{
    background-color: {BEE_PALETTE["primary"]};
    color: black;
}}

QMenu::separator {{
    height: 1px;
    background-color: #757575;
    margin: 5px 10px;
}}

QScrollBar:vertical {{
    background-color: {BEE_PALETTE["background"]};
    width: 12px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: {BEE_PALETTE["primary"]};
    min-height: 20px;
    border-radius: 6px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""

def get_dark_stylesheet():
    return COMMON_STYLE + DARK_STYLE

def get_bee_stylesheet():
    return COMMON_STYLE + BEE_STYLE

def apply_theme(app, theme="dark"):
    """Applique le thème à l'application entière
    
    Args:
        app: L'instance QApplication
        theme: Le thème à appliquer ('dark' ou 'bee')
    """
    if theme == "bee":
        stylesheet = get_bee_stylesheet()
    else:
        stylesheet = get_dark_stylesheet()
    app.setStyleSheet(stylesheet)

def get_style_sheet(theme="dark"):
    """Retourne la feuille de style pour le thème spécifié
    
    Args:
        theme: Le thème à utiliser ('dark' ou 'bee')
    
    Returns:
        str: La feuille de style CSS
    """
    if theme == "bee":
        return COMMON_STYLE + BEE_STYLE
    return COMMON_STYLE + DARK_STYLE
