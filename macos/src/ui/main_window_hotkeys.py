"""Raccourcis de la fenêtre principale : enregistrement et rechargement."""

from __future__ import annotations

from src.utils.hotkey_manager import HotkeyRecorderDialog
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QTimer, Qt
from supermenu_core.config.feature_modes import experimental_enabled
from src.utils.logger import log


class HotkeyActionsMixin:
    """Global and per-prompt hotkey recording for the main window."""

    def record_dictation_hotkey(self):
        self._open_hotkey_recorder(self.dictation_shortcut_settings.set_shortcut)

    def record_main_hotkey(self):
        if self.hotkey_manager:
            self._open_hotkey_recorder(
                lambda hotkey: self._apply_recorded_hotkey(
                    self.hotkey_manager,
                    self.main_hotkey,
                    hotkey,
                )
            )

    def record_custom_hotkey(self):
        if self.custom_hotkey_manager:
            self._open_hotkey_recorder(
                lambda hotkey: self._apply_recorded_hotkey(
                    self.custom_hotkey_manager,
                    self.custom_hotkey,
                    hotkey,
                )
            )

    def _open_hotkey_recorder(self, on_recorded):
        if self._hotkey_dialog is not None:
            self._hotkey_dialog.raise_()
            self._hotkey_dialog.activateWindow()
            return
        service = None
        for manager in (
            self.hotkey_manager,
            self.custom_hotkey_manager,
            self.dictation_hotkey_manager,
            self.prompt_hotkey_manager,
        ):
            if manager is not None:
                service = manager.service
                break
        if service is not None:
            service.suspend()
        dialog = HotkeyRecorderDialog(self)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._hotkey_dialog = dialog

        def finish_recording(result):
            recorded = dialog.recorded_hotkey
            self._hotkey_dialog = None
            if (
                result == HotkeyRecorderDialog.DialogCode.Accepted
                and recorded
            ):
                on_recorded(recorded)
            dialog.deleteLater()
            if service is not None:
                # Listening again while the just-recorded combination is still
                # held would fire it immediately. The condition is the user's
                # fingers, not a delay: wait for the modifiers to come up, and
                # resume at once when nothing is held.
                self._keys.when_modifiers_released(
                    QTimer.singleShot,
                    service.resume,
                )

        dialog.finished.connect(finish_recording)
        dialog.open()

    def _apply_recorded_hotkey(self, manager, field, hotkey):
        if manager.set_hotkey(hotkey):
            field.setText(hotkey)
            self.settings.sync()
            self._retry_prompt_hotkeys()
            return
        QMessageBox.warning(
            self,
            "Raccourci non enregistré",
            manager.last_register_error,
        )

    def record_prompt_hotkey(self):
        self._open_hotkey_recorder(self.prompt_hotkey.setText)

    def _reload_all_hotkeys(self):
        results = []
        for manager in (self.hotkey_manager, self.custom_hotkey_manager, getattr(self, "dictation_hotkey_manager", None)):
            if manager is not None:
                results.append(manager.register_hotkey())
        if self.prompt_hotkey_manager is not None:
            prompt_ok, _errors = self.prompt_hotkey_manager.refresh_hotkeys()
            results.append(prompt_ok)
        return all(results) if results else True

    def refused_hotkey_messages(self):
        """Describe the saved shortcuts that validation leaves inactive.

        Recording them again fixes these; relaunching SuperMenu would refuse
        the same saved value again.
        """
        messages = []
        dictation_manager = (
            getattr(self, "dictation_hotkey_manager", None)
            if experimental_enabled(self.settings)
            else None
        )
        for label, manager in (
            ("Menu principal", self.hotkey_manager),
            ("Mode personnalisé", self.custom_hotkey_manager),
            ("Dictée instantanée", dictation_manager),
        ):
            error = getattr(manager, "refused_hotkey_error", "") if manager else ""
            if error:
                messages.append(f"{label} : {error}")
        if self.prompt_hotkey_manager is not None:
            errors = dict(getattr(self.prompt_hotkey_manager, "errors", {}) or {})
            # A service failure is not a refused shortcut.
            errors.pop("registration", None)
            prompts = self.settings.get_prompts()
            for prompt_id, error in errors.items():
                messages.append(
                    self._prompt_hotkey_error({prompt_id: error}, prompts)
                )
        return messages

    def _retry_prompt_hotkeys(self, *_args):
        """Bind a prompt shortcut freed by a new main, custom or dictation one.

        A prompt shortcut left unbound because another SuperMenu shortcut
        held it comes back as soon as that one moves, as the « Raccourcis
        inactifs » warning promises, without waiting for a relaunch.
        """
        manager = self.prompt_hotkey_manager
        if manager is not None and getattr(manager, "errors", None):
            self._refresh_prompt_hotkeys()

    def _refresh_prompt_hotkeys(self):
        if self.prompt_hotkey_manager:
            success, errors = self.prompt_hotkey_manager.refresh_hotkeys()
            if not success:
                log(f"Raccourcis de prompts invalides : {errors}")
            return success, errors
        return True, {}
