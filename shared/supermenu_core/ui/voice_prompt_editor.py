"""Shared voice prompt library and editor for both desktop compositions."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from supermenu_core.config.model_target import without_server
from supermenu_core.config.voice_prompts import VOICE_ORDER_CHOICES
from .controls import ChoiceBox
from .model_catalog import selected_model_id, selected_model_target
from .settings_panel import form_layout, scrollable_form
from .page_actions import PromptActions
from .confirmations import confirm_action, confirm_unsaved_changes
from .prompt_restore import restore_library, restore_previous_library
from .prompt_reasoning import PromptReasoningChoice
from .prompt_model import PromptModelChoice


class VoicePromptEditor(QWidget):
    run_requested = Signal(str)
    import_requested = Signal()
    export_requested = Signal()

    def __init__(
        self, settings, parent=None, *, list_factory=QListWidget, sidebar_width=260
    ):
        super().__init__(parent)
        self.settings = settings
        self._loading = False
        self._current_id = None
        # Form values as loaded or saved, to detect edits before replacing them.
        self._saved_form = None
        self._pending_target = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        help_text = QLabel(
            "Choisissez une instruction à appliquer après la dictée. La voix utilise le moteur de Dictée, puis le texte utilise le moteur de Texte."
        )
        help_text.setWordWrap(True)
        help_text.setObjectName("mutedText")
        layout.addWidget(help_text)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(12)
        layout.addWidget(splitter, 1)
        left = QWidget()
        left.setFixedWidth(sidebar_width)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher un prompt vocal…")
        self.search.textChanged.connect(self._filter)
        left_layout.addWidget(self.search)
        self.prompt_list = list_factory()
        self.prompt_list.setAccessibleName("Prompts vocaux")
        self.prompt_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.prompt_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.prompt_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.prompt_list.currentItemChanged.connect(self._current_changed)
        self.prompt_list.model().rowsMoved.connect(self._reorder)
        left_layout.addWidget(self.prompt_list, 1)
        buttons = QHBoxLayout()
        self.add_button = QPushButton("Ajouter")
        self.add_button.clicked.connect(self.add_prompt)
        buttons.addWidget(self.add_button)
        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setProperty("variant", "danger")
        self.delete_button.clicked.connect(self.delete_prompt)
        buttons.addWidget(self.delete_button)
        left_layout.addLayout(buttons)
        transfer = QHBoxLayout()
        self.import_button = QPushButton("Importer")
        self.import_button.setToolTip("Importer les prompts textuels et vocaux")
        self.import_button.clicked.connect(self.import_requested)
        transfer.addWidget(self.import_button)
        self.export_button = QPushButton("Exporter")
        self.export_button.setToolTip("Exporter les prompts textuels et vocaux")
        self.export_button.clicked.connect(self.export_requested)
        transfer.addWidget(self.export_button)
        left_layout.addLayout(transfer)
        splitter.addWidget(left)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        self.form = QGroupBox("Votre prompt vocal")
        form = form_layout(self.form, stacked=True)
        self.name_input = QLineEdit()
        form.addRow("Nom", self.name_input)
        self.instruction_input = QTextEdit()
        self.instruction_input.setMinimumHeight(100)
        form.addRow("Instructions", self.instruction_input)
        self.model_choice = PromptModelChoice(settings)
        form.addRow("Modèle de texte après transcription", self.model_choice)
        self.reasoning = PromptReasoningChoice()
        form.addRow("Raisonnement (si disponible)", self.reasoning)
        self.status_input = QLineEdit()
        form.addRow("Message pendant le traitement", self.status_input)
        self.insert_directly = QCheckBox(
            "Insérer le résultat sans ouvrir la fenêtre de réponse"
        )
        form.addRow(self.insert_directly)
        self.include_selected = QCheckBox(
            "Inclure le texte sélectionné dans la requête vocale"
        )
        form.addRow(self.include_selected)
        self.order_combo = ChoiceBox()
        for label, value in VOICE_ORDER_CHOICES:
            self.order_combo.addItem(label, value)
        form.addRow("Ordre des éléments", self.order_combo)
        self.include_selected.toggled.connect(self.order_combo.setEnabled)
        right_layout.addWidget(scrollable_form(self.form), 1)
        self.feedback = QLabel()
        self.feedback.setWordWrap(True)
        right_layout.addWidget(self.feedback)
        self.actions = PromptActions(self.reset_prompt, self.save, run=self.run)
        self.actions.restore_requested.connect(self.restore_library)
        self.actions.restore_previous_requested.connect(self.restore_previous_library)
        self.reset_button = self.actions.reset_button
        self.save_button = self.actions.save_button
        self.run_button = self.actions.run_button
        right_layout.addWidget(self.actions)
        splitter.addWidget(right)
        self.reload()

    def reload(self, selected_id=None):
        selected_id = selected_id or self._current_id
        self._pending_target = None
        self._loading = True
        self.prompt_list.clear()
        selected = None
        for identifier, prompt in sorted(
            self.settings.get_voice_prompts().items(),
            key=lambda item: item[1].get("position", 999),
        ):
            item = QListWidgetItem(prompt["name"])
            item.setToolTip(prompt["name"])
            item.setData(Qt.ItemDataRole.UserRole, identifier)
            self.prompt_list.addItem(item)
            if identifier == selected_id:
                selected = item
        self._filter(self.search.text())
        # An explicit reload replaces the form: no unsaved-changes prompt.
        self.prompt_list.setCurrentItem(selected or self.prompt_list.item(0))
        self._loading = False
        self._select(self.prompt_list.currentItem())

    def _item_for(self, identifier):
        for index in range(self.prompt_list.count()):
            item = self.prompt_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == identifier:
                return item
        return None

    def _set_current_item(self, item):
        self._loading = True
        try:
            self.prompt_list.setCurrentItem(item)
        finally:
            self._loading = False

    def _model_state(self):
        # The choice as shown, not target(): target() also checks the server
        # type of the Text settings, which can change without any edit here.
        provider = self.model_choice.provider.currentData()
        model = self.model_choice.model
        if provider == "custom":
            return provider, without_server(selected_model_target(model))
        if provider in {"openai", "foundry"}:
            return provider, selected_model_id(model)
        return provider, None

    def _form_state(self):
        return (
            self.name_input.text().strip(),
            self.instruction_input.toPlainText().strip(),
            self.status_input.text().strip(),
            self.insert_directly.isChecked(),
            self.include_selected.isChecked(),
            self.order_combo.currentData(),
            self.reasoning.currentData(),
            self._model_state(),
        )

    def has_unsaved_changes(self):
        return (
            self._current_id is not None
            and self._saved_form is not None
            and self._form_state() != self._saved_form
        )

    def _confirm_leaving(self, proceed):
        """Offer to save the edited prompt before another one replaces it."""
        name = self.name_input.text().strip() or "ce prompt vocal"

        def save_then_proceed():
            if self.save():
                proceed()

        confirm_unsaved_changes(
            self,
            "Modifications non enregistrées",
            f"Enregistrer les modifications de « {name} » avant de continuer ?",
            save_then_proceed,
            proceed,
        )

    def _current_changed(self, item, _previous=None):
        if self._loading:
            return
        target_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if target_id == self._current_id and item is not None:
            # Same prompt (for example after a move): keep the edits on screen.
            return
        if self._item_for(self._current_id) is None or not self.has_unsaved_changes():
            self._select(item)
            return
        # Ask once the click is fully handled: the view would otherwise still
        # select the clicked row after the edited one was restored.
        first = self._pending_target is None
        self._pending_target = (target_id,)
        if first:
            QTimer.singleShot(0, self, self._confirm_selection_change)

    def _confirm_selection_change(self):
        pending, self._pending_target = self._pending_target, None
        if pending is None:
            return
        target_id = pending[0]
        edited_item = self._item_for(self._current_id)
        if edited_item is None or not self.has_unsaved_changes():
            self._select(self.prompt_list.currentItem())
            return
        # Keep the edited prompt selected until the user decides.
        self._set_current_item(edited_item)
        if getattr(self, "_confirmation_dialog", None) is not None:
            return

        def select_target():
            target = self._item_for(target_id)
            if target is not None:
                self._set_current_item(target)
            self._select(self.prompt_list.currentItem())

        self._confirm_leaving(select_target)

    def _select(self, item, _previous=None):
        if self._loading:
            return
        self._current_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        prompt = self.settings.get_voice_prompt(self._current_id) or {}
        for widget in (
            self.form,
            self.save_button,
            self.run_button,
            self.delete_button,
        ):
            widget.setEnabled(bool(prompt))
        self.reset_button.setEnabled(
            self._current_id in self.settings.default_voice_prompts
        )
        self.name_input.setText(prompt.get("name", ""))
        self.instruction_input.setPlainText(prompt.get("prompt", ""))
        self.status_input.setText(prompt.get("status", ""))
        self.insert_directly.setChecked(prompt.get("insert_directly", False))
        self.reasoning.set_mode(prompt.get("reasoning_mode", "default"))
        self.model_choice.set_target(prompt.get("model_target", {}))
        self.include_selected.setChecked(prompt.get("include_selected_text", False))
        self.order_combo.setEnabled(self.include_selected.isChecked())
        self.order_combo.setCurrentIndex(
            max(0, self.order_combo.findData(prompt.get("prompt_order")))
        )
        self.feedback.clear()
        self._saved_form = self._form_state() if prompt else None

    def _filter(self, text):
        for index in range(self.prompt_list.count()):
            item = self.prompt_list.item(index)
            item.setHidden(text.casefold() not in item.text().casefold())

    def _reorder(self, *_args):
        if self._loading:
            return
        prompts = self.settings.get_voice_prompts()
        for index in range(self.prompt_list.count()):
            identifier = self.prompt_list.item(index).data(Qt.ItemDataRole.UserRole)
            prompts[identifier]["position"] = (index + 1) * 10
        self.settings.set_voice_prompts(prompts)

    def save(self, _checked=False):
        if not self.model_choice.is_valid():
            return False
        if self._current_id is None:
            return True
        name = self.name_input.text().strip()
        instruction = self.instruction_input.toPlainText().strip()
        if not name or not instruction:
            self.feedback.setText("Renseignez le nom et les instructions du prompt.")
            return False
        self.settings.update_voice_prompt(
            self._current_id,
            name,
            instruction,
            self.status_input.text().strip() or "Traitement en cours…",
            self.insert_directly.isChecked(),
            include_selected_text=self.include_selected.isChecked(),
            prompt_order=self.order_combo.currentData(),
            reasoning_mode=self.reasoning.currentData(),
            model_target=self.model_choice.target(),
        )
        item = self._item_for(self._current_id) or self.prompt_list.currentItem()
        if item is not None:
            item.setText(name)
            item.setToolTip(name)
        self._saved_form = self._form_state()
        self.feedback.setText("Prompt vocal enregistré.")
        return True

    def add_prompt(self):
        if self.has_unsaved_changes():
            if getattr(self, "_confirmation_dialog", None) is None:
                self._confirm_leaving(self._add_prompt)
            return
        self._add_prompt()

    def _add_prompt(self):
        self.search.clear()
        identifier = self.settings.add_voice_prompt(
            None,
            "Nouveau prompt vocal",
            "",
            "Traitement en cours…",
            position=(self.prompt_list.count() + 1) * 10,
        )
        self.reload(identifier)
        self.name_input.setFocus()
        self.name_input.selectAll()

    def delete_prompt(self):
        identifier = self._current_id
        if identifier is None:
            return

        def remove():
            self.settings.delete_voice_prompt(identifier)
            self._current_id = None
            self.reload()

        confirm_action(self, "Supprimer le prompt vocal", "Supprimer ce prompt vocal ?", remove)

    def reset_prompt(self):
        identifier = self._current_id
        default = self.settings.default_voice_prompts.get(identifier)
        if default is None:
            return

        def restore():
            prompts = self.settings.get_voice_prompts()
            if identifier not in prompts:
                return
            prompts[identifier] = {**default, "position": prompts[identifier]["position"]}
            self.settings.set_voice_prompts(prompts)
            self.reload(identifier)

        confirm_action(self, "Réinitialiser le prompt vocal",
                       "Rétablir les instructions et options d’origine ?", restore)

    def restore_library(self):
        restore_library(self, self.settings, self.reload, voice=True)

    def restore_previous_library(self):
        """Go back to the copy kept by the last restore, import or repair."""
        restore_previous_library(self, self.settings, self.reload, voice=True)

    def run(self):
        if self._current_id is not None and self.save():
            self.run_requested.emit(self._current_id)
