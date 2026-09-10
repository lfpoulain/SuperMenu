#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Fenêtre de réponse modernisée avec pyqtdarktheme
"""

import logging
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QApplication,
)
from PySide6.QtCore import Qt, QTimer, Signal

from supermenu_core.ui.controls import set_ui_property
from supermenu_core.utils.thinking import mask_thinking

logger = logging.getLogger("SuperMenu.core.ui")


class BaseResponseWindow(QWidget):
    """Window to display API responses"""

    # Signal émis quand l'utilisateur clique sur Réessayer
    retry_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("responseWindow")

        # Set window properties
        self.setWindowTitle("SuperMenu - Réponse")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)

        # Create the main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)

        # Create the content layout
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.addLayout(self.content_layout)

        # Create the title bar
        self.create_title_bar()

        # Create the response text area
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setMinimumSize(600, 400)
        self.response_text.setObjectName("responseText")
        self.content_layout.addWidget(self.response_text)

        # Create the status bar
        self.status_label = QLabel("Prêt")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.status_label)
        self._set_status("info")

        # Create the button bar
        self.create_button_bar()

        # Initialize the loading animation
        self.loading = False
        self.loading_dots = 0
        self.loading_timer = None

        # Variable pour stocker la position d'ouverture
        self.trigger_position = None

        # Variables pour stocker la dernière requête (pour retry)
        self.last_prompt = None
        self.last_content = None

        # Stockage des réponses avec/sans raisonnement
        self.raw_response = None
        self.masked_response = None
        self.final_response = None
        self.think_visible = False
        self.paste_target = None
        self._pending_paste_text = None
        self._active_text_inserter = None

    def _set_status(self, level):
        set_ui_property(self.status_label, "status", level)

    def create_title_bar(self):
        """Create the title bar"""
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 10)

        # Title
        self.title_label = QLabel("💬 Votre réponse")
        self.title_label.setObjectName("pageTitle")
        self.title_label.setWordWrap(False)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.content_layout.addWidget(header)

    def create_button_bar(self):
        """Create the button bar"""
        button_bar = QWidget()
        button_layout = QHBoxLayout(button_bar)
        button_layout.setSpacing(8)

        # Retry button
        self.retry_button = QPushButton("Réessayer")
        self.retry_button.setEnabled(False)
        self.retry_button.clicked.connect(self.retry_request)
        button_layout.addWidget(self.retry_button)

        # Copy button
        self.copy_button = QPushButton("Copier")
        self.copy_button.clicked.connect(self.copy_response)
        button_layout.addWidget(self.copy_button)

        # Toggle reasoning visibility
        self.think_toggle_button = QPushButton("Voir le raisonnement")
        self.think_toggle_button.clicked.connect(self.toggle_thinking_visibility)
        self.think_toggle_button.setVisible(False)
        button_layout.addWidget(self.think_toggle_button)

        # Write button
        button_layout.addStretch()
        self.write_button = QPushButton("Insérer le texte")
        self.write_button.setProperty("variant", "primary")
        self.write_button.clicked.connect(self.write_response)
        button_layout.addWidget(self.write_button)

        self.content_layout.addWidget(button_bar)

    def set_status(self, status):
        """Set the status message"""
        self.raw_response = None
        self.masked_response = None
        self.final_response = None
        self.think_visible = False
        self.think_toggle_button.setVisible(False)
        self.think_toggle_button.setEnabled(False)
        self.retry_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.write_button.setEnabled(False)
        self.response_text.setText(status)
        self.title_label.setText("⏳ SuperMenu - Chargement…")
        self.status_label.setText(status)

    def set_response(self, response):
        """Set the response text"""
        self.raw_response = response
        self.think_visible = False

        masked_response, has_thinking = self._mask_thinking(response)
        self.masked_response = masked_response
        self.final_response = masked_response if has_thinking else response

        display_text = response
        if has_thinking:
            display_text = (
                masked_response
                if masked_response
                else "(Aucune reponse finale; seul le raisonnement a ete renvoye.)"
            )
            self.think_toggle_button.setVisible(True)
            self.think_toggle_button.setEnabled(True)
            self.think_toggle_button.setText("Voir le raisonnement")
        else:
            self.think_toggle_button.setVisible(False)
            self.think_toggle_button.setEnabled(False)

        # setPlainText alone: setText auto-detects rich text, so a model answer
        # containing angle brackets was parsed as HTML before being discarded.
        self.response_text.setPlainText(display_text)
        self.title_label.setText("💬 Votre réponse")
        self.status_label.setText("✅ Terminé")
        self._set_status("success")
        self.retry_button.setEnabled(True)
        self.copy_button.setEnabled(True)
        self.write_button.setEnabled(True)

    def set_standalone_response(self, response, title="SuperMenu - Résultat"):
        """Display reusable plain text that did not come from an AI request."""
        text = str(response or "")
        self.last_prompt = None
        self.last_content = None
        self.raw_response = text
        self.masked_response = text
        self.final_response = text
        self.think_visible = False
        self.think_toggle_button.setVisible(False)
        self.think_toggle_button.setEnabled(False)
        self.response_text.setPlainText(text)
        self.title_label.setText(title)
        self.status_label.setText("✅ Terminé")
        self._set_status("success")
        self.retry_button.setEnabled(False)
        self.copy_button.setEnabled(bool(text))
        self.write_button.setEnabled(bool(text))

    def present(self):
        """Afficher la fenêtre de réponse de manière fiable."""
        self._prepare_presentation()
        self._show_normal()
        self._raise_to_front()
        QTimer.singleShot(75, self._raise_to_front)
        QTimer.singleShot(200, self._raise_to_front)

    def set_paste_target(self, target):
        self.paste_target = target

    def _prepare_presentation(self):
        """Hook executed before the platform presents the window."""

    def _create_text_inserter(self):
        """Return a platform adapter exposing insert_text_async()."""
        raise NotImplementedError

    def _show_normal(self):
        """Afficher la fenêtre sans la laisser minimisée."""
        state = self.windowState()
        state &= ~Qt.WindowMinimized
        state |= Qt.WindowActive
        self.setWindowState(state)
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()

    def _raise_to_front(self):
        """Présenter la fenêtre avec les API Qt natives de macOS."""
        self._raise_to_front_qt()

    def _raise_to_front_qt(self):
        """Mettre la fenêtre devant avec les API Qt."""
        if self.isMinimized():
            self.showNormal()
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()

    def _mask_thinking(self, response):
        """Masque le contenu <think>...</think> si présent."""
        return mask_thinking(response)

    def toggle_thinking_visibility(self):
        """Afficher ou masquer le raisonnement."""
        if not self.raw_response or self.masked_response is None:
            return

        self.think_visible = not self.think_visible
        if self.think_visible:
            self.response_text.setPlainText(self.raw_response)
            self.think_toggle_button.setText("Masquer le raisonnement")
        else:
            display_text = (
                self.masked_response
                if self.masked_response
                else "(Aucune reponse finale; seul le raisonnement a ete renvoye.)"
            )
            self.response_text.setPlainText(display_text)
            self.think_toggle_button.setText("Voir le raisonnement")

    def set_loading(self, is_loading):
        """Set the loading state"""
        if is_loading:
            self.title_label.setText("⏳ SuperMenu - Chargement...")
            self.status_label.setText("⏳ Traitement en cours...")
            self._set_status("info")
            self.retry_button.setEnabled(False)
            self.copy_button.setEnabled(False)
            self.write_button.setEnabled(False)
        else:
            self.retry_button.setEnabled(True)
            self.copy_button.setEnabled(True)
            self.write_button.setEnabled(True)

    def copy_response(self):
        """Copy the response to the clipboard"""
        QApplication.clipboard().setText(self.response_text.toPlainText())
        self.copy_button.setText("✅ Copié!")
        self.copy_button.setEnabled(False)

        # Reset the button text after a delay
        def reset_button():
            self.copy_button.setText("Copier")
            self.copy_button.setEnabled(True)

        QTimer.singleShot(2000, reset_button)

    def write_response(self):
        """Paste the final response only into the captured target control."""
        try:
            text = (
                self.final_response
                if self.final_response is not None
                else self.response_text.toPlainText()
            )
            if text:
                self._pending_paste_text = text
                self.hide()
                QTimer.singleShot(100, self._paste_text)
            else:
                self.status_label.setText("⚠️ Aucun texte à coller")
                self._set_status("warning")
        except Exception as e:
            self.status_label.setText(f"❌ Erreur: {str(e)}")
            self._set_status("error")

    def _paste_text(self):
        """Paste after macOS asynchronously reactivates the captured target."""
        try:
            text = self._pending_paste_text
            self._pending_paste_text = None
            if not text:
                return
            self.write_button.setEnabled(False)
            inserter = self._create_text_inserter()
            self._active_text_inserter = inserter

            def insertion_finished(success, reason):
                self._active_text_inserter = None
                self.write_button.setEnabled(True)
                if success:
                    return
                self.show()
                messages = {
                    "target_unavailable": (
                        "⚠️ L’application cible n’est plus disponible"
                    ),
                    "activation_failed": (
                        "⚠️ Impossible de réactiver l’application cible"
                    ),
                    "target_changed": (
                        "⚠️ Insertion annulée : l’application active a changé"
                    ),
                    "clipboard_failed": "⚠️ Presse-papiers indisponible",
                    "paste_failed": "⚠️ Commande Coller impossible",
                }
                self.status_label.setText(
                    messages.get(reason, "⚠️ Insertion impossible")
                )
                self._set_status("warning")

            inserter.insert_text_async(
                text,
                self.paste_target,
                insertion_finished,
            )
        except Exception:
            logger.exception("Erreur lors du collage")
            self._active_text_inserter = None
            self.write_button.setEnabled(True)
            self.show()
            self.status_label.setText("⚠️ Erreur interne pendant l’insertion")
            self._set_status("error")

    def retry_request(self):
        """Retry the API request"""
        if self.last_prompt is not None:
            self.status_label.setText("🔄 Réessai...")
            self._set_status("info")
            self.set_loading(True)
            self.retry_requested.emit()
        else:
            self.status_label.setText("⚠️ Aucune requête à réessayer")
            self._set_status("warning")

    def store_request(self, prompt, content):
        """Stocke les informations de la requête pour permettre un retry

        Args:
            prompt: Le prompt utilisé
            content: Le contenu texte
        """
        self.last_prompt = prompt
        self.last_content = content

    def get_last_request(self):
        """Retourne les informations de la dernière requête

        Returns:
            tuple: (prompt, content) ou (None, None) si pas de requête stockée
        """
        return self.last_prompt, self.last_content

    def showEvent(self, event):
        """Handle show event"""
        if self.trigger_position:
            # Utiliser la position du curseur ou de la fenêtre de dialogue
            screen = QApplication.screenAt(self.trigger_position)
            if not screen:
                screen = QApplication.primaryScreen()

            # Calculer la position optimale sur l'écran
            screen_geometry = screen.availableGeometry()
            window_geometry = self.frameGeometry()

            # Positionner la fenêtre près de la position de déclenchement, mais en s'assurant qu'elle reste visible
            x = max(
                screen_geometry.left(),
                min(
                    self.trigger_position.x() - window_geometry.width() // 2,
                    screen_geometry.right() - window_geometry.width(),
                ),
            )
            y = max(
                screen_geometry.top(),
                min(
                    self.trigger_position.y() - window_geometry.height() // 2,
                    screen_geometry.bottom() - window_geometry.height(),
                ),
            )

            self.move(x, y)
        else:
            # Comportement par défaut : centrer sur l'écran principal
            screen_geometry = QApplication.primaryScreen().geometry()
            window_geometry = self.frameGeometry()
            window_geometry.moveCenter(screen_geometry.center())
            self.move(window_geometry.topLeft())

        super().showEvent(event)

    def set_trigger_position(self, position):
        """Définir la position de déclenchement pour l'affichage de la fenêtre

        Args:
            position: QPoint représentant la position du curseur ou de la fenêtre de dialogue
        """
        self.trigger_position = position
