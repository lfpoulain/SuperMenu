#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module de gestion moderne des thèmes avec pyqtdarktheme
"""

import qdarktheme
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QPalette

from supermenu_core.ui.verification_status import VerificationStatus
from supermenu_core.ui.theme_styles import ACCENT_COLORS, PALETTES, widget_styles


class ThemeManager:
    """Gestionnaire centralisé des thèmes de l'application"""

    # Thèmes disponibles
    THEMES = {"dark": "dark", "light": "light", "auto": "auto"}

    ACCENT_COLORS = ACCENT_COLORS

    @staticmethod
    def system_color_scheme() -> str:
        """Return the scheme the operating system is currently using.

        Qt 6.5 exposes this through QStyleHints; anything older, or a headless
        run without style hints, falls back to dark.
        """
        application = QGuiApplication.instance()
        hints = application.styleHints() if application is not None else None
        if hints is None or not hasattr(hints, "colorScheme"):
            return "dark"
        try:
            return "light" if hints.colorScheme() == Qt.ColorScheme.Light else "dark"
        except Exception:
            return "dark"

    @staticmethod
    def resolve_theme(theme: str) -> str:
        """Turn the stored preference into a scheme the stylesheet supports."""
        if theme not in ThemeManager.THEMES:
            theme = "dark"
        if theme == "auto":
            return ThemeManager.system_color_scheme()
        return theme

    @staticmethod
    def _follow_system_scheme(app: QApplication, follow: bool) -> None:
        """Re-apply the theme when the OS switches between light and dark."""
        application = QGuiApplication.instance()
        hints = application.styleHints() if application is not None else None
        changed = getattr(hints, "colorSchemeChanged", None) if hints else None
        if changed is None:
            return
        app.setProperty("supermenuFollowsSystem", follow)
        if follow and not app.property("supermenuThemeConnected"):
            changed.connect(
                lambda *_args: ThemeManager.apply_theme(app, "auto")
                if app.property("supermenuFollowsSystem") else None
            )
            app.setProperty("supermenuThemeConnected", True)

    @staticmethod
    def apply_theme(app: QApplication, theme: str = "dark"):
        """
        Applique un thème moderne à l'application

        Args:
            app: Instance de QApplication
            theme: "dark", "light" ou "auto"
        """
        requested = theme if theme in ThemeManager.THEMES else "dark"
        theme = ThemeManager.resolve_theme(requested)
        ThemeManager._follow_system_scheme(app, requested == "auto")

        # Qt supplies the platform's UI typeface; use a readable minimum size.
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
        font.setPointSizeF(max(10.5, font.pointSizeF()))

        # Charger le stylesheet de base
        stylesheet = qdarktheme.load_stylesheet(theme)

        # Ajouter nos styles personnalisés
        stylesheet += ThemeManager._get_custom_styles(theme, font.pointSizeF())
        stylesheet += VerificationStatus.stylesheet(theme)

        app.setFont(font)
        app.setStyleSheet(stylesheet)
        ThemeManager._apply_palette(app, theme)

    @staticmethod
    def _get_custom_styles(theme: str = "dark", font_size: float = 10.5) -> str:
        return widget_styles(theme, font_size)

    @staticmethod
    def _apply_palette(app: QApplication, theme: str):
        colours = PALETTES[theme]
        palette = qdarktheme.load_palette(theme)
        roles = {
            QPalette.Window: "canvas", QPalette.WindowText: "text",
            QPalette.Base: "field", QPalette.AlternateBase: "surface",
            QPalette.Text: "text", QPalette.Button: "surface",
            QPalette.ButtonText: "text", QPalette.Highlight: "selection",
            QPalette.HighlightedText: "selected_text", QPalette.PlaceholderText: "muted",
            QPalette.Link: "accent", QPalette.ToolTipBase: "surface",
            QPalette.ToolTipText: "text",
        }
        for role, token in roles.items():
            palette.setColor(role, QColor(colours[token]))
        for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
            palette.setColor(QPalette.Disabled, role, QColor(colours["disabled"]))
        app.setPalette(palette)

    @staticmethod
    def get_theme_names():
        """Retourne la liste des noms de thèmes disponibles"""
        return {"dark": "Sombre", "light": "Clair", "auto": "Automatique (Système)"}

    @staticmethod
    def get_accent_color(color_name: str = "primary") -> str:
        """Retourne une couleur d'accentuation"""
        return ThemeManager.ACCENT_COLORS.get(
            color_name, ThemeManager.ACCENT_COLORS["primary"]
        )
