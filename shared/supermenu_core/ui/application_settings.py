"""Appearance, update and feature controls independent of OS integration."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from supermenu_core.config.feature_modes import (
    advanced_enabled,
    experimental_enabled,
    prompts_with_model_target,
)
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


TEXT_ENGINE_NAMES = {
    "openai": "OpenAI",
    "custom": "Ollama / LM Studio",
    "foundry": "Foundry Local",
    "apple": "Apple Intelligence",
}


def _muted_label(text):
    label = QLabel(text)
    label.setObjectName("mutedText")
    label.setWordWrap(True)
    return label


class FeatureModeSettings(QGroupBox):
    """Fonctions avancées et expérimentales, appliquées par le bouton Appliquer.

    La plateforme appelle save() depuis son bouton Appliquer et réagit à
    modes_changed(avancées, expérimentales) pour afficher ou masquer ses
    fonctions. Désactiver une fonction ne supprime aucun réglage.
    """

    modes_changed = Signal(bool, bool)

    def __init__(
        self, settings, parent=None, *, screen_capture=False, text_model_retention=False
    ):
        super().__init__("Fonctions", parent)
        self.settings = settings
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.addWidget(
            _muted_label(
                "SuperMenu affiche l’essentiel par défaut. Activez des fonctions "
                "supplémentaires selon vos besoins."
            )
        )
        retention = (
            "durée de conservation des modèles locaux en mémoire"
            if text_model_retention
            else "durée de conservation du modèle vocal local"
        )
        advanced_text = (
            "Choix du modèle, du fournisseur ou du poste LM Link pour chaque "
            f"prompt, raccourci direct par prompt et {retention}. Désactivées : "
            "chaque prompt utilise le moteur et le modèle des réglages Texte."
        )
        experimental_text = (
            "Prompts vocaux, dictée instantanée, réglages de la dictée, test du "
            "micro, ainsi que capture et analyse d’écran. Ces fonctions peuvent "
            "encore évoluer."
            if screen_capture
            else "Prompts vocaux, dictée instantanée, réglages de la dictée et "
            "test du micro. Ces fonctions peuvent encore évoluer."
        )
        self.advanced_check = QCheckBox("Fonctions avancées")
        self.advanced_check.setAccessibleName("Activer les fonctions avancées")
        self.advanced_check.setAccessibleDescription(advanced_text)
        layout.addWidget(self.advanced_check)
        self.advanced_description = _muted_label(advanced_text)
        layout.addWidget(self.advanced_description)
        self.experimental_check = QCheckBox("Fonctions expérimentales")
        self.experimental_check.setAccessibleName(
            "Activer les fonctions expérimentales"
        )
        self.experimental_check.setAccessibleDescription(experimental_text)
        layout.addWidget(self.experimental_check)
        self.experimental_description = _muted_label(experimental_text)
        layout.addWidget(self.experimental_description)
        layout.addWidget(
            _muted_label(
                "Cliquez sur Appliquer pour afficher ou masquer ces fonctions, "
                "sans redémarrer. Les désactiver ne supprime rien : vos réglages "
                "et vos prompts sont conservés et réapparaissent si vous les "
                "réactivez."
            )
        )
        self.refresh()

    def refresh(self):
        """Show the saved switches, discarding unapplied changes."""
        self.advanced_check.setChecked(bool(advanced_enabled(self.settings)))
        self.experimental_check.setChecked(bool(experimental_enabled(self.settings)))

    def has_unsaved_changes(self):
        return (
            self.advanced_check.isChecked() != bool(advanced_enabled(self.settings))
            or self.experimental_check.isChecked()
            != bool(experimental_enabled(self.settings))
        )

    def _text_engine_name(self):
        try:
            provider = self.settings.get_ai_provider()
        except Exception:
            provider = None
        return TEXT_ENGINE_NAMES.get(provider, "réglage général")

    def _confirm_disabling_advanced(self):
        count = prompts_with_model_target(self.settings)
        if count <= 0:
            return True
        reply = QMessageBox.question(
            self,
            "Désactiver les fonctions avancées",
            f"{count} prompt(s) utilisent un modèle choisi pour eux. Fonctions "
            "avancées désactivées, ils utiliseront le moteur des réglages Texte "
            f"({self._text_engine_name()}), éventuellement en ligne. Leurs "
            "réglages sont conservés. Continuer ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def save(self):
        """Persist the switches; emit modes_changed only when one changed.

        Returns True when a switch changed. Turning the advanced features off
        while prompts have their own model asks first: refusing keeps them on.
        """
        saved_advanced = bool(advanced_enabled(self.settings))
        saved_experimental = bool(experimental_enabled(self.settings))
        advanced = self.advanced_check.isChecked()
        experimental = self.experimental_check.isChecked()
        if advanced == saved_advanced and experimental == saved_experimental:
            return False
        if saved_advanced and not advanced and not self._confirm_disabling_advanced():
            advanced = True
            self.advanced_check.setChecked(True)
            if experimental == saved_experimental:
                return False
        self.settings.set_advanced_features_enabled(advanced)
        self.settings.set_experimental_features_enabled(experimental)
        self.settings.sync()
        self.modes_changed.emit(advanced, experimental)
        return True
