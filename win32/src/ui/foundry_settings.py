"""Model acquisition controls; no network or native work on the UI thread."""

from datetime import datetime

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from supermenu_core.ui.verification_status import VerificationStatus
from supermenu_core.ui.settings_panel import Disclosure
from supermenu_core.ui.controls import ChoiceBox
from supermenu_core.config.model_memory import idle_choices
from src.api.foundry_client import get_foundry_service
from src.api.foundry_worker import platform_error
from src.config.foundry_models import FOUNDRY_MODELS


class FoundrySettingsWidget(QGroupBox):
    def __init__(self, settings, parent=None):
        super().__init__("Foundry Local", parent)
        self.service = get_foundry_service()
        self.settings = settings
        self.service.set_idle_seconds(settings.get_text_idle_seconds())
        self.request_id = None
        self.operation = None
        self.models = {}
        self.probed = False
        self.hardware_warning = ""
        self.checked_at = ""
        layout = QVBoxLayout(self)
        description = QLabel(
            "Correction, reformulation et traduction sur ce PC, sans clé API. "
            "Windows 11 24H2 minimum. Les modèles téléchargés sont conservés entre les mises à jour."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.model_combo = ChoiceBox()
        for alias, info in FOUNDRY_MODELS.items():
            self.model_combo.addItem(info["label"], alias)
        self.model_combo.setCurrentIndex(
            self.model_combo.findData(settings.get_foundry_model())
        )
        self.model_combo.currentIndexChanged.connect(self.update_model)
        layout.addWidget(self.model_combo)
        self.device_combo = ChoiceBox()
        self.device_combo.addItem("Automatique — GPU en priorité", "auto")
        self.device_combo.addItem("CPU uniquement", "cpu")
        self.device_combo.setCurrentIndex(
            self.device_combo.findData(settings.get_foundry_device())
        )
        self.device_combo.currentIndexChanged.connect(self.device_changed)
        self.model_info = QLabel()
        self.model_info.setWordWrap(True)
        layout.addWidget(self.model_info)
        self.verification = VerificationStatus()
        self.status = self.verification.detail
        self.progress_bar = self.verification.progress_bar
        layout.addWidget(self.verification)
        buttons = QHBoxLayout()
        self.check_button = QPushButton("Vérifier le modèle")
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
        advanced = Disclosure("Matériel et mémoire du modèle")
        advanced.content_layout.addWidget(QLabel("Calcul local"))
        advanced.content_layout.addWidget(self.device_combo)
        advanced.content_layout.addWidget(self.cache_label)
        advanced.content_layout.addWidget(QLabel("Décharger le modèle texte après"))
        self.idle_combo = ChoiceBox()
        for title, seconds in idle_choices("Chaque requête"):
            self.idle_combo.addItem(title, seconds)
        self.idle_combo.setCurrentIndex(self.idle_combo.findData(settings.get_text_idle_seconds()))
        self.idle_combo.currentIndexChanged.connect(self._save_memory_policy)
        advanced.content_layout.addWidget(self.idle_combo)
        self.memory_status = QLabel()
        self.memory_status.setWordWrap(True)
        advanced.content_layout.addWidget(self.memory_status)
        self.unload_button = QPushButton("Décharger maintenant")
        self.unload_button.clicked.connect(self.service.unload_idle)
        advanced.content_layout.addWidget(self.unload_button)
        self.service.state_changed.connect(self._memory_changed)
        self._memory_changed()
        layout.addWidget(advanced)
        note = QLabel(
            'Modèles sous licence <a href="https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/LICENSE">Apache 2.0</a>. '
            "16 Go de RAM conseillés pour le 4B, 24 Go pour le 9B. "
            "La vitesse dépend du matériel. Limite : 16 000 caractères par requête. "
            "Le moteur vocal se choisit dans la rubrique Dictée."
        )
        note.setOpenExternalLinks(True)
        note.setWordWrap(True)
        advanced.content_layout.addWidget(note)
        self.service.completed.connect(self.completed)
        self.service.failed.connect(self.failed)
        self.service.progress.connect(self.progress)
        self.update_model()

    def _save_memory_policy(self):
        seconds = self.idle_combo.currentData()
        self.settings.set_text_idle_seconds(seconds)
        self.settings.sync()
        self.service.set_idle_seconds(seconds)

    def _memory_changed(self):
        if self.service.busy:
            message = "Moteur en cours d’utilisation. Le déchargement attend la fin des requêtes."
        elif self.service.loaded:
            message = "Modèle texte en mémoire — prêt pour la prochaine requête."
        else:
            message = "Modèle texte déchargé. Le moteur reste prêt pour accélérer le prochain chargement ; les fichiers restent installés."
        self.memory_status.setText(message)
        self.unload_button.setEnabled(self.service.loaded and not self.service.busy)

    def selected_model(self):
        return self.model_combo.currentData()

    def selected_device(self):
        return self.device_combo.currentData()

    def device_changed(self, *_args):
        if self.request_id:
            self.cancel()
        self.models = {}
        self.hardware_warning = ""
        self.checked_at = ""
        self.update_model()
        if self.probed:
            self.probe()

    def update_model(self, *_args):
        info = self.models.get(self.selected_model())
        if info:
            size = info.get("size_mb")
            size_text = f"{size / 1000:.1f} Go" if size else "taille non annoncée"
            provider = info.get("execution_provider", "")
            device = {
                "CUDAExecutionProvider": "GPU — CUDA (NVIDIA)",
                "WebGpuExecutionProvider": "GPU — WebGPU",
            }.get(provider, info["device"])
            self.model_info.setText(f"Exécution : {device} · {size_text}")
        else:
            self.model_info.setText(
                "Le téléchargement et le matériel d'exécution seront précisés après vérification."
            )
        if not self.request_id:
            self.show_readiness()
        self.update_controls()

    def show_readiness(self):
        info = self.models.get(self.selected_model())
        if platform_error():
            state, title, detail = (
                "warning",
                "Foundry Local indisponible",
                platform_error(),
            )
        elif self.hardware_warning:
            state, title, detail = (
                "warning",
                "Accélération GPU à vérifier",
                self.hardware_warning,
            )
        elif info and info["cached"]:
            state, title, detail = (
                "success",
                "Prêt à utiliser",
                "Le modèle est téléchargé sur ce PC. "
                "Enregistrez la configuration pour l’utiliser.",
            )
        elif info:
            state, title, detail = (
                "info",
                "Vérification réussie · modèle à télécharger",
                "Ce modèle est compatible avec le mode d’exécution affiché. "
                "Téléchargez-le pour pouvoir l’utiliser.",
            )
        elif self.probed:
            state, title, detail = (
                "warning",
                "Modèle indisponible",
                "Ce modèle n’est pas disponible dans le catalogue pour le mode choisi. "
                "Choisissez un autre modèle ou relancez la vérification.",
            )
        else:
            state, title, detail = (
                "idle",
                "Disponibilité à vérifier",
                "Vérifiez les modèles disponibles et le matériel d’exécution sur ce PC.",
            )
        self.verification.set_status(state, title, detail, checked_at=self.checked_at)

    def update_controls(self):
        info = self.models.get(self.selected_model())
        self.download_button.setVisible(bool(info and not info["cached"]))
        self.download_button.setEnabled(
            bool(info and not info["cached"] and not self.request_id)
        )
        self.check_button.setEnabled(not self.request_id and not platform_error())
        self.model_combo.setEnabled(not self.request_id)
        self.device_combo.setEnabled(not self.request_id)
        self.check_button.setText(
            "Vérification en cours…"
            if self.operation == "probe"
            else "Vérifier à nouveau" if self.probed else "Vérifier le modèle"
        )
        self.download_button.setText(
            "Téléchargement en cours…"
            if self.operation == "download"
            else (
                "Modèle téléchargé"
                if info and info["cached"]
                else "Télécharger le modèle"
            )
        )

    def start(self, operation, **payload):
        if self.request_id:
            return
        self.operation = operation
        self.request_id = self.service.submit(operation, **payload)
        self.verification.set_status(
            "busy",
            (
                "Vérification en cours…"
                if operation == "probe"
                else "Téléchargement du modèle…"
            ),
            (
                "Vérification des fichiers et du matériel. Les composants déjà installés sont réutilisés."
                if operation == "probe"
                else "Le modèle sera disponible sur ce PC à la fin du téléchargement."
            ),
        )
        self.cancel_button.show()
        self.update_controls()

    def probe(self):
        if not platform_error():
            self.start("probe", device=self.selected_device())

    def download(self):
        info = self.models.get(self.selected_model())
        if info and not info["cached"]:
            self.start(
                "download", model=self.selected_model(), device=self.selected_device()
            )

    def finish(self):
        self.request_id = None
        self.operation = None
        self.progress_bar.hide()
        self.cancel_button.hide()
        self.update_controls()

    def completed(self, request_id, result):
        if request_id != self.request_id:
            return
        if self.operation == "probe":
            self.models = {m["alias"]: m for m in result["models"]}
            self.probed = True
            self.hardware_warning = result.get("hardware_warning") or ""
            self.cache_label.setText("Stockage des modèles : " + result["cache_dir"])
            self.checked_at = f"Vérifié à {datetime.now():%H:%M:%S}"
        else:
            self.models[result["alias"]] = result
        self.finish()
        self.update_model()

    def failed(self, request_id, error):
        if request_id == self.request_id:
            operation = self.operation
            if operation == "probe":
                # Do not present a previous successful check as current after a failure.
                self.models = {}
                self.hardware_warning = ""
                self.checked_at = ""
                self.model_info.clear()
            self.finish()
            self.verification.set_status(
                "error",
                (
                    "La vérification a échoué"
                    if operation == "probe"
                    else "Téléchargement interrompu"
                ),
                error,
                checked_at=f"Dernière tentative à {datetime.now():%H:%M:%S}",
            )
            self.check_button.setText("Réessayer la vérification")

    def progress(self, request_id, progress):
        if request_id != self.request_id:
            return
        if "stage" in progress:
            self.verification.set_status(
                "busy",
                (
                    "Activation du GPU"
                    if progress.get("phase") == "hardware"
                    else self.verification.title.text()
                ),
                progress["stage"],
            )
        if "percent" in progress:
            self.verification.title.setText("Téléchargement du modèle")
            self.verification.set_progress(progress["percent"])

    def cancel(self):
        request_id = self.request_id
        if not request_id:
            return
        operation = self.operation
        self.finish()
        self.verification.set_status(
            "idle",
            "Vérification annulée" if operation == "probe" else "Téléchargement annulé",
            (
                "Relancez la vérification pour connaître la disponibilité du modèle."
                if operation == "probe"
                else "Vous pouvez reprendre le téléchargement quand vous le souhaitez."
            ),
        )
        self.service.cancel(request_id)
