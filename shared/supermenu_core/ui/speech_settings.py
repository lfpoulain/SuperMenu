"""Choose and prepare a voice engine independently of the text engine."""

from datetime import datetime
import sys

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from supermenu_core.audio.microphone import microphones
from supermenu_core.audio.settings import languages, local_language
from .verification_status import VerificationStatus


class SpeechSettingsWidget(QGroupBox):
    settings_saved = Signal()
    dictation_requested = Signal()

    def __init__(self, settings, backend_factory, parent=None, *, platform=None):
        super().__init__("Dictée et transcription en direct", parent)
        self.settings, self.backend_factory = settings, backend_factory
        self.backend = None
        self.platform = platform or sys.platform
        layout = QVBoxLayout(self)
        description = QLabel(
            "Choisissez le moteur qui transforme votre voix en texte. Ce choix est indépendant du moteur de correction et de traduction."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("OpenAI — GPT Live Transcribe (en ligne)", "openai")
        if self.platform == "darwin":
            self.provider_combo.addItem("Apple Speech — local sur ce Mac", "apple")
        else:
            self.provider_combo.addItem(
                "Foundry Local — Nemotron 3.5 (local)", "foundry"
            )
        index = self.provider_combo.findData(settings.get_speech_provider())
        self.provider_combo.setCurrentIndex(max(0, index))
        layout.addWidget(self.provider_combo)
        self.description = QLabel()
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self.device_combo = QComboBox()
        self.device_combo.addItem("Automatique — CUDA en priorité", "auto")
        self.device_combo.addItem("CPU uniquement", "cpu")
        self.device_combo.setCurrentIndex(
            self.device_combo.findData(settings.get_speech_device())
        )
        layout.addWidget(self.device_combo)
        layout.addWidget(QLabel("Microphone"))
        self.microphone_combo = QComboBox()
        mic_row = QHBoxLayout()
        mic_row.addWidget(self.microphone_combo, 1)
        refresh = QPushButton("Actualiser")
        refresh.clicked.connect(self.refresh_microphones)
        mic_row.addWidget(refresh)
        layout.addLayout(mic_row)
        self.refresh_microphones()
        layout.addWidget(QLabel("Langue de dictée"))
        self.languages_input = QLineEdit(settings.get_transcription_languages())
        self.languages_input.setPlaceholderText("fr — vide = détection automatique")
        layout.addWidget(self.languages_input)
        self.language_hint = QLabel()
        self.language_hint.setWordWrap(True)
        layout.addWidget(self.language_hint)
        self.cloud_group = QGroupBox("OpenAI")
        cloud = QVBoxLayout(self.cloud_group)
        cloud.addWidget(QLabel("Clé API OpenAI — partagée avec le moteur de texte"))
        self.api_key_input = QLineEdit(settings.get_api_key() or "")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Clé API OpenAI")
        cloud.addWidget(self.api_key_input)
        cloud.addWidget(QLabel("Vocabulaire et contexte facultatifs"))
        self.keywords_input = QLineEdit(settings.get_transcription_keywords())
        self.keywords_input.setPlaceholderText("Vocabulaire : SuperMenu, noms propres…")
        cloud.addWidget(self.keywords_input)
        self.prompt_input = QTextEdit()
        self.prompt_input.setAcceptRichText(False)
        self.prompt_input.setMaximumHeight(65)
        self.prompt_input.setPlaceholderText(
            "Contexte : dictée technique sur une application Python…"
        )
        self.prompt_input.setPlainText(settings.get_transcription_prompt())
        cloud.addWidget(self.prompt_input)
        layout.addWidget(self.cloud_group)
        self.status = VerificationStatus()
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.check_button = QPushButton("Vérifier")
        self.check_button.clicked.connect(lambda: self.prepare("probe"))
        actions.addWidget(self.check_button)
        self.download_button = QPushButton("Télécharger le modèle vocal")
        self.download_button.clicked.connect(lambda: self.prepare("download"))
        actions.addWidget(self.download_button)
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)
        bottom = QHBoxLayout()
        self.save_button = QPushButton("Enregistrer la dictée")
        self.save_button.clicked.connect(self.save)
        bottom.addWidget(self.save_button)
        self.test_button = QPushButton("Dicter")
        self.test_button.clicked.connect(self._dictate)
        bottom.addWidget(self.test_button)
        layout.addLayout(bottom)
        for widget in (self.provider_combo, self.device_combo):
            widget.currentIndexChanged.connect(self._changed)
        self.languages_input.textChanged.connect(self._changed)
        self.api_key_input.textChanged.connect(self._changed)
        self._changed()

    def refresh_microphones(self):
        selected = (
            self.microphone_combo.currentData() or self.settings.get_speech_microphone()
        )
        self.microphone_combo.clear()
        self.microphone_combo.addItem("Microphone par défaut du système", "")
        for identifier, name in microphones():
            self.microphone_combo.addItem(name, identifier)
        index = self.microphone_combo.findData(selected)
        if selected and index < 0:
            self.microphone_combo.addItem(
                "Microphone enregistré — déconnecté", selected
            )
            index = self.microphone_combo.count() - 1
        self.microphone_combo.setCurrentIndex(max(0, index))

    def options(self):
        provider = self.provider_combo.currentData()
        expected = self.languages_input.text().strip()
        words = [s.strip() for s in self.keywords_input.text().split(",") if s.strip()]
        if provider == "openai" and any(
            any(c in word for c in "<>\r\n") for word in words
        ):
            raise ValueError(
                "Le vocabulaire OpenAI ne peut pas contenir <, > ou de saut de ligne."
            )
        return {
            "provider": provider,
            "device": self.device_combo.currentData(),
            "microphone": self.microphone_combo.currentData(),
            "languages": languages(expected),
            "language": (
                local_language(expected, provider) if provider != "openai" else ""
            ),
            "prompt": self.prompt_input.toPlainText().strip(),
            "keywords": words,
            **(
                {"api_key": self.api_key_input.text().strip()}
                if provider == "openai"
                else {}
            ),
        }

    def _changed(self, *_args):
        self.cancel(silent=True)
        provider = self.provider_combo.currentData()
        self.device_combo.setVisible(provider == "foundry")
        self.cloud_group.setVisible(provider == "openai")
        self.download_button.setVisible(provider != "openai")
        self.download_button.setEnabled(False)
        self.description.setText(
            {
                "openai": "L’audio est envoyé à OpenAI pendant la dictée. Utilise votre clé API OpenAI et la facturation de GPT Live Transcribe.",
                "apple": "Reconnaissance vocale Apple sur l’appareil, via Apple Speech. macOS 26+ et modèle de langue installé. Aucun audio envoyé dans le cloud.",
                "foundry": "Nemotron 3.5 multilingue reconnaît le français en direct. Environ 756 Mo à télécharger une fois, puis transcription sur ce PC.",
            }[provider]
        )
        self.language_hint.setText(
            {
                "openai": "Une ou plusieurs langues, par exemple fr, en. Vide : détection automatique.",
                "apple": "Une seule langue requise, par exemple fr ou en. Le modèle correspondant sera vérifié.",
                "foundry": "Une seule langue, par exemple fr. Vide : détection automatique des langues.",
            }[provider]
        )
        self.status.set_status(
            "idle",
            "Moteur vocal à vérifier",
            "Vérifiez la disponibilité avant votre première dictée.",
        )

    def _busy(self, active):
        for widget in (
            self.provider_combo,
            self.device_combo,
            self.languages_input,
            self.check_button,
            self.save_button,
            self.test_button,
        ):
            widget.setEnabled(not active)
        self.cancel_button.setVisible(active)
        self.download_button.setEnabled(False)

    def prepare(self, action):
        if self.backend:
            return
        try:
            options = self.options()
            self.backend = self.backend_factory({**options, "action": action})
            backend = self.backend
            self._busy(True)
            self.check_button.setText(
                "Vérification…" if action == "probe" else "Vérifier"
            )
            self.status.set_status(
                "busy",
                (
                    "Vérification en cours…"
                    if action == "probe"
                    else "Installation du modèle vocal…"
                ),
                "La première préparation peut prendre quelques minutes.",
            )
            backend.result.connect(lambda result: self._result(backend, result))
            backend.ready.connect(
                lambda: self._result(
                    backend, {"cached": True, "device": "OpenAI en ligne"}
                )
            )
            backend.failed.connect(lambda message: self._failed(backend, message))
            backend.progress.connect(
                lambda message, percent: self._progress(backend, message, percent)
            )
            backend.start()
        except Exception as exc:
            self.cancel(silent=True)
            self.status.set_status("error", "Vérification impossible", str(exc))

    def _progress(self, backend, message, percent):
        if self.backend is backend:
            self.status.detail.setText(message)
            if percent >= 0:
                self.status.set_progress(percent)

    def _result(self, backend, result):
        if self.backend is not backend:
            return
        self.cancel(silent=True)
        cached = result.get("cached", False)
        self.download_button.setEnabled(not cached)
        device = result.get("device", "Sur cet appareil")
        self.status.set_status(
            "success" if cached else "info",
            "Prêt pour la dictée" if cached else "Modèle vocal à télécharger",
            (
                f"{device}. Enregistrez vos réglages, puis cliquez sur Dicter."
                if cached
                else "Téléchargez le modèle vocal pour activer la transcription locale en direct."
            ),
            checked_at=f"Vérifié à {datetime.now():%H:%M:%S}",
        )

    def _failed(self, backend, message):
        if self.backend is backend:
            self.cancel(silent=True)
            self.status.set_status("error", "Moteur vocal indisponible", message)
            self.check_button.setText("Réessayer")

    def cancel(self, _checked=False, *, silent=False):
        backend, self.backend = self.backend, None
        if backend:
            backend.cancel()
            backend.deleteLater()
        self._busy(False)
        self.check_button.setText("Vérifier")
        if not silent:
            self.status.set_status(
                "idle",
                "Opération annulée",
                "Vous pourrez reprendre la préparation du modèle vocal.",
            )

    def save(self):
        try:
            options = self.options()
        except ValueError as exc:
            self.status.set_status("error", "Réglages à corriger", str(exc))
            return False
        self.settings.set_speech_provider(options["provider"])
        if options["provider"] == "openai":
            self.settings.set_api_key(options["api_key"])
        self.settings.set_speech_device(options["device"])
        self.settings.set_speech_microphone(options["microphone"])
        self.settings.set_transcription_languages(self.languages_input.text().strip())
        self.settings.set_transcription_prompt(options["prompt"])
        self.settings.set_transcription_keywords(self.keywords_input.text().strip())
        self.settings.sync()
        self.save_button.setText("Enregistré")
        QTimer.singleShot(
            1200, self, lambda: self.save_button.setText("Enregistrer la dictée")
        )
        self.settings_saved.emit()
        return True

    def _dictate(self):
        if self.save():
            self.dictation_requested.emit()
