"""Model acquisition controls; no network or native work on the UI thread."""

from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from src.api.foundry_client import get_foundry_service
from src.api.foundry_worker import platform_error
from src.config.foundry_models import FOUNDRY_MODELS


class FoundrySettingsWidget(QGroupBox):
    def __init__(self, settings, parent=None):
        super().__init__("IA locale Microsoft — Foundry Local (bêta)", parent)
        self.service = get_foundry_service()
        self.request_id = None
        self.operation = None
        self.models = {}
        self.probed = False
        layout = QVBoxLayout(self)
        description = QLabel(
            "Correction, reformulation et traduction sur ce PC, sans clé API. "
            "Windows 11 24H2 minimum. Une connexion est nécessaire au premier téléchargement."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.model_combo = QComboBox()
        for alias, info in FOUNDRY_MODELS.items():
            self.model_combo.addItem(info["label"], alias)
        self.model_combo.setCurrentIndex(
            self.model_combo.findData(settings.get_foundry_model())
        )
        self.model_combo.currentIndexChanged.connect(self.update_model)
        layout.addWidget(self.model_combo)
        self.model_info = QLabel()
        self.model_info.setWordWrap(True)
        layout.addWidget(self.model_info)
        self.status = QLabel(
            platform_error()
            or "Cliquez sur Vérifier pour consulter les modèles disponibles sur ce PC."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        buttons = QHBoxLayout()
        self.check_button = QPushButton("Vérifier")
        self.check_button.clicked.connect(self.probe)
        self.download_button = QPushButton("Télécharger le modèle")
        self.download_button.clicked.connect(self.download)
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()
        for button in (self.check_button, self.download_button, self.cancel_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.cache_label = QLabel()
        self.cache_label.setWordWrap(True)
        layout.addWidget(self.cache_label)
        note = QLabel(
            'Modèles sous licence <a href="https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/LICENSE">Apache 2.0</a>. '
            "16 Go de RAM conseillés pour le 4B, 24 Go pour le 9B. "
            "La vitesse dépend du matériel. Limite : 16 000 caractères par requête. "
            "Cette bêta locale traite le texte ; la dictée utilise toujours OpenAI."
        )
        note.setOpenExternalLinks(True)
        note.setWordWrap(True)
        layout.addWidget(note)
        self.service.completed.connect(self.completed)
        self.service.failed.connect(self.failed)
        self.service.progress.connect(self.progress)
        self.update_model()

    def selected_model(self):
        return self.model_combo.currentData()

    def update_model(self, *_args):
        info = self.models.get(self.selected_model())
        if info:
            size = info.get("size_mb")
            size_text = f"{size / 1000:.1f} Go" if size else "taille non annoncée"
            state = (
                "Téléchargé — prêt à utiliser" if info["cached"] else "À télécharger"
            )
            self.model_info.setText(
                f"{state} · {size_text} · Exécution : {info['device']}"
            )
        else:
            self.model_info.setText(
                "Le téléchargement et le matériel d'exécution seront précisés après vérification."
            )
        self.download_button.setEnabled(
            bool(info and not info["cached"] and not self.request_id)
        )
        self.check_button.setEnabled(not self.request_id and not platform_error())
        self.model_combo.setEnabled(not self.request_id)

    def start(self, operation, **payload):
        if self.request_id:
            return
        self.operation = operation
        self.request_id = self.service.submit(operation, **payload)
        self.status.setText(
            "Vérification du catalogue Microsoft…"
            if operation == "probe"
            else "Téléchargement du modèle…"
        )
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self.cancel_button.show()
        self.update_model()

    def probe(self):
        if not platform_error():
            self.start("probe")

    def download(self):
        info = self.models.get(self.selected_model())
        if info and not info["cached"]:
            self.start("download", model=self.selected_model())

    def finish(self):
        self.request_id = None
        self.operation = None
        self.progress_bar.hide()
        self.cancel_button.hide()
        self.update_model()

    def completed(self, request_id, result):
        if request_id != self.request_id:
            return
        if self.operation == "probe":
            self.models = {m["alias"]: m for m in result["models"]}
            self.probed = True
            self.cache_label.setText("Stockage des modèles : " + result["cache_dir"])
            self.status.setText(
                "Choisissez le modèle, téléchargez-le puis enregistrez la configuration."
            )
        else:
            self.models[result["alias"]] = result
            self.status.setText(
                "Modèle téléchargé. Enregistrez la configuration pour l'utiliser."
            )
        self.finish()

    def failed(self, request_id, error):
        if request_id == self.request_id:
            self.status.setText(error)
            self.finish()

    def progress(self, request_id, progress):
        if request_id == self.request_id and "percent" in progress:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(round(progress["percent"]))

    def cancel(self):
        request_id = self.request_id
        self.finish()
        self.status.setText(
            "Opération annulée. Vous pouvez reprendre le téléchargement."
        )
        if request_id:
            self.service.cancel(request_id)
