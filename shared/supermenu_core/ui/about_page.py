"""Shared product information and links; callbacks keep OS actions local."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton


class AboutPage(QWidget):
    def __init__(self, version, open_releases, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        for text, name in (
            ("SuperMenu", "aboutTitle"),
            (f"Version {version}", "mutedText"),
            ("Corrigez, reformulez, traduisez et dictez depuis vos applications.\n"
             "Retrouvez vos prompts et choisissez votre moteur IA dans les réglages.", "mutedText"),
            ("Développé par LFPoulain avec ❤️", "mutedText"),
        ):
            label = QLabel(text)
            label.setObjectName(name)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
        button = QPushButton("Voir les versions publiées")
        button.clicked.connect(open_releases)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
