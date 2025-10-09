#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module de gestion du style pour SuperMenu
Style moderne et sombre unifié
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt

# Palette de couleurs unique
COLORS = {
    "primary": "#3498db",      # Bleu
    "primary_hover": "#2980b9", # Bleu hover
    "primary_pressed": "#1f6dad", # Bleu pressed
    "secondary": "#2ecc71",    # Vert
    "accent": "#9b59b6",       # Violet
    "background": "#2c3e50",   # Bleu foncé
    "card": "#34495e",         # Bleu-gris
    "card_dark": "#2a2d3e",    # Bleu-gris plus foncé
    "border": "#546e7a",       # Bordure
    "text": "#ecf0f1",         # Blanc cassé
    "text_secondary": "#bdc3c7", # Gris clair
    "text_dim": "#7f8c8d",     # Gris foncé
    "success": "#2ecc71",      # Vert succès
    "warning": "#f39c12",      # Orange warning
    "error": "#e74c3c"         # Rouge erreur
}

# Style unifié moderne et sombre
APP_STYLESHEET = f"""
/* === Base === */
QMainWindow, QDialog, QWidget {{
    background-color: {COLORS["background"]};
    color: {COLORS["text"]};
    font-family: 'Segoe UI', Arial, sans-serif;
}}

/* === Boutons === */
QPushButton {{
    background-color: {COLORS["primary"]};
    color: {COLORS["text"]};
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: {COLORS["primary_hover"]};
}}

QPushButton:pressed {{
    background-color: {COLORS["primary_pressed"]};
}}

QPushButton:disabled {{
    background-color: {COLORS["card"]};
    color: {COLORS["text_dim"]};
}}

/* === Champs de saisie === */
QLineEdit, QTextEdit, QComboBox {{
    background-color: {COLORS["card"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 8px;
    selection-background-color: {COLORS["primary"]};
    selection-color: white;
}}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {COLORS["primary"]};
}}

QTextEdit {{
    font-size: 13px;
}}

/* === ComboBox === */
QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid {COLORS["text"]};
    margin-right: 4px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS["card"]};
    color: {COLORS["text"]};
    selection-background-color: {COLORS["primary"]};
    border: 1px solid {COLORS["border"]};
}}

/* === Onglets === */
QTabWidget::pane {{
    background-color: {COLORS["card"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
}}

QTabBar::tab {{
    background-color: {COLORS["background"]};
    color: {COLORS["text"]};
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}

QTabBar::tab:selected {{
    background-color: {COLORS["primary"]};
    color: {COLORS["text"]};
    font-weight: bold;
}}

QTabBar::tab:hover {{
    background-color: {COLORS["card"]};
}}

/* === GroupBox === */
QGroupBox {{
    color: {COLORS["text"]};
    font-weight: bold;
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    margin-top: 16px;
    padding-top: 16px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 5px;
}}

/* === Labels === */
QLabel {{
    color: {COLORS["text"]};
}}

/* === CheckBox === */
QCheckBox {{
    color: {COLORS["text"]};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {COLORS["border"]};
    border-radius: 3px;
    background-color: {COLORS["card"]};
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS["primary"]};
    border-color: {COLORS["primary"]};
}}

/* === SpinBox === */
QSpinBox {{
    background-color: {COLORS["card"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 4px 8px;
}}

/* === Menu contextuel === */
QMenu {{
    background-color: {COLORS["card"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 5px;
}}

QMenu::item {{
    padding: 8px 24px;
    border-radius: 4px;
    margin: 2px 4px;
}}

QMenu::item:selected {{
    background-color: {COLORS["primary"]};
    color: white;
}}

QMenu::separator {{
    height: 1px;
    background-color: {COLORS["border"]};
    margin: 5px 10px;
}}

/* === ScrollBar === */
QScrollBar:vertical {{
    background-color: {COLORS["background"]};
    width: 12px;
    margin: 0px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS["primary"]};
    min-height: 20px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS["primary_hover"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {COLORS["background"]};
    height: 12px;
    margin: 0px;
    border-radius: 6px;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS["primary"]};
    min-width: 20px;
    border-radius: 6px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLORS["primary_hover"]};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* === ProgressDialog === */
QProgressDialog {{
    background-color: {COLORS["background"]};
    color: {COLORS["text"]};
}}
"""

def apply_style(app):
    """Applique le style unifié à l'application
    
    Args:
        app: L'instance QApplication
    """
    app.setStyleSheet(APP_STYLESHEET)

def get_stylesheet():
    """Retourne la feuille de style
    
    Returns:
        str: La feuille de style CSS
    """
    return APP_STYLESHEET
