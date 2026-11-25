"""Mise à jour de la fenêtre principale : vérification et annonce des versions."""

from __future__ import annotations

from src.config.build_info import APP_VERSION
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QUrl, Signal
from src.ui.background_worker import _BackgroundWorker
from src.utils import updater as app_updater
from src.utils.logger import log
from datetime import date


class UpdateCheckWorker(_BackgroundWorker):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, channel: str):
        super().__init__()
        self.channel = channel

    def run(self):
        try:
            self.finished_ok.emit(app_updater.check_latest_release(self.channel))
        except Exception as exc:
            self.failed.emit(str(exc))


class UpdateActionsMixin:
    """Update checks and release notices of the main window."""

    def schedule_startup_update_check(self):
        today = date.today().isoformat()
        if self.settings.get_last_update_check_date() != today:
            self.check_for_updates(silent=True)

    def check_for_updates(self, silent=False):
        if self._update_worker is not None and self._update_worker.isRunning():
            return
        worker = UpdateCheckWorker(self.settings.get_update_channel())
        self._update_worker = worker
        worker.finished_ok.connect(
            lambda release: self._update_finished(release, silent)
        )
        worker.failed.connect(lambda error: self._update_failed(error, silent))
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda: setattr(self, "_update_worker", None))
        worker.start()

    def _update_finished(self, release, silent):
        self.settings.set_last_update_check_date(date.today().isoformat())
        self.settings.sync()
        version = release.get("version", "")
        if app_updater.is_newer_version(APP_VERSION, version):
            self._bring_application_forward()
            if QMessageBox.question(
                self,
                "Mise à jour disponible",
                f"La version {version} est disponible. Télécharger le DMG ?",
            ) == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(release.get("url", "")))
        elif not silent:
            self._bring_application_forward()
            QMessageBox.information(
                self,
                "SuperMenu à jour",
                "Aucune version plus récente n’est disponible.",
            )

    def _bring_application_forward(self):
        """Make SuperMenu frontmost before a message box asks something.

        A menu bar application is not activated by its status menu, nor by a
        check that ends in the background: its modal box would open behind
        the frontmost application and block SuperMenu's windows unseen.
        """
        try:
            self.show_main_window()
        except Exception as exc:
            log(f"Activation avant le message de mise à jour impossible : {exc}")

    def _update_failed(self, error, silent):
        if not silent:
            self._bring_application_forward()
            QMessageBox.warning(self, "Mise à jour", error)
