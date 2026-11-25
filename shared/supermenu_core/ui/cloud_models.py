"""Model choices of the online engines (OpenAI, Anthropic), shared by both apps."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QLineEdit, QVBoxLayout

from supermenu_core.config.anthropic_models import (
    AVAILABLE_ANTHROPIC_MODELS,
    get_anthropic_model_description,
    get_anthropic_model_label,
    get_anthropic_reasoning_efforts,
)
from supermenu_core.config.openai_models import (
    AVAILABLE_MODELS,
    get_openai_model_description,
)

from .controls import ChoiceBox
from .settings_panel import Disclosure


def populate_openai_models(combo):
    """List the OpenAI models by identifier, each described in its tooltip."""
    combo.clear()
    for model in AVAILABLE_MODELS:
        combo.addItem(model, model)
        description = get_openai_model_description(model)
        if description:
            combo.setItemData(
                combo.count() - 1, description, Qt.ItemDataRole.ToolTipRole
            )


def populate_anthropic_models(combo):
    """List the Claude models by name; the item data is the API identifier."""
    combo.clear()
    for model in AVAILABLE_ANTHROPIC_MODELS:
        combo.addItem(get_anthropic_model_label(model), model)
        description = get_anthropic_model_description(model)
        if description:
            combo.setItemData(
                combo.count() - 1, description, Qt.ItemDataRole.ToolTipRole
            )


def select_model(combo, model):
    """Select ``model`` by identifier; return False when it is not listed."""
    index = combo.findData(model)
    if index < 0:
        return False
    combo.setCurrentIndex(index)
    return True


class AnthropicSettingsGroup(QGroupBox):
    """API key, model and reasoning effort of the Anthropic text engine."""

    def __init__(self, settings, parent=None):
        super().__init__("Anthropic", parent)
        self.settings = settings
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Clé API"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("sk-ant-…")
        self.api_key_input.setAccessibleName("Clé API Anthropic")
        layout.addWidget(self.api_key_input)

        layout.addWidget(QLabel("Modèle"))
        self.model_combo = ChoiceBox()
        self.model_combo.setAccessibleName("Modèle Claude")
        populate_anthropic_models(self.model_combo)
        layout.addWidget(self.model_combo)
        self.model_hint = QLabel()
        self.model_hint.setObjectName("mutedText")
        self.model_hint.setTextFormat(Qt.TextFormat.PlainText)
        self.model_hint.setWordWrap(True)
        layout.addWidget(self.model_hint)

        advanced = Disclosure()
        advanced.content_layout.addWidget(QLabel("Raisonnement"))
        self.reasoning_combo = ChoiceBox()
        self.reasoning_combo.setAccessibleName("Raisonnement Claude")
        self.reasoning_combo.setToolTip(
            "Les modèles Claude raisonnent toujours un peu : « low » est le "
            "niveau le plus rapide."
        )
        advanced.content_layout.addWidget(self.reasoning_combo)
        layout.addWidget(advanced)

        self.model_combo.currentIndexChanged.connect(self._model_changed)
        self.reload()

    def selected_model(self):
        return self.model_combo.currentData()

    def selected_effort(self):
        return self.reasoning_combo.currentText()

    def api_key(self):
        return self.api_key_input.text().strip()

    def _model_changed(self, *_args):
        model = self.selected_model()
        self.model_hint.setText(get_anthropic_model_description(model))
        # Keep the effort being edited when the next model accepts it too.
        wanted = self.reasoning_combo.currentText() or None
        current = self.settings.get_anthropic_reasoning_effort(model)
        efforts = get_anthropic_reasoning_efforts(model)
        self.reasoning_combo.blockSignals(True)
        self.reasoning_combo.clear()
        self.reasoning_combo.addItems(efforts)
        self.reasoning_combo.setCurrentText(wanted if wanted in efforts else current)
        self.reasoning_combo.blockSignals(False)

    def reload(self):
        """Show the saved configuration again (first display, reset)."""
        self.api_key_input.setText(self.settings.get_anthropic_api_key() or "")
        self.reasoning_combo.clear()
        select_model(self.model_combo, self.settings.get_anthropic_model())
        self._model_changed()

    def validation_error(self):
        """Return why the key cannot be saved, or an empty string."""
        key = self.api_key()
        if key and (len(key) < 20 or any(char.isspace() for char in key)):
            return (
                "La clé API Anthropic semble incomplète. Copiez-la en entier "
                "depuis la console Anthropic."
            )
        return ""

    def save(self):
        """Store the key, the model and the effort chosen for that model."""
        model = self.selected_model()
        self.settings.set_anthropic_api_key(self.api_key())
        self.settings.set_anthropic_model(model)
        self.settings.set_anthropic_reasoning_effort(self.selected_effort(), model)
