"""Dictation delivery and shortcut preferences for both desktop apps."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from .controls import ChoiceBox


class DictationBehaviorSettings(QGroupBox):
    def __init__(self, settings, parent=None):
        super().__init__("Après la dictée", parent)
        self.settings = settings
        layout = QVBoxLayout(self)
        self.auto_insert = QCheckBox(
            "Coller automatiquement quand la dictée se termine"
        )
        self.auto_insert.setChecked(settings.get_dictation_auto_insert())
        layout.addWidget(self.auto_insert)
        self.correct_before_insert = QCheckBox(
            "Corriger avec le moteur de texte avant d’insérer"
        )
        self.correct_before_insert.setChecked(
            settings.get_dictation_correct_before_insert()
        )
        layout.addWidget(self.correct_before_insert)
        hint = QLabel(
            "Sinon, Copier et Insérer restent disponibles dans la fenêtre de dictée. La correction utilise le moteur choisi dans Texte et peut donc envoyer la dictée à ce service. Ces options ne modifient pas les prompts vocaux."
        )
        hint.setWordWrap(True)
        hint.setObjectName("mutedText")
        layout.addWidget(hint)
        self.auto_insert.toggled.connect(self.save)
        self.correct_before_insert.toggled.connect(self.save)

    def save(self):
        self.settings.set_dictation_auto_insert(self.auto_insert.isChecked())
        self.settings.set_dictation_correct_before_insert(
            self.correct_before_insert.isChecked()
        )
        self.settings.sync()


class DictationShortcutSettings(QGroupBox):
    record_requested = Signal()

    def __init__(self, settings, manager=None, parent=None):
        super().__init__("Dictée instantanée", parent)
        self.settings, self.manager = settings, manager
        layout = QVBoxLayout(self)
        hint = QLabel(
            "Démarrer une dictée depuis l’application où vous écrivez, sans ouvrir le menu."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        row = QHBoxLayout()
        self.shortcut = QLineEdit(settings.get_dictation_hotkey())
        self.shortcut.setReadOnly(True)
        self.shortcut.setPlaceholderText("Aucun raccourci — cliquez sur Définir")
        row.addWidget(self.shortcut, 1)
        record = QPushButton("Définir")
        record.clicked.connect(self.record_requested)
        row.addWidget(record)
        clear = QPushButton("Effacer")
        clear.clicked.connect(lambda: self.set_shortcut(""))
        row.addWidget(clear)
        layout.addLayout(row)
        self.mode = ChoiceBox()
        self.mode.addItem("Appuyer une fois — arrêter avec Terminer", "press")
        self.mode.addItem("Maintenir pour parler — relâcher pour terminer", "hold")
        self.mode.setCurrentIndex(
            self.mode.findData(settings.get_dictation_hotkey_mode())
        )
        self.mode.currentIndexChanged.connect(self.save_mode)
        layout.addWidget(self.mode)
        self.feedback = QLabel()
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)

    def save_mode(self):
        self.settings.set_dictation_hotkey_mode(self.mode.currentData())
        self.settings.sync()
        self.feedback.setText("Mode de dictée enregistré.")

    def set_shortcut(self, shortcut):
        if self.manager is not None and not self.manager.set_hotkey(shortcut):
            error = getattr(self.manager, "last_register_error", "") or getattr(
                self.manager, "_last_register_error", ""
            )
            self.feedback.setText(f"Raccourci indisponible : {error}")
            return False
        self.settings.set_dictation_hotkey(shortcut)
        self.settings.sync()
        self.shortcut.setText(shortcut)
        self.feedback.setText(
            "Raccourci enregistré." if shortcut else "Raccourci désactivé."
        )
        return True
