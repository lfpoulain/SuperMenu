"""Choose and prepare a voice engine independently of the text engine."""

from datetime import datetime
import sys

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from supermenu_core.audio.microphone import microphones
from supermenu_core.audio.settings import languages, local_language
from supermenu_core.audio.resident import get_resident_service
from .verification_status import VerificationStatus
from .settings_panel import Disclosure, NoWheelComboBox as QComboBox
from .microphone_test import MicrophoneTest


class SpeechSettingsWidget(QGroupBox):
    settings_saved = Signal()
    dictation_requested = Signal()

    def __init__(self, settings, backend_factory, parent=None, *, platform=None):
        super().__init__("Microphone et moteur vocal", parent)
        self.settings, self.backend_factory = settings, backend_factory
        self.backend = None
        self.platform = platform or sys.platform
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Microphone"))
        self.microphone_combo = QComboBox()
        mic_row = QHBoxLayout()
        mic_row.addWidget(self.microphone_combo, 1)
        refresh = QPushButton("Actualiser")
        refresh.clicked.connect(self.refresh_microphones)
        mic_row.addWidget(refresh)
        layout.addLayout(mic_row)
        self.refresh_microphones()
        self.microphone_test = MicrophoneTest(
            lambda: self.microphone_combo.currentData(), self
        )
        layout.addWidget(self.microphone_test)
        self.microphone_combo.currentIndexChanged.connect(
            lambda: self.microphone_test.cancel()
        )
        layout.addSpacing(8)
        layout.addWidget(QLabel("Moteur de transcription"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("OpenAI · en ligne", "openai")
        if self.platform == "darwin":
            self.provider_combo.addItem("Apple Speech · sur ce Mac", "apple")
        else:
            self.provider_combo.addItem("Nemotron 3.5 · sur ce PC", "foundry")
        self.provider_combo.setCurrentIndex(
            max(0, self.provider_combo.findData(settings.get_speech_provider()))
        )
        layout.addWidget(self.provider_combo)
        self.description = QLabel()
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self.cloud_group = QGroupBox("Clé OpenAI")
        cloud = QVBoxLayout(self.cloud_group)
        self.api_key_input = QLineEdit(settings.get_api_key() or "")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText(
            "Clé API partagée avec le moteur de texte"
        )
        cloud.addWidget(self.api_key_input)
        layout.addWidget(self.cloud_group)
        language_row = QHBoxLayout()
        language_row.addWidget(QLabel("Langue"))
        self.language_combo = QComboBox()
        for title, code in (
            ("Français", "fr"),
            ("Français (Canada)", "fr-ca"),
            ("Anglais", "en"),
            ("Espagnol", "es"),
            ("Allemand", "de"),
            ("Italien", "it"),
            ("Détection automatique", ""),
            ("Personnaliser…", None),
        ):
            self.language_combo.addItem(title, code)
        language_row.addWidget(self.language_combo, 1)
        layout.addLayout(language_row)
        self.languages_input = QLineEdit(settings.get_transcription_languages())
        self.languages_input.setPlaceholderText("Codes de langue, par exemple fr, en")
        layout.addWidget(self.languages_input)
        self.language_hint = QLabel()
        self.language_hint.setWordWrap(True)
        layout.addWidget(self.language_hint)
        self.language_combo.currentIndexChanged.connect(self._choose_language)
        self.languages_input.textChanged.connect(self._sync_language)
        self._sync_language()
        self.status = VerificationStatus()
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.check_button = QPushButton("Vérifier le moteur")
        self.check_button.clicked.connect(lambda: self.prepare("probe"))
        actions.addWidget(self.check_button)
        self.download_button = QPushButton("Télécharger le modèle")
        self.download_button.clicked.connect(lambda: self.prepare("download"))
        actions.addWidget(self.download_button)
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)
        self.advanced = Disclosure()
        advanced = self.advanced.content_layout
        self.device_label = QLabel("Calcul local")
        advanced.addWidget(self.device_label)
        self.device_combo = QComboBox()
        self.device_combo.addItem("Automatique — CUDA en priorité", "auto")
        self.device_combo.addItem("CPU uniquement", "cpu")
        self.device_combo.setCurrentIndex(
            self.device_combo.findData(settings.get_speech_device())
        )
        advanced.addWidget(self.device_combo)
        self.memory_options = QWidget()
        memory = QVBoxLayout(self.memory_options)
        memory.setContentsMargins(0, 0, 0, 0)
        memory.addWidget(QLabel("Décharger le modèle vocal après"))
        self.idle_combo = QComboBox()
        for title, seconds in (
            ("Chaque dictée", 0),
            ("1 minute d’inactivité", 60),
            ("5 minutes d’inactivité (par défaut)", 300),
            ("15 minutes d’inactivité", 900),
            ("30 minutes d’inactivité", 1800),
            ("À la fermeture de SuperMenu", -1),
        ):
            self.idle_combo.addItem(title, seconds)
        self.idle_combo.setCurrentIndex(
            self.idle_combo.findData(settings.get_speech_idle_seconds())
        )
        memory.addWidget(self.idle_combo)
        hint = QLabel(
            "Garder le modèle en mémoire accélère les prochaines dictées et occupe de la RAM ou de la mémoire GPU. Le microphone reste arrêté entre les dictées."
        )
        hint.setWordWrap(True)
        memory.addWidget(hint)
        self.memory_status = QLabel()
        self.memory_status.setWordWrap(True)
        memory.addWidget(self.memory_status)
        self.unload_button = QPushButton("Décharger maintenant")
        self.resident = get_resident_service()
        self.unload_button.clicked.connect(self.resident.unload_idle)
        self.resident.state_changed.connect(self._memory_changed)
        memory.addWidget(self.unload_button)
        advanced.addWidget(self.memory_options)
        self._memory_changed()
        self.context_options = QWidget()
        context = QVBoxLayout(self.context_options)
        context.setContentsMargins(0, 0, 0, 0)
        context.addWidget(QLabel("Vocabulaire et contexte OpenAI facultatifs"))
        self.keywords_input = QLineEdit(settings.get_transcription_keywords())
        self.keywords_input.setPlaceholderText("SuperMenu, noms propres…")
        context.addWidget(self.keywords_input)
        self.prompt_input = QTextEdit()
        self.prompt_input.setAcceptRichText(False)
        self.prompt_input.setMaximumHeight(65)
        self.prompt_input.setPlaceholderText("Contexte de la dictée…")
        self.prompt_input.setPlainText(settings.get_transcription_prompt())
        context.addWidget(self.prompt_input)
        advanced.addWidget(self.context_options)
        layout.addWidget(self.advanced)
        self.actions_widget = QWidget()
        bottom = QHBoxLayout(self.actions_widget)
        bottom.setContentsMargins(0, 0, 0, 0)
        self.save_button = QPushButton("Enregistrer")
        self.save_button.clicked.connect(self.save)
        bottom.addWidget(self.save_button)
        self.test_button = QPushButton("Dicter")
        self.test_button.clicked.connect(self._dictate)
        bottom.addWidget(self.test_button)
        layout.addWidget(self.actions_widget)
        for widget in (self.provider_combo, self.device_combo):
            widget.currentIndexChanged.connect(self._changed)
        self.languages_input.textChanged.connect(self._changed)
        self.api_key_input.textChanged.connect(self._changed)
        self._changed()

    def _choose_language(self):
        code = self.language_combo.currentData()
        self.languages_input.setVisible(code is None)
        self.language_hint.setVisible(code is None)
        if code is not None:
            self.languages_input.setText(code)
        else:
            self.languages_input.setFocus()

    def _sync_language(self):
        # Keep the custom editor open while typing a list such as "fr, en",
        # even when its first characters match a preset.
        if self.language_combo.currentData() is None:
            return
        code = self.languages_input.text().strip().lower()
        index = self.language_combo.findData(code)
        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentIndex(
            index if index >= 0 else self.language_combo.count() - 1
        )
        self.language_combo.blockSignals(False)
        self.languages_input.setVisible(index < 0)
        self.language_hint.setVisible(index < 0)

    def refresh_microphones(self):
        selected = (
            self.microphone_combo.currentData()
            if self.microphone_combo.count()
            else self.settings.get_speech_microphone()
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
        self.device_label.setVisible(provider == "foundry")
        self.context_options.setVisible(provider == "openai")
        self.memory_options.setVisible(provider != "openai")
        self.cloud_group.setVisible(provider == "openai")
        self.download_button.hide()
        self.download_button.setEnabled(False)
        self.description.setText(
            {
                "openai": "GPT Live Transcribe. Audio envoyé à OpenAI ; facturation selon votre usage.",
                "apple": "Votre voix reste sur ce Mac. Nécessite macOS 26 et le modèle de langue Apple.",
                "foundry": "Foundry Local. Votre voix reste sur ce PC. Modèle de 756 Mo à télécharger une fois.",
            }[provider]
        )
        self.language_hint.setText(
            {
                "openai": "Plusieurs langues possibles avec Personnaliser.",
                "apple": "Choisissez une langue précise pour le modèle Apple.",
                "foundry": "Choisissez votre langue ou la détection automatique.",
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
            self.language_combo,
            self.check_button,
            self.save_button,
            self.test_button,
        ):
            widget.setEnabled(not active)
        self.cancel_button.setVisible(active)
        self.download_button.setEnabled(False)

    def _memory_changed(self):
        if self.resident.busy:
            message = "Modèle en cours d’utilisation. Le déchargement sera possible après la dictée."
        elif self.resident.loaded:
            message = "Modèle en mémoire — prêt pour la prochaine dictée."
        else:
            message = "Modèle déchargé — il sera chargé à la prochaine dictée. Les fichiers téléchargés sont conservés."
        self.memory_status.setText(message)
        self.unload_button.setEnabled(self.resident.loaded and not self.resident.busy)

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
                (
                    "Vérification de l’installation et activation du moteur. Les fichiers déjà présents sont réutilisés."
                    if action == "probe"
                    else "Téléchargement sur cet appareil. Le modèle sera conservé entre les mises à jour."
                ),
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
            titles = {
                "verify": "Vérification du modèle",
                "hardware": "Activation du GPU",
                "load": "Chargement en mémoire",
                "download": "Téléchargement du modèle",
                "connect": "Connexion à OpenAI",
            }
            self.status.set_status(
                "busy", titles.get(backend.phase, self.status.title.text()), message
            )
            if percent >= 0:
                self.status.set_progress(percent)

    def _result(self, backend, result):
        if self.backend is not backend:
            return
        self.cancel(silent=True)
        cached = result.get("cached", False)
        self.download_button.setVisible(not cached)
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
        self.settings.set_speech_idle_seconds(self.idle_combo.currentData())
        self.resident.set_idle_seconds(self.idle_combo.currentData())
        if options["provider"] == "openai":
            self.resident.unload_idle()
        self.settings.set_transcription_languages(self.languages_input.text().strip())
        self.settings.set_transcription_prompt(options["prompt"])
        self.settings.set_transcription_keywords(self.keywords_input.text().strip())
        self.settings.sync()
        self.save_button.setText("Enregistré")
        QTimer.singleShot(1200, self, lambda: self.save_button.setText("Enregistrer"))
        self.settings_saved.emit()
        return True

    def _dictate(self):
        self.microphone_test.cancel(silent=True)
        if self.save():
            self.dictation_requested.emit()

    def hideEvent(self, event):
        self.microphone_test.cancel(silent=True)
        super().hideEvent(event)
