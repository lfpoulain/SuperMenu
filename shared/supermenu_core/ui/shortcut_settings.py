"""Shared shortcut rows; native registration is supplied by the platform."""

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLineEdit, QPushButton

from .settings_panel import form_layout


class ShortcutSettings(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Raccourcis clavier", parent)
        self.form = form_layout(self)

    def add_shortcut(self, label, value, record):
        row = QHBoxLayout()
        row.setSpacing(8)
        field = QLineEdit(value)
        field.setReadOnly(True)
        row.addWidget(field, 1)
        button = QPushButton("Définir")
        button.clicked.connect(record)
        row.addWidget(button)
        self.form.addRow(label, row)
        return field

    def add_test(self, callback):
        button = QPushButton("Afficher le menu des prompts")
        button.clicked.connect(callback)
        self.form.addRow("Test sans raccourci", button)
