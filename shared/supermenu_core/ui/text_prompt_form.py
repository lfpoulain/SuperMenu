"""Shared text prompt fields; persistence and hotkeys stay in each adapter."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGroupBox, QLineEdit, QTextEdit, QCheckBox, QHBoxLayout, QPushButton, QMessageBox

from .settings_panel import form_layout
from .prompt_reasoning import PromptReasoningChoice


def reset_text_prompt(settings, prompt_id, parent):
    """Restore one built-in prompt without changing the user's list order."""
    default = settings.default_prompts.get(prompt_id)
    current = settings.get_prompt(prompt_id)
    if default is None or current is None:
        return False
    reply = QMessageBox.question(
        parent, "Réinitialiser le prompt", "Rétablir les instructions et options d’origine ?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return False
    settings.update_prompt(
        prompt_id, default["name"], default["prompt"], default["status"],
        default.get("insert_directly", False), position=current.get("position", 999),
        hotkey=default.get("hotkey", ""),
        reasoning_mode=default.get("reasoning_mode", "default"),
    )
    settings.sync()
    return True


class TextPromptForm(QGroupBox):
    record_requested = Signal()
    clear_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("Votre prompt", parent)
        form = form_layout(self, stacked=True)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ex. : Corriger l’orthographe")
        form.addRow("Nom", self.name)
        self.instruction = QTextEdit()
        self.instruction.setAcceptRichText(False)
        self.instruction.setMinimumHeight(100)
        self.instruction.setPlaceholderText("Ex. : Corrige l’orthographe et la grammaire du texte suivant.")
        form.addRow("Instructions", self.instruction)
        self.reasoning = PromptReasoningChoice()
        form.addRow("Raisonnement (si disponible)", self.reasoning)
        self.status = QLineEdit()
        self.status.setPlaceholderText("Ex. : Correction en cours…")
        form.addRow("Message pendant le traitement", self.status)
        self.insert_directly = QCheckBox("Insérer le résultat sans ouvrir la fenêtre de réponse")
        form.addRow(self.insert_directly)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.hotkey = QLineEdit()
        self.hotkey.setReadOnly(True)
        self.hotkey.setPlaceholderText("Aucun raccourci direct pour ce prompt")
        row.addWidget(self.hotkey, 1)
        record = QPushButton("Définir")
        record.clicked.connect(self.record_requested)
        row.addWidget(record)
        clear = QPushButton("Effacer")
        clear.clicked.connect(self.clear_requested)
        row.addWidget(clear)
        form.addRow("Raccourci direct", row)
