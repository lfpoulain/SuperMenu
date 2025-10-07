#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Indicateur de chargement visuel pour SuperMenu.
Affiche une notification non-bloquante pour les opérations longues.
"""
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QProgressBar
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont


class LoadingIndicator(QDialog):
    """Dialogue de chargement non-bloquant avec barre de progression."""
    
    # Signal émis quand l'indicateur est fermé
    closed = Signal()
    
    def __init__(self, message="Traitement en cours...", parent=None, show_progress=True):
        """
        Initialise l'indicateur de chargement.
        
        Args:
            message (str): Message à afficher
            parent: Widget parent (optionnel)
            show_progress (bool): Afficher la barre de progression indéterminée
        """
        super().__init__(parent)
        
        # Configuration de la fenêtre
        self.setWindowFlags(
            Qt.Window | 
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint |
            Qt.Tool  # Pas dans la barre des tâches
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setModal(False)  # Non-bloquant
        
        # Style moderne
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                border: 2px solid #3daee9;
                border-radius: 10px;
            }
            QLabel {
                color: #ffffff;
                background-color: transparent;
                padding: 10px;
            }
            QProgressBar {
                border: 1px solid #3daee9;
                border-radius: 5px;
                text-align: center;
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #3daee9;
                border-radius: 4px;
            }
        """)
        
        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)
        
        # Label du message
        self.label = QLabel(message)
        self.label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.label.setFont(font)
        layout.addWidget(self.label)
        
        # Barre de progression
        if show_progress:
            self.progress_bar = QProgressBar()
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(0)  # Mode indéterminé
            self.progress_bar.setFixedHeight(8)
            self.progress_bar.setTextVisible(False)
            layout.addWidget(self.progress_bar)
        else:
            self.progress_bar = None
        
        self.setLayout(layout)
        self.setFixedWidth(300)
        
        # Timer pour auto-fermeture (optionnel)
        self.auto_close_timer = None
    
    def set_message(self, message):
        """
        Met à jour le message affiché.
        
        Args:
            message (str): Nouveau message
        """
        if self.label:
            self.label.setText(message)
    
    def set_progress(self, value):
        """
        Définit la progression (0-100).
        
        Args:
            value (int): Valeur de progression (0-100)
        """
        if self.progress_bar:
            if self.progress_bar.maximum() == 0:
                # Passer en mode déterminé
                self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(value)
    
    def show_for(self, duration_ms):
        """
        Affiche l'indicateur pour une durée limitée.
        
        Args:
            duration_ms (int): Durée en millisecondes
        """
        self.show()
        if self.auto_close_timer:
            self.auto_close_timer.stop()
        
        self.auto_close_timer = QTimer()
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.timeout.connect(self.close)
        self.auto_close_timer.start(duration_ms)
    
    def show_centered(self):
        """Affiche l'indicateur au centre de l'écran."""
        self.show()
        # Centrer sur l'écran
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2
        )
    
    def closeEvent(self, event):
        """Émet le signal closed lors de la fermeture."""
        if self.auto_close_timer:
            self.auto_close_timer.stop()
        self.closed.emit()
        super().closeEvent(event)
    
    @staticmethod
    def show_loading(message="Traitement en cours...", parent=None):
        """
        Méthode statique pour créer et afficher rapidement un indicateur.
        
        Args:
            message (str): Message à afficher
            parent: Widget parent (optionnel)
            
        Returns:
            LoadingIndicator: Instance de l'indicateur
        """
        indicator = LoadingIndicator(message, parent)
        indicator.show_centered()
        return indicator


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
            Qt.Tool
        )
        self.setModal(False)
        
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
