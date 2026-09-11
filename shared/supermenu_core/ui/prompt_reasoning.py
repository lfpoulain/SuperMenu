"""Shared reasoning selector for text and voice prompts."""

from .controls import ChoiceBox
from supermenu_core.config.prompt_reasoning import REASONING_CHOICES


class PromptReasoningChoice(ChoiceBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        for label, value in REASONING_CHOICES:
            self.addItem(label, value)
        self.setToolTip(
            "Active ou désactive le raisonnement pour ce prompt, si le modèle le permet. "
            "Apple Foundation Models reste automatique. Certains modèles imposent un raisonnement minimal."
        )

    def set_mode(self, mode):
        self.setCurrentIndex(max(0, self.findData(mode)))
