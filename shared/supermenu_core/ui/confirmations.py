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


class UnsavedChangesDialog(QMessageBox):
    """Ask whether pending edits are saved before they are replaced."""

    def __init__(self, parent, title, message, save, discard, cancel=None):
        super().__init__(parent)
        self._callbacks = {"save": save, "discard": discard, "cancel": cancel}
        self.setOption(QMessageBox.Option.DontUseNativeDialog, True)
        self.setWindowTitle(title)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText(message)
        self.setIcon(QMessageBox.Icon.Question)
        self.save_button = self.addButton(
            "Enregistrer", QMessageBox.ButtonRole.AcceptRole
        )
        self.discard_button = self.addButton(
            "Ignorer", QMessageBox.ButtonRole.DestructiveRole
        )
        self.cancel_button = self.addButton(
            "Annuler", QMessageBox.ButtonRole.RejectRole
        )
        self.setDefaultButton(self.save_button)
        self.setEscapeButton(self.cancel_button)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.finished.connect(self._finished)

    @Slot(int)
    def _finished(self, _result):
        parent = self.parentWidget()
        if parent is not None:
            parent._confirmation_dialog = None
        clicked = self.clickedButton()
        if clicked is self.save_button:
            choice = "save"
        elif clicked is self.discard_button:
            choice = "discard"
        else:
            choice = "cancel"
        callbacks, self._callbacks = self._callbacks, {}
        self.deleteLater()
        callback = callbacks.get(choice)
        if callback is not None:
            callback()


def confirm_unsaved_changes(parent, title, message, save, discard, cancel=None):
    pending = getattr(parent, "_confirmation_dialog", None)
    if pending is not None:
        pending.raise_()
        return pending
    dialog = UnsavedChangesDialog(parent, title, message, save, discard, cancel)
    parent._confirmation_dialog = dialog
    dialog.open()
    return dialog


def confirm_action(parent, title, message, accepted):
    pending = getattr(parent, "_confirmation_dialog", None)
    if pending is not None:
        pending.raise_()
        return pending
    dialog = ConfirmationDialog(parent, title, message, accepted)
    parent._confirmation_dialog = dialog
    dialog.open()
    return dialog
