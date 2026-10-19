"""Shared, compact identity for the desktop configuration windows."""

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel


class WindowHeader(QWidget):
    def __init__(self, parent=None, *, icon=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 2)
        layout.setSpacing(10)
        mark = QLabel()
        mark.setObjectName("brandLogo")
        mark.setAccessibleName("Logo SuperMenu")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(40, 40)
        logo = icon if icon is not None else QIcon()
        mark.setPixmap(logo.pixmap(QSize(40, 40), self.devicePixelRatioF()))
        mark.setVisible(not logo.isNull())
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
