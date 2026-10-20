"""Page des prompts texte de la fenêtre principale."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLineEdit,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QSignalBlocker, Qt
from supermenu_core.ui.controls import SIDEBAR_WIDTH, SidebarList
from supermenu_core.ui.confirmations import confirm_action
from supermenu_core.ui.prompt_restore import restore_library
from supermenu_core.ui.settings_panel import scrollable_form


class PromptPageMixin:
    """Text prompt page of the main window."""

    def _create_prompts_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(12)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left.setFixedWidth(SIDEBAR_WIDTH)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        self.prompt_search = QLineEdit()
        self.prompt_search.setPlaceholderText("Rechercher un prompt…")
        self.prompt_search.textChanged.connect(self._filter_prompts)
        left_layout.addWidget(self.prompt_search)
        self.prompt_list = SidebarList()
        self.prompt_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.prompt_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.prompt_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.prompt_list.setDropIndicatorShown(True)
        self.prompt_list.currentItemChanged.connect(self._load_selected_prompt)
        self.prompt_list.model().rowsMoved.connect(self._save_prompt_order)
        left_layout.addWidget(self.prompt_list)
        prompt_buttons = QHBoxLayout()
        add_button = QPushButton("Ajouter")
        add_button.clicked.connect(self.add_prompt)
        prompt_buttons.addWidget(add_button)
        delete_button = QPushButton("Supprimer")
        delete_button.setProperty("variant", "danger")
        delete_button.clicked.connect(self.delete_prompt)
        prompt_buttons.addWidget(delete_button)
        left_layout.addLayout(prompt_buttons)
        transfer_buttons = QHBoxLayout()
        import_button = QPushButton("Importer")
        import_button.clicked.connect(self.import_prompts)
        transfer_buttons.addWidget(import_button)
        export_button = QPushButton("Exporter")
        export_button.clicked.connect(self.export_prompts)
        transfer_buttons.addWidget(export_button)
        left_layout.addLayout(transfer_buttons)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        from supermenu_core.ui.text_prompt_form import TextPromptForm
        from supermenu_core.ui.page_actions import PromptActions

        self.text_prompt_form = TextPromptForm(settings=self.settings)
        self.prompt_name = self.text_prompt_form.name
        self.prompt_instruction = self.text_prompt_form.instruction
        self.prompt_status = self.text_prompt_form.status
        self.prompt_direct = self.text_prompt_form.insert_directly
        self.prompt_hotkey = self.text_prompt_form.hotkey
        self.text_prompt_form.record_requested.connect(self.record_prompt_hotkey)
        self.text_prompt_form.clear_requested.connect(self.prompt_hotkey.clear)
        right_layout.addWidget(scrollable_form(self.text_prompt_form), 1)
        self.prompt_actions = PromptActions(self.reset_prompt, lambda: self.save_current_prompt())
        self.prompt_actions.restore_requested.connect(self.restore_prompt_library)
        self.prompt_actions.restore_previous_requested.connect(
            self.restore_previous_prompt_library
        )
        right_layout.addWidget(self.prompt_actions)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([SIDEBAR_WIDTH, 700])
        layout.addWidget(splitter)
        self._reload_prompts()
        return tab

    def _ordered_prompts(self):
        return sorted(
            self.settings.get_prompts().items(),
            key=lambda item: (item[1].get("position", 999), item[0]),
        )

    def _reload_prompts(self, selected_id=None):
        current = selected_id
        if current is None and self.prompt_list.currentItem() is not None:
            current = self.prompt_list.currentItem().data(Qt.ItemDataRole.UserRole)
        blocker = QSignalBlocker(self.prompt_list)
        self.prompt_list.clear()
        selected_item = None
        for prompt_id, prompt in self._ordered_prompts():
            item = QListWidgetItem(prompt.get("name") or prompt_id)
            # Long names are elided in the sidebar: the tooltip shows them whole.
            item.setToolTip(item.text())
            item.setData(Qt.ItemDataRole.UserRole, prompt_id)
            self.prompt_list.addItem(item)
            if prompt_id == current:
                selected_item = item
        self._filter_prompts(self.prompt_search.text())
        if selected_item is not None:
            self.prompt_list.setCurrentItem(selected_item)
        elif self.prompt_list.count():
            self.prompt_list.setCurrentRow(0)
        blocker.unblock()
        self._load_selected_prompt(self.prompt_list.currentItem())

    def _filter_prompts(self, text):
        query = str(text or "").strip().casefold()
        for index in range(self.prompt_list.count()):
            item = self.prompt_list.item(index)
            item.setHidden(query not in item.text().casefold())

    def _load_selected_prompt(self, current, _previous=None):
        self.prompt_actions.reset_button.setEnabled(
            current is not None and current.data(Qt.ItemDataRole.UserRole) in self.settings.default_prompts
        )
        if current is None:
            return
        prompt_id = current.data(Qt.ItemDataRole.UserRole)
        prompt = self.settings.get_prompt(prompt_id)
        if prompt is None:
            return
        self._loading_prompt = True
        self.prompt_name.setText(prompt.get("name", ""))
        self.prompt_instruction.setPlainText(prompt.get("prompt", ""))
        self.prompt_status.setText(prompt.get("status", ""))
        self.prompt_direct.setChecked(bool(prompt.get("insert_directly", False)))
        self.text_prompt_form.reasoning.set_mode(prompt.get("reasoning_mode", "default"))
        self.text_prompt_form.model_choice.set_target(prompt.get("model_target", {}))
        self.prompt_hotkey.setText(prompt.get("hotkey", ""))
        self._loading_prompt = False

    def _save_prompt_order(self, *_args):
        prompts = self.settings.get_prompts()
        for index in range(self.prompt_list.count()):
            prompt_id = self.prompt_list.item(index).data(Qt.ItemDataRole.UserRole)
            if prompt_id in prompts:
                prompts[prompt_id]["position"] = (index + 1) * 10
        self.settings.set_prompts(prompts)
        self.settings.sync()

    def add_prompt(self):
        prompt_id = self.settings.add_prompt(
            None,
            "Nouveau prompt",
            "",
            "Traitement en cours…",
            position=(self.prompt_list.count() + 1) * 10,
        )
        self.settings.sync()
        self._reload_prompts(prompt_id)
        self.prompt_name.selectAll()
        self.prompt_name.setFocus()

    def delete_prompt(self):
        item = self.prompt_list.currentItem()
        if item is None:
            return
        prompt_id, name = item.data(Qt.ItemDataRole.UserRole), item.text()

        def remove():
            self.settings.delete_prompt(prompt_id)
            self.settings.sync()
            self._prompts_restored()

        confirm_action(self, "Supprimer le prompt", f"Supprimer « {name} » ?", remove)

    def import_prompts(self):
        from PySide6.QtWidgets import QFileDialog

        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Importer des prompts",
            "",
            "Fichiers JSON (*.json)",
        )
        if not path:
            return
        previous_prompts = self.settings.get_prompts()
        previous_voice_prompts = self.settings.get_voice_prompts()
        try:
            count = self.settings.import_prompts(path)
        except Exception as exc:
            QMessageBox.warning(self, "Import impossible", str(exc))
            return
        if self.prompt_hotkey_manager is not None:
            # The imported library is now the saved one, so its shortcuts get
            # the tolerance of saved shortcuts: a backup restores as it was and
            # a refused shortcut stays unbound instead of refusing everything.
            # Only a conflict with another SuperMenu shortcut cancels.
            imported_prompts = self.settings.get_prompts()
            valid, errors = self.prompt_hotkey_manager.validate_prompts(
                imported_prompts
            )
            if not valid:
                self.settings.set_prompts(previous_prompts)
                self.settings.set_voice_prompts(previous_voice_prompts)
                self.settings.sync()
                message = self._prompt_hotkey_error(errors, imported_prompts)
                QMessageBox.warning(self, "Import impossible", message)
                return
        self._reload_prompts()
        self.voice_prompt_editor.reload()
        _success, hotkey_errors = self._refresh_prompt_hotkeys()
        message = f"{count} prompt(s) importé(s)."
        refused = {
            prompt_id: error
            for prompt_id, error in hotkey_errors.items()
            if prompt_id != "registration"
        }
        if refused:
            message += (
                "\n\nRaccourci non activé — "
                + self._prompt_hotkey_error(refused, self.settings.get_prompts())
                + "\nRéenregistrez-le avec « Définir » dans l’onglet Prompts."
            )
        QMessageBox.information(self, "Import terminé", message)

    def export_prompts(self):
        from PySide6.QtWidgets import QFileDialog

        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exporter les prompts",
            "SuperMenu-prompts.json",
            "Fichiers JSON (*.json)",
        )
        if not path:
            return
        if not path.casefold().endswith(".json"):
            path += ".json"
        try:
            self.settings.export_prompts(path)
        except Exception as exc:
            QMessageBox.warning(self, "Export impossible", str(exc))
            return
        QMessageBox.information(self, "Export terminé", "Les prompts ont été exportés.")

    def save_current_prompt(self, show_confirmation=True):
        # A hidden model choice (advanced features off) is kept, never checked.
        if not self.text_prompt_form.model_choice_is_valid():
            return False
        item = self.prompt_list.currentItem()
        if item is None:
            return False
        name = self.prompt_name.text().strip()
        instruction = self.prompt_instruction.toPlainText().strip()
        if not name or not instruction:
            QMessageBox.warning(
                self,
                "Prompt incomplet",
                "Le nom et l’instruction sont obligatoires.",
            )
            return False
        prompt_id = item.data(Qt.ItemDataRole.UserRole)
        prompt = self.settings.get_prompt(prompt_id) or {}
        # Without the advanced features the model and shortcut rows are hidden:
        # the stored values are saved back unchanged (None keeps the model).
        model_target = self.text_prompt_form.model_target_for_save()
        if self.text_prompt_form.is_advanced_visible():
            hotkey = self.prompt_hotkey.text().strip()
        else:
            hotkey = str(prompt.get("hotkey", "") or "").strip()
        candidate_prompts = self.settings.get_prompts()
        candidate_prompts[prompt_id] = {
            "name": name,
            "prompt": instruction,
            "status": self.prompt_status.text().strip()
            or "Traitement en cours…",
            "insert_directly": self.prompt_direct.isChecked(),
            "reasoning_mode": self.text_prompt_form.reasoning.currentData(),
            "model_target": (
                model_target
                if model_target is not None
                else prompt.get("model_target", {})
            ),
            "position": prompt.get("position", 999),
            "hotkey": hotkey,
        }
        if self.prompt_hotkey_manager is not None:
            valid, errors = self.prompt_hotkey_manager.validate_prompts(
                candidate_prompts
            )
            if not valid:
                message = self._prompt_hotkey_error(errors, candidate_prompts)
                QMessageBox.warning(self, "Raccourci invalide", message)
                return False
        try:
            self.settings.update_prompt(
                prompt_id,
                name,
                instruction,
                self.prompt_status.text().strip() or "Traitement en cours…",
                self.prompt_direct.isChecked(),
                position=prompt.get("position", 999),
                hotkey=hotkey,
                reasoning_mode=self.text_prompt_form.reasoning.currentData(),
                model_target=model_target,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Raccourci invalide", str(exc))
            return False
        self.settings.sync()
        self._reload_prompts(prompt_id)
        self._refresh_prompt_hotkeys()
        if show_confirmation:
            self.statusBar().showMessage("Prompt enregistré.", 5000)
        return True

    @staticmethod
    def _prompt_hotkey_error(errors, prompts):
        """Name the prompt whose shortcut is refused, not only the reason.

        The error can concern another prompt than the one on screen (a
        conflict, or a refused shortcut reported after an import); the name
        says which one to fix.
        """
        prompt_id, message = next(
            iter(errors.items()), ("", "Conflit de raccourci")
        )
        prompt = prompts.get(prompt_id) if isinstance(prompts, dict) else None
        name = str(prompt.get("name") or "").strip() if isinstance(prompt, dict) else ""
        return f"« {name} » : {message}" if name else message

    def reset_prompt(self):
        from supermenu_core.ui.text_prompt_form import reset_text_prompt
        item = self.prompt_list.currentItem()
        prompt_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        reset_text_prompt(self.settings, prompt_id, self, self._prompts_restored)

    def _prompts_restored(self):
        self._reload_prompts()
        self._refresh_prompt_hotkeys()

    def restore_prompt_library(self):
        restore_library(self, self.settings, self._prompts_restored)
