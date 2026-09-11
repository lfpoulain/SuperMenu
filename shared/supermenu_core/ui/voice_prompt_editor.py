"""Shared voice prompt library and editor for both desktop compositions."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from supermenu_core.config.voice_prompts import VOICE_ORDER_CHOICES
from .controls import ChoiceBox
from .settings_panel import form_layout, scrollable_form
from .page_actions import PromptActions
from .prompt_reasoning import PromptReasoningChoice


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
        self.prompt_list.currentItemChanged.connect(self._select)
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
        self.reset_button = self.actions.reset_button
        self.save_button = self.actions.save_button
        self.run_button = self.actions.run_button
        right_layout.addWidget(self.actions)
        splitter.addWidget(right)
        self.reload()

    def reload(self, selected_id=None):
        selected_id = selected_id or self._current_id
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
        self._loading = False
        self._filter(self.search.text())
        self.prompt_list.setCurrentItem(selected or self.prompt_list.item(0))
        self._select(self.prompt_list.currentItem())

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
        self.include_selected.setChecked(prompt.get("include_selected_text", False))
        self.order_combo.setEnabled(self.include_selected.isChecked())
        self.order_combo.setCurrentIndex(
            max(0, self.order_combo.findData(prompt.get("prompt_order")))
        )
        self.feedback.clear()

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
        )
        self.prompt_list.currentItem().setText(name)
        self.prompt_list.currentItem().setToolTip(name)
        self.feedback.setText("Prompt vocal enregistré.")
        return True

    def add_prompt(self):
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
        if self._current_id is None:
            return
        reply = QMessageBox.question(
            self,
            "Supprimer le prompt vocal",
            "Supprimer ce prompt vocal ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.settings.delete_voice_prompt(self._current_id)
            self._current_id = None
            self.reload()

    def reset_prompt(self):
        default = self.settings.default_voice_prompts.get(self._current_id)
        if default is None:
            return
        reply = QMessageBox.question(
            self,
            "Réinitialiser le prompt vocal",
            "Rétablir les instructions et options d’origine ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            prompts = self.settings.get_voice_prompts()
            prompts[self._current_id] = {
                **default,
                "position": prompts[self._current_id]["position"],
            }
            self.settings.set_voice_prompts(prompts)
            self.reload()

    def run(self):
        if self._current_id is not None and self.save():
            self.run_requested.emit(self._current_id)
