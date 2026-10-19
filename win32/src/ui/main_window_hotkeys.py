"""Raccourcis de la fenêtre principale : enregistrement, état et réenregistrement."""

from PySide6.QtWidgets import QMessageBox


def _hotkey_error(manager):
    """Registration error of a shortcut Windows refused, "" when it is active."""
    if manager is None:
        return ""
    error = getattr(manager, "last_error", "")
    if error and not getattr(manager, "registered", False):
        return error
    return ""


class HotkeyActionsMixin:
    """Global and per-prompt hotkey recording for the main window."""

    def change_hotkey(self):
        """Modifier le raccourci clavier"""
        if not self.hotkey_manager:
            # Cette situation ne devrait plus se produire si HotkeyManager est toujours passé
            QMessageBox.warning(self, "Erreur", "HotkeyManager non initialisé.")
            return

        if self._change_core_hotkey(self.hotkey_manager):
            QMessageBox.information(
                self,
                "Raccourci modifié",
                f"Le raccourci a été modifié avec succès en {self.settings.get_hotkey()}.\n\n"
                "Le nouveau raccourci est maintenant actif."
            )

    def _change_core_hotkey(self, manager):
        """Record and apply a main shortcut; True once the new one is active."""
        try:
            hotkey = self._record_hotkey_with_shortcuts_released()
            if not hotkey:
                return False
            # Every other shortcut is registered again at this point, so a
            # combination already used by SuperMenu is refused and rolled back.
            if manager.set_hotkey(hotkey):
                return True
            QMessageBox.warning(
                self,
                "Erreur",
                f"Impossible d'enregistrer le raccourci '{hotkey}'.\n\n"
                f"{getattr(manager, 'last_error', '')}",
            )
            return False
        finally:
            self._refresh_hotkey_states()

    def record_dictation_hotkey(self):
        shortcut = self._record_hotkey_with_shortcuts_released()
        if shortcut:
            self.dictation_shortcut_settings.set_shortcut(shortcut)

    def record_prompt_hotkey(self):
        """Capture a shortcut for the selected prompt without saving it yet."""
        if self.prompt_combo.count() == 0:
            return

        shortcut = self._record_hotkey_with_shortcuts_released()
        if shortcut:
            self.prompt_hotkey_input.setText(shortcut)

    def clear_prompt_hotkey(self):
        """Clear the shortcut editor; the change is applied when saving."""
        self.prompt_hotkey_input.clear()

    def change_voice_hotkey(self):
        """Modifier le raccourci vocal"""
        if not self.voice_hotkey_manager:
            # Cette situation ne devrait plus se produire
            QMessageBox.warning(self, "Erreur", "VoiceHotkeyManager non initialisé.")
            return

        if self._change_core_hotkey(self.voice_hotkey_manager):
            QMessageBox.information(
                self,
                "Raccourci modifié",
                f"Le raccourci vocal a été modifié avec succès en {self.settings.get_voice_hotkey()}.\n\n"
                "Le nouveau raccourci est maintenant actif."
            )

    def change_custom_hotkey(self):
        """Modifier le raccourci du mode personnalisé"""
        if not self.custom_hotkey_manager:
            QMessageBox.warning(self, "Erreur", "CustomHotkeyManager non initialisé.")
            return

        if self._change_core_hotkey(self.custom_hotkey_manager):
            QMessageBox.information(
                self,
                "Raccourci modifié",
                f"Le raccourci du mode personnalisé a été modifié avec succès en {self.settings.get_custom_hotkey()}.\n\n"
                "Le nouveau raccourci est maintenant actif."
            )

    def change_screenshot_hotkey(self):
        """Modifier le raccourci de capture d'écran"""
        if not self.screenshot_hotkey_manager:
            # Cette situation ne devrait plus se produire
            QMessageBox.warning(self, "Erreur", "ScreenshotHotkeyManager non initialisé.")
            return

        if self._change_core_hotkey(self.screenshot_hotkey_manager):
            QMessageBox.information(
                self,
                "Raccourci modifié",
                f"Le raccourci de capture d'écran a été modifié avec succès en {self.settings.get_screenshot_hotkey()}.\n\n"
                "Le nouveau raccourci est maintenant actif."
            )

    def _core_hotkey_rows(self):
        """(manager, field, configured shortcut) of the Shortcuts tab rows."""
        return (
            (self.hotkey_manager, self.hotkey_label, self.settings.get_hotkey),
            (self.custom_hotkey_manager, self.custom_hotkey_label, self.settings.get_custom_hotkey),
            (self.voice_hotkey_manager, self.voice_hotkey_label, self.settings.get_voice_hotkey),
            (self.screenshot_hotkey_manager, self.screenshot_hotkey_label, self.settings.get_screenshot_hotkey),
        )

    def _refresh_hotkey_states(self):
        """Show the configured shortcuts, marking those Windows refused."""
        for manager, field, configured_hotkey in self._core_hotkey_rows():
            hotkey = configured_hotkey()
            error = _hotkey_error(manager)
            if error:
                field.setText(f"{hotkey} (inactif)" if hotkey else "Inactif")
                field.setToolTip(f"Inactif : {error}")
            else:
                field.setText(hotkey)
                field.setToolTip("")

    def _on_hotkey_registration_failed(self, _error):
        self._refresh_hotkey_states()

    def _inactive_core_hotkeys(self):
        """Main shortcuts Windows refused: list of (feature, shortcut, error)."""
        failures = []
        for manager in (
            self.hotkey_manager,
            self.custom_hotkey_manager,
            self.voice_hotkey_manager,
            self.screenshot_hotkey_manager,
            self.dictation_hotkey_manager,
        ):
            error = _hotkey_error(manager)
            if error:
                failures.append((
                    getattr(manager, "feature_name", "Raccourci"),
                    getattr(manager, "hotkey", "") or "aucun",
                    error,
                ))
        return failures

    def _reregister_all_hotkeys(self, previous_hotkeys):
        """Apply all reset hotkeys together and roll them back on conflict."""
        managers = [
            self.hotkey_manager,
            self.voice_hotkey_manager,
            self.screenshot_hotkey_manager,
            self.custom_hotkey_manager,
            getattr(self, "dictation_hotkey_manager", None),
        ]
        active_managers = [manager for manager in managers if manager is not None]

        for manager in active_managers:
            manager.unregister_hotkey()

        try:
            for manager in active_managers:
                if not manager.register_hotkey():
                    raise RuntimeError(
                        getattr(manager, "_last_register_error", "")
                        or "échec d'enregistrement du raccourci"
                    )
            return True
        except Exception:
            for manager in active_managers:
                manager.unregister_hotkey()

            self.settings.set_hotkey(previous_hotkeys["hotkey"])
            self.settings.set_voice_hotkey(previous_hotkeys["voice_hotkey"])
            self.settings.set_screenshot_hotkey(
                previous_hotkeys["screenshot_hotkey"]
            )
            self.settings.set_custom_hotkey(previous_hotkeys["custom_hotkey"])
            if "dictation_hotkey" in previous_hotkeys:
                self.settings.set_dictation_hotkey(previous_hotkeys["dictation_hotkey"])
            self.settings.sync()

            for manager in active_managers:
                manager.register_hotkey()
            return False
