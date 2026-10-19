"""Page-scoped actions with stable placement on both desktop platforms."""

from PySide6.QtCore import Signal
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


class PromptActions(PageActions):
    """Keep reset anchored left and save anchored right in both editors."""

    restore_requested = Signal()
    restore_previous_requested = Signal()

    def __init__(self, reset, save, *, run=None, parent=None):
        super().__init__(parent)
        self.reset_button = self.add_action("Réinitialiser", reset)
        self.reset_button.setToolTip("Rétablir le prompt d’origine après confirmation")
        self.row.removeWidget(self.reset_button)
        self.row.insertWidget(0, self.reset_button)
        self.restore_button = self.add_action("Tout restaurer…", self.restore_requested.emit)
        self.restore_button.setToolTip("Restaurer la liste complète des prompts d’origine")
        self.row.removeWidget(self.restore_button)
        self.row.insertWidget(1, self.restore_button)
        self.previous_button = self.add_action(
            "Revenir à la copie…", self.restore_previous_requested.emit
        )
        self.previous_button.setToolTip(
            "Remettre la liste conservée avant la dernière restauration ou le dernier import"
        )
        self.row.removeWidget(self.previous_button)
        self.row.insertWidget(2, self.previous_button)
        self.run_button = self.add_action("Dicter", run) if run is not None else None
        self.save_button = self.add_action("Enregistrer", save, primary=True)
