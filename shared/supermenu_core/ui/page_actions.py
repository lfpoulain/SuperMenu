"""Page-scoped actions with stable placement on both desktop platforms."""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton


class PageActions(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pageActions")
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(0, 8, 0, 0)
        self.row.setSpacing(8)
        self.row.addStretch()

    def add_action(self, label, callback, *, primary=False):
        button = QPushButton(label)
        button.setAutoDefault(False)
        button.setMinimumWidth(110)
        if primary:
            button.setProperty("variant", "primary")
        button.clicked.connect(callback)
        self.row.addWidget(button)
        return button
