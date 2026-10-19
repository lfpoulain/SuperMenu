"""Shared shortcut rows; native registration is supplied by the platform."""

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLineEdit, QPushButton

from .settings_panel import form_layout


class ShortcutSettings(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Raccourcis clavier", parent)
        self.form = form_layout(self)
        # Row layout of each shortcut field, to hide a whole row with its label.
        self._rows = {}

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
        self._rows[field] = row
        return field

    def set_shortcut_visible(self, field, visible):
        """Show or hide the row of a field returned by add_shortcut()."""
        self.form.setRowVisible(self._rows[field], visible)

    def is_shortcut_visible(self, field):
        return self.form.isRowVisible(self._rows[field])

    def add_test(self, callback):
        button = QPushButton("Afficher le menu des prompts")
        button.clicked.connect(callback)
        self.form.addRow("Test sans raccourci", button)
