#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Indicateur de chargement visuel pour SuperMenu.
Affiche une notification non-bloquante pour les opérations longues.
"""
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QTimer


class SimpleLoadingIndicator(QDialog):
    """Version simplifiée sans barre de progression (plus légère)."""
    
    def __init__(self, message="⏳ Chargement...", parent=None):
        """
        Initialise l'indicateur simple.
        
        Args:
            message (str): Message à afficher (peut inclure des emojis)
            parent: Widget parent (optionnel)
        """
        super().__init__(parent)
        
        # Configuration minimaliste
        self.setWindowFlags(
            Qt.Window | 
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowDoesNotAcceptFocus
        )
        self.setModal(False)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        
        # Style compact
        self.setStyleSheet("""
            QDialog {
                background-color: rgba(43, 43, 43, 230);
                border: 2px solid #3daee9;
                border-radius: 8px;
            }
            QLabel {
                color: #ffffff;
                font-size: 11pt;
                padding: 8px 15px;
            }
        """)
        
        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel(message)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        
        self.setLayout(layout)
        self.adjustSize()
    
    def set_message(self, message):
        """Met à jour le message."""
        self.label.setText(message)
        self.adjustSize()

    def move_near_cursor(self):
        """Place the compact indicator near the cursor without leaving the screen."""
        from PySide6.QtGui import QCursor, QGuiApplication

        cursor = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
        if screen is None:
            return

        area = screen.availableGeometry()
        x = min(cursor.x() + 18, area.right() - self.width())
        y = min(cursor.y() + 22, area.bottom() - self.height())
        self.move(max(area.left(), x), max(area.top(), y))
    
    @staticmethod
    def show_simple(message="⏳ Chargement...", duration_ms=None):
        """
        Affiche un indicateur simple.
        
        Args:
            message (str): Message à afficher
            duration_ms (int): Durée d'affichage (None = manuel)
            
        Returns:
            SimpleLoadingIndicator: Instance de l'indicateur
        """
        indicator = SimpleLoadingIndicator(message)
        
        # Centrer sur l'écran
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        indicator.move(
            screen.center().x() - indicator.width() // 2,
            screen.center().y() - indicator.height() // 2
        )
        
        indicator.show()
        
        # Auto-fermeture si demandé
        if duration_ms:
            QTimer.singleShot(duration_ms, indicator.close)
        
        return indicator

    @staticmethod
    def show_near_cursor(message="⏳ Chargement...", duration_ms=None):
        """Show a small, non-blocking notification close to the active selection."""
        indicator = SimpleLoadingIndicator(message)
        indicator.move_near_cursor()
        indicator.show()

        if duration_ms:
            QTimer.singleShot(duration_ms, indicator.close)

        return indicator
