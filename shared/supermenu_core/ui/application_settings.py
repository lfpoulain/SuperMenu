"""Appearance and update controls independent of OS integration."""

from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton

from .controls import ChoiceBox
from .settings_panel import form_layout
from .theme_manager import ThemeManager


class ApplicationSettings(QGroupBox):
    def __init__(self, settings, check_updates, parent=None):
        super().__init__("Interface et mises à jour", parent)
        self.settings = settings
        form = form_layout(self)
        self.theme_combo = ChoiceBox()
        for key, label in ThemeManager.get_theme_names().items():
            self.theme_combo.addItem(label, key)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(settings.get_theme())))
        form.addRow("Thème", self.theme_combo)
        self.channel_combo = ChoiceBox()
        self.channel_combo.addItem("Stable", "stable")
        self.channel_combo.addItem("Bêta", "beta")
        self.channel_combo.setCurrentIndex(max(0, self.channel_combo.findData(settings.get_update_channel())))
        form.addRow("Canal de mise à jour", self.channel_combo)
        self.channel_hint = QLabel()
        self.channel_hint.setWordWrap(True)
        form.addRow(self.channel_hint)
        check = QPushButton("Vérifier les mises à jour")
        check.clicked.connect(check_updates)
        form.addRow(check)
        self.channel_combo.currentIndexChanged.connect(self._save_channel)
        self.refresh_channel()

    def refresh_channel(self):
        self.channel_hint.setText(
            "Versions de test : elles peuvent contenir des régressions. Le canal choisi est enregistré automatiquement."
            if self.channel_combo.currentData() == "beta" else
            "Versions stables validées. Le canal choisi est enregistré automatiquement."
        )

    def _save_channel(self):
        channel = self.channel_combo.currentData()
        if channel != self.settings.get_update_channel():
            self.settings.set_update_channel(channel)
            self.settings.set_last_update_check_date("")
            self.settings.sync()
        self.refresh_channel()
