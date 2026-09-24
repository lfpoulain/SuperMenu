"""Non-blocking Qt confirmations, also safe from Cocoa menu callbacks."""

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QMessageBox


class ConfirmationDialog(QMessageBox):
    def __init__(self, parent, title, message, accepted):
        super().__init__(parent)
        self._accepted = accepted
        self.setOption(QMessageBox.Option.DontUseNativeDialog, True)
        self.setWindowTitle(title)
        self.setText(message)
        self.setIcon(QMessageBox.Icon.Question)
        self.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        self.setDefaultButton(QMessageBox.StandardButton.No)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.finished.connect(self._finished)

    @Slot(int)
    def _finished(self, result):
        parent = self.parentWidget()
        if parent is not None:
            parent._confirmation_dialog = None
        accepted, self._accepted = self._accepted, None
        self.deleteLater()
        if result == QMessageBox.StandardButton.Yes and accepted is not None:
            accepted()


def confirm_action(parent, title, message, accepted):
    pending = getattr(parent, "_confirmation_dialog", None)
    if pending is not None:
        pending.raise_()
        return pending
    dialog = ConfirmationDialog(parent, title, message, accepted)
    parent._confirmation_dialog = dialog
    dialog.open()
    return dialog
