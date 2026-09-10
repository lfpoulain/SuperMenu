"""Common configuration window; platform code supplies pages and callbacks."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton

from .window_header import WindowHeader


def close_footer(callback):
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addStretch()
    button = QPushButton("Fermer")
    button.setAutoDefault(False)
    button.clicked.connect(callback)
    layout.addWidget(button)
    return layout


class ConfigurationShell(QWidget):
    def __init__(self, window, icon):
        super().__init__(window)
        window.setWindowTitle("SuperMenu - Configuration")
        window.setMinimumSize(820, 620)
        window.resize(1000, 720)
        window.setWindowIcon(icon)
        self.setObjectName("desktopRoot")
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(16, 12, 16, 12)
        self.content_layout.setSpacing(8)
        self.content_layout.addWidget(WindowHeader(icon=icon))
        self.tabs = QTabWidget()
        self.tabs.setObjectName("configurationTabs")
        self.tabs.setDocumentMode(False)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.content_layout.addWidget(self.tabs, 1)
        window.setCentralWidget(self)
