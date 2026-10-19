"""Pages des prompts texte et vocaux de la fenêtre principale."""

import os
from supermenu_core.ui.controls import ChoiceBox, SIDEBAR_WIDTH, SidebarList
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from supermenu_core.utils.validators import Validators
from supermenu_core.ui.voice_prompt_editor import VoicePromptEditor
from supermenu_core.ui.prompt_restore import restore_library
from supermenu_core.ui.settings_panel import scrollable_form


class PromptPageMixin:
    """Text and voice prompt pages of the main window."""

    def create_prompts_tab(self):
        """Create the prompts settings tab"""
        prompts_tab = QWidget()
        layout = QVBoxLayout(prompts_tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.prompt_combo = ChoiceBox()
        self.populate_prompt_combo()
        self.prompt_combo.hide()

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(12)
        splitter.setChildrenCollapsible(False)

        left_panel = QWidget()
        left_panel.setFixedWidth(SIDEBAR_WIDTH)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.prompt_search_input = QLineEdit()
        self.prompt_search_input.setPlaceholderText("Rechercher un prompt…")
        self.prompt_search_input.textChanged.connect(self._apply_prompt_filter)
        left_layout.addWidget(self.prompt_search_input)

        self.prompt_order_list = SidebarList()
        self.prompt_order_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.prompt_order_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.prompt_order_list.setDefaultDropAction(Qt.MoveAction)
        self.prompt_order_list.setDropIndicatorShown(True)
        self.prompt_order_list.model().rowsMoved.connect(self.on_prompt_order_changed)
        self.prompt_order_list.currentItemChanged.connect(self._on_prompt_list_current_changed)
        left_layout.addWidget(self.prompt_order_list)

        left_buttons = QHBoxLayout()
        add_prompt_button = QPushButton("Ajouter")
        add_prompt_button.clicked.connect(self.add_prompt)
        left_buttons.addWidget(add_prompt_button)

        delete_prompt_button = QPushButton("Supprimer")
        delete_prompt_button.setProperty("variant", "danger")
        delete_prompt_button.clicked.connect(self.delete_prompt)
        left_buttons.addWidget(delete_prompt_button)

        left_layout.addLayout(left_buttons)
        transfer_buttons = QHBoxLayout()
        for label, callback in (("Importer", self.import_all_prompts), ("Exporter", self.export_all_prompts)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            transfer_buttons.addWidget(button)
        left_layout.addLayout(transfer_buttons)


        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        
        from supermenu_core.ui.text_prompt_form import TextPromptForm
        from supermenu_core.ui.page_actions import PromptActions

        self.text_prompt_form = TextPromptForm(settings=self.settings)
        self.prompt_name_input = self.text_prompt_form.name
        self.prompt_text_input = self.text_prompt_form.instruction
        self.prompt_status_input = self.text_prompt_form.status
        self.prompt_insert_directly = self.text_prompt_form.insert_directly
        self.prompt_hotkey_input = self.text_prompt_form.hotkey
        self.text_prompt_form.record_requested.connect(self.record_prompt_hotkey)
        self.text_prompt_form.clear_requested.connect(self.clear_prompt_hotkey)
        right_layout.addWidget(scrollable_form(self.text_prompt_form), 1)
        self.prompt_actions = PromptActions(self.reset_prompt, self.save_prompt)
        self.prompt_actions.restore_requested.connect(self.restore_prompt_library)
        # Offered by the shared actions once they expose the kept copies.
        restore_previous = getattr(self.prompt_actions, "restore_previous_requested", None)
        if restore_previous is not None:
            restore_previous.connect(self.restore_previous_prompt_library)
        right_layout.addWidget(self.prompt_actions)

        # Connect prompt selection change
        self.prompt_combo.currentIndexChanged.connect(self.load_prompt)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)
        
        # Add the tab
        self.tab_widget.addTab(prompts_tab, "Prompts")
        
        # Load the first prompt
        if self.prompt_combo.count() > 0:
            self.load_prompt(0)

        self.populate_prompt_order_list()

    def create_voice_prompts_tab(self):
        self.voice_prompt_editor = VoicePromptEditor(self.settings, self, list_factory=SidebarList, sidebar_width=SIDEBAR_WIDTH)
        self.voice_prompt_editor.run_button.hide()
        self.voice_prompt_editor.import_requested.connect(self.import_all_prompts)
        self.voice_prompt_editor.export_requested.connect(self.export_all_prompts)
        self.tab_widget.addTab(self.voice_prompt_editor, "Voix")

    def load_prompt(self, index):
        """Load the selected prompt into the editing fields"""
        self.prompt_actions.reset_button.setEnabled(
            self.prompt_combo.currentData() in self.settings.default_prompts
        )
        if index < 0 or self.prompt_combo.count() == 0:
            return
            
        prompt_id = self.prompt_combo.currentData()
        prompt_data = self.settings.get_prompt(prompt_id)
        
        if prompt_data:
            self.prompt_name_input.setText(prompt_data["name"])
            self.prompt_text_input.setPlainText(prompt_data["prompt"])
            self.prompt_status_input.setText(prompt_data["status"])
            self.prompt_insert_directly.setChecked(prompt_data.get("insert_directly", False))
            self.text_prompt_form.reasoning.set_mode(prompt_data.get("reasoning_mode", "default"))
            self.text_prompt_form.model_choice.set_target(prompt_data.get("model_target", {}))
            self.prompt_hotkey_input.setText(prompt_data.get("hotkey", ""))

    def save_prompt(self):
        """Save the prompt"""
        # A model choice hidden with the advanced features is not saved.
        if not self.text_prompt_form.model_choice_is_valid():
            return False
        if self.prompt_combo.count() == 0:
            return

        prompt_id = self.prompt_combo.currentData()
        name = self.prompt_name_input.text().strip()
        prompt = self.prompt_text_input.toPlainText()
        status = self.prompt_status_input.text()
        insert_directly = self.prompt_insert_directly.isChecked()
        if self.text_prompt_form.is_advanced_visible():
            prompt_hotkey = self.prompt_hotkey_input.text().strip()
        else:
            # Hidden with the advanced features: the stored shortcut is kept.
            stored_prompt = self.settings.get_prompt(prompt_id) or {}
            prompt_hotkey = str(stored_prompt.get("hotkey", "") or "").strip()

        position = 999
        previous_prompts = self.settings.get_prompts()
        try:
            position = self.settings.get_prompt(prompt_id).get("position", 999)
        except Exception:
            position = 999
        
        # Vérifier que les champs ne sont pas vides
        if not name or not prompt or not status:
            QMessageBox.warning(self, "Champs incomplets", 
                              "Veuillez remplir tous les champs (nom, prompt et statut).")
            return
        
        # Mettre à jour le prompt
        try:
            self.settings.update_prompt(
                prompt_id,
                name,
                prompt,
                status,
                insert_directly,
                position,
                hotkey=prompt_hotkey,
                reasoning_mode=self.text_prompt_form.reasoning.currentData(),
                # None keeps the stored model while the choice is hidden.
                model_target=self.text_prompt_form.model_target_for_save(),
            )
        except ValueError as e:
            QMessageBox.warning(self, "Raccourci invalide", str(e))
            return

        if self.prompt_hotkey_manager is not None:
            _success, errors = self.prompt_hotkey_manager.refresh_hotkeys()
            current_error = errors.get(prompt_id)
            if current_error:
                self.settings.set_prompts(previous_prompts)
                self.prompt_hotkey_manager.refresh_hotkeys()
                self.prompt_hotkey_input.setText(
                    previous_prompts.get(prompt_id, {}).get("hotkey", "")
                )
                QMessageBox.warning(
                    self,
                    "Raccourci indisponible",
                    f"Le raccourci '{prompt_hotkey}' n'a pas été enregistré.\n\n"
                    f"{current_error}",
                )
                return
        
        # Mettre à jour le nom dans le combo
        self.prompt_combo.setItemText(self.prompt_combo.currentIndex(), name)

        self.populate_prompt_order_list()
        
        QMessageBox.information(self, "Prompt enregistré", 
                              f"Le prompt '{name}' a été enregistré avec succès.")

    def reset_prompt(self):
        from supermenu_core.ui.text_prompt_form import reset_text_prompt
        reset_text_prompt(self.settings, self.prompt_combo.currentData(), self, self._prompts_restored)

    def _prompts_restored(self):
        self.populate_prompt_combo()
        self.populate_prompt_order_list()
        if self.prompt_hotkey_manager is not None:
            self.prompt_hotkey_manager.refresh_hotkeys()

    def restore_prompt_library(self):
        restore_library(self, self.settings, self._prompts_restored)

    def add_prompt(self):
        """Ajouter un nouveau prompt"""
        # Demander le nom affiché du nouveau prompt
        prompt_name, ok = QInputDialog.getText(
            self,
            "Nouveau prompt",
            "Entrez le nom du nouveau prompt :"
        )
        
        if not ok or not prompt_name:
            return
        
        prompt_name = prompt_name.strip()
        prompt_id = Validators.normalize_prompt_id(prompt_name)

        if not prompt_id:
            QMessageBox.warning(
                self,
                "Nom invalide",
                "Le nom du prompt ne peut pas être vide."
            )
            return
        
        # Créer un nouveau prompt avec des valeurs par défaut
        new_prompt_id = self.settings.add_prompt(
            prompt_id,
            prompt_name,
            "",
            "Traitement en cours...",
            False,
            999,
            hotkey="",
        )
        
        # Mettre à jour la liste des prompts
        self.populate_prompt_combo()

        self.populate_prompt_order_list()
        
        # Sélectionner le nouveau prompt
        index = self.prompt_combo.findData(new_prompt_id)
        if index >= 0:
            self.prompt_combo.setCurrentIndex(index)
            self.load_prompt(index)
        
        # Afficher un message de confirmation
        QMessageBox.information(
            self,
            "Prompt ajouté",
            f"Le nouveau prompt '{prompt_name}' a été ajouté avec succès. Vous pouvez maintenant le personnaliser."
        )

    def delete_prompt(self):
        """Supprimer un prompt"""
        # Vérifier qu'un prompt est sélectionné
        index = self.prompt_combo.currentIndex()
        if index < 0:
            return
        
        # Obtenir l'ID et le nom du prompt
        prompt_id = self.prompt_combo.itemData(index)
        prompt_name = self.prompt_combo.itemText(index)
        
        # Vérifier qu'il reste au moins un prompt après suppression
        if self.prompt_combo.count() <= 1:
            QMessageBox.warning(
                self,
                "Impossible de supprimer",
                "Vous ne pouvez pas supprimer le dernier prompt. Il doit toujours y avoir au moins un prompt disponible."
            )
            return
        
        # Demander confirmation
        reply = QMessageBox.question(
            self,
            "Confirmer la suppression",
            f"Êtes-vous sûr de vouloir supprimer le prompt '{prompt_name}' ?\n\nCette action est irréversible.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Supprimer le prompt
        if self.settings.delete_prompt(prompt_id):
            if self.prompt_hotkey_manager is not None:
                self.prompt_hotkey_manager.refresh_hotkeys()
            # Mettre à jour la liste des prompts
            self.populate_prompt_combo()

            self.populate_prompt_order_list()
            
            # Sélectionner le premier prompt
            if self.prompt_combo.count() > 0:
                self.prompt_combo.setCurrentIndex(0)
                self.load_prompt(0)
            
            # Afficher un message de confirmation
            QMessageBox.information(
                self,
                "Prompt supprimé",
                f"Le prompt '{prompt_name}' a été supprimé avec succès."
            )
        else:
            # Afficher un message d'erreur
            QMessageBox.warning(
                self,
                "Erreur",
                f"Impossible de supprimer le prompt '{prompt_name}'."
            )

    def populate_prompt_combo(self):
        """Populate the prompt combo box with available prompts"""
        current_prompt_id = None
        try:
            current_prompt_id = self.prompt_combo.currentData()
        except Exception:
            current_prompt_id = None

        self.prompt_combo.clear()

        prompts = self.settings.get_prompts()

        sorted_prompts = sorted(prompts.items(), key=lambda x: x[1].get("position", 999))
        for prompt_id, prompt_data in sorted_prompts:
            self.prompt_combo.addItem(prompt_data["name"], prompt_id)

        if current_prompt_id is not None:
            index = self.prompt_combo.findData(current_prompt_id)
            if index >= 0:
                self.prompt_combo.setCurrentIndex(index)

    def populate_prompt_order_list(self):
        try:
            current_prompt_id = None
            try:
                current_prompt_id = self.prompt_combo.currentData()
            except Exception:
                current_prompt_id = None

            query = ""
            try:
                query = (self.prompt_search_input.text() or "").strip().lower()
            except Exception:
                query = ""
            is_filtered = bool(query)

            self._is_updating_prompt_order_list = True
            self.prompt_order_list.clear()

            if is_filtered:
                self.prompt_order_list.setDragDropMode(QAbstractItemView.NoDragDrop)
                self.prompt_order_list.setDropIndicatorShown(False)
            else:
                self.prompt_order_list.setDragDropMode(QAbstractItemView.InternalMove)
                self.prompt_order_list.setDropIndicatorShown(True)

            prompts = self.settings.get_prompts()
            sorted_prompts = sorted(prompts.items(), key=lambda x: x[1].get("position", 999))
            for prompt_id, prompt_data in sorted_prompts:
                name = prompt_data.get("name", str(prompt_id))
                if is_filtered and query not in (name or "").lower():
                    continue
                item = QListWidgetItem(name)
                item.setToolTip(item.text())
                item.setData(Qt.UserRole, prompt_id)
                self.prompt_order_list.addItem(item)

            if current_prompt_id is not None:
                for row in range(self.prompt_order_list.count()):
                    if self.prompt_order_list.item(row).data(Qt.UserRole) == current_prompt_id:
                        self.prompt_order_list.setCurrentRow(row)
                        break
        finally:
            self._is_updating_prompt_order_list = False

    def _apply_prompt_filter(self, *args):
        self.populate_prompt_order_list()

    def _on_prompt_list_current_changed(self, current, previous):
        if getattr(self, "_is_updating_prompt_order_list", False):
            return
        if current is None:
            return
        prompt_id = current.data(Qt.UserRole)
        if prompt_id is None:
            return
        index = self.prompt_combo.findData(prompt_id)
        if index >= 0 and index != self.prompt_combo.currentIndex():
            self.prompt_combo.setCurrentIndex(index)

    def on_prompt_order_changed(self, *args):
        if getattr(self, "_is_updating_prompt_order_list", False):
            return

        prompts = self.settings.get_prompts()
        changed = False
        for row in range(self.prompt_order_list.count()):
            item = self.prompt_order_list.item(row)
            prompt_id = item.data(Qt.UserRole)
            if prompt_id not in prompts:
                continue
            prompt_data = prompts[prompt_id]
            new_position = (row + 1) * 10
            if prompt_data.get("position", 999) == new_position:
                continue
            prompt_data["position"] = new_position
            changed = True

        if changed:
            self.settings.set_prompts(prompts)

        self.populate_prompt_combo()
        self.populate_prompt_order_list()

    def export_all_prompts(self):
        """Export all text and voice prompts to a JSON file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Exporter les Prompts", 
            os.path.join(os.path.expanduser("~"), "supermenu_prompts.json"), 
            "JSON Files (*.json)"
        )
        if file_path:
            success, message = self.settings.export_prompts(file_path)
            if success:
                QMessageBox.information(self, "Exportation Réussie", message)
            else:
                QMessageBox.warning(self, "Erreur d'Exportation", message)

    def import_all_prompts(self):
        """Import all text and voice prompts from a JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Importer les Prompts", 
            os.path.expanduser("~"), 
            "JSON Files (*.json)"
        )
        if file_path:
            reply = QMessageBox.question(self, "Confirmer l'Importation", 
                                           "L'importation remplacera tous vos prompts actuels. Voulez-vous continuer?",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                success, message = self.settings.import_prompts(file_path)
                if success:
                    shortcut_errors = {}
                    prompt_hotkey_manager = getattr(
                        self,
                        "prompt_hotkey_manager",
                        None,
                    )
                    if prompt_hotkey_manager is not None:
                        _registered, shortcut_errors = (
                            prompt_hotkey_manager.refresh_hotkeys()
                        )
                    QMessageBox.information(self, "Importation Réussie", message)
                    # Rafraîchir les listes de prompts dans l'UI
                    self.populate_prompt_combo()
                    self.voice_prompt_editor.reload()
                    # Optionnellement, sélectionner le premier prompt ou aucun
                    if self.prompt_combo.count() > 0:
                        self.prompt_combo.setCurrentIndex(0)
                        self.load_prompt(0)
                    else:
                        self.clear_prompt_editor()
                    # The sidebar list is the visible selector: rebuild it too.
                    populate_prompt_order_list = getattr(
                        self,
                        "populate_prompt_order_list",
                        None,
                    )
                    if populate_prompt_order_list is not None:
                        populate_prompt_order_list()
                    
                    if shortcut_errors:
                        QMessageBox.warning(
                            self,
                            "Certains raccourcis sont indisponibles",
                            "\n".join(
                                f"- {prompt_id}: {error}"
                                for prompt_id, error in shortcut_errors.items()
                            ),
                        )
                else:
                    QMessageBox.warning(self, "Erreur d'Importation", message)

    def clear_prompt_editor(self):
        self.prompt_name_input.clear()
        self.prompt_text_input.clear()
        self.prompt_status_input.clear()
        self.prompt_insert_directly.setChecked(False)
        self.text_prompt_form.reasoning.set_mode("default")
        self.text_prompt_form.model_choice.set_target({})
        self.prompt_hotkey_input.clear()
