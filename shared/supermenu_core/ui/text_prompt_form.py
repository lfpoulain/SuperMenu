"""Shared text prompt fields; persistence and hotkeys stay in each adapter."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGroupBox, QLineEdit, QCheckBox, QHBoxLayout, QPushButton

from supermenu_core.config.feature_modes import advanced_enabled
from .settings_panel import form_layout
from .confirmations import confirm_action
from .controls import PlainTextEdit
from .prompt_reasoning import PromptReasoningChoice
from .prompt_model import PromptModelChoice


def reset_text_prompt(settings, prompt_id, parent, refreshed):
    default = settings.default_prompts.get(prompt_id)
    if default is None:
        return

    def restore():
        current = settings.get_prompt(prompt_id)
        if current is None:
            return
        # Without the advanced features, the hidden hotkey and model choice
        # are kept: they return unchanged when the features are turned on.
        advanced = advanced_enabled(settings)
        settings.update_prompt(
            prompt_id, default["name"], default["prompt"], default["status"],
            default.get("insert_directly", False), position=current.get("position", 999),
            hotkey=default.get("hotkey", "") if advanced else current.get("hotkey", ""),
            reasoning_mode=default.get("reasoning_mode", "default"),
            model_target=default.get("model_target", {}) if advanced else None,
        )
        settings.sync()
        refreshed()

    return confirm_action(parent, "Réinitialiser le prompt",
                          "Rétablir les instructions et options d’origine ?", restore)


INSTRUCTIONS_MAX_HEIGHT = 140


class TextPromptForm(QGroupBox):
    record_requested = Signal()
    clear_requested = Signal()

    def __init__(self, parent=None, *, settings=None):
        super().__init__("Votre prompt", parent)
        form = self.form = form_layout(self, stacked=True)
        # Per-prompt model and hotkey belong to the advanced features.
        self._advanced_visible = True
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ex. : Corriger l’orthographe")
        form.addRow("Nom", self.name)
        # Plain text only, even when an adapter loads it with setText().
        self.instruction = PlainTextEdit()
        # About six lines: the options below stay visible without scrolling
        # the form; a longer instruction scrolls inside the editor.
        self.instruction.setMinimumHeight(90)
        self.instruction.setMaximumHeight(INSTRUCTIONS_MAX_HEIGHT)
        self.instruction.setPlaceholderText("Ex. : Corrige l’orthographe et la grammaire du texte suivant.")
        form.addRow("Instructions", self.instruction)
        self.model_choice = PromptModelChoice(settings)
        form.addRow("Modèle de texte pour ce prompt", self.model_choice)
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
        self.hotkey_row = row

    def set_advanced_visible(self, visible):
        """Show or hide the per-prompt model and hotkey rows (reasoning stays)."""
        self._advanced_visible = bool(visible)
        self.form.setRowVisible(self.model_choice, self._advanced_visible)
        self.form.setRowVisible(self.hotkey_row, self._advanced_visible)

    def is_advanced_visible(self):
        return self._advanced_visible

    def model_target_for_save(self):
        """The shown choice, or None (keep the stored one) while it is hidden."""
        return self.model_choice.target() if self._advanced_visible else None

    def model_choice_is_valid(self):
        # A hidden choice is not saved, so it never blocks saving.
        return not self._advanced_visible or self.model_choice.is_valid()
