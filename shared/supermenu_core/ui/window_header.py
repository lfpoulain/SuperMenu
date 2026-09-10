"""Shared, compact identity for the desktop configuration windows."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel


class WindowHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 8)
        layout.setSpacing(12)
        mark = QLabel("S")
        mark.setObjectName("brandMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(42, 42)
        layout.addWidget(mark)
        identity = QVBoxLayout()
        identity.setSpacing(2)
        title = QLabel("SuperMenu")
        title.setObjectName("brandTitle")
        identity.addWidget(title)
        subtitle = QLabel("Un raccourci. Toutes vos idées.")
        subtitle.setObjectName("mutedText")
        identity.addWidget(subtitle)
        layout.addLayout(identity)
        layout.addStretch()
