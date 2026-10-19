"""Model overrides shared by text and voice prompt editors."""

import threading

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from .controls import ChoiceBox
from .model_catalog import (
    configure_model_combo,
    device_label,
    populate_model_catalog,
    selected_model_id,
    selected_model_target,
    restore_model_target,
    DeviceNameButton,
)
from supermenu_core.config.model_target import (
    normalize_model_target,
    registered_foundry_models,
    without_server,
)
from supermenu_core.config.openai_models import AVAILABLE_MODELS

_catalog_workers = set()


class CatalogWorker(QObject):
    result = Signal(object)
    finished = Signal()

    def __init__(self, endpoint, endpoint_type, key):
        super().__init__()
        self.endpoint, self.endpoint_type, self.key = endpoint, endpoint_type, key
        self._running = False

    def isRunning(self):
        return self._running

    def start(self):
        self._running = True
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        from supermenu_core.api.openai_client import OpenAIClient

        try:
            ok, result = OpenAIClient.fetch_available_model_details(
                self.endpoint,
                api_key=self.key,
                endpoint_type=self.endpoint_type,
            )
        except Exception:
            ok, result = (
                False,
                "Impossible de récupérer les modèles. Vérifiez le serveur dans Réglages > Texte.",
            )
        self.result.emit((self.endpoint, self.endpoint_type, ok, result))
        self.key = None
        self._running = False
        self.finished.emit()


class PromptModelChoice(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.saved = {}
        self.worker = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.provider = ChoiceBox()
        self.provider.addItem("Utiliser le réglage général", "default")
        self.provider.addItem("LM Studio / Ollama — serveur configuré", "custom")
        self.provider.addItem("OpenAI", "openai")
        if hasattr(settings, "get_foundry_model"):
            self.provider.addItem("Foundry Local — sur ce PC", "foundry")
        else:
            self.provider.addItem("Apple Intelligence — sur ce Mac", "apple")
        layout.addWidget(self.provider)
        self.model_row = QWidget()
        row = QHBoxLayout(self.model_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.model = ChoiceBox()
        configure_model_combo(self.model)
        row.addWidget(self.model, 1)
        self.refresh_button = QPushButton("Actualiser")
        self.refresh_button.clicked.connect(self.refresh)
        row.addWidget(self.refresh_button)
        layout.addWidget(self.model_row)
        self.device_name_button = DeviceNameButton(self.model, settings, self._endpoint)
        layout.addWidget(self.device_name_button)
        self.help = QLabel()
        self.help.setTextFormat(Qt.TextFormat.PlainText)
        self.help.setWordWrap(True)
        layout.addWidget(self.help)
        self.provider.currentIndexChanged.connect(self._provider_changed)
        self._provider_changed()

    def set_target(self, target):
        self.saved = normalize_model_target(target)
        self.provider.blockSignals(True)
        index = self.provider.findData(self.saved.get("provider", "default"))
        # Preserve imported choices for another platform without substituting.
        if index < 0:
            self.provider.addItem(
                "Moteur indisponible sur cet ordinateur", self.saved["provider"]
            )
            index = self.provider.count() - 1
        self.provider.setCurrentIndex(index)
        self.provider.blockSignals(False)
        self._provider_changed()

    def _provider_changed(self, *_args):
        provider = self.provider.currentData()
        self.model.clear()
        self.model.setEditable(provider == "custom")
        self.model_row.setVisible(provider not in {"default", "apple"})
        self.refresh_button.setVisible(provider == "custom")
        same = self.saved.get("provider") == provider
        if provider == "openai":
            self.model.addItems(list(AVAILABLE_MODELS))
            self.model.setCurrentText(
                self.saved["model"] if same else self.settings.get_model()
            )
        elif provider == "foundry":
            # The Windows adapter registers the aliases it supports. Elsewhere
            # an imported choice is only shown as it is (added below).
            aliases = list(registered_foundry_models())
            getter = getattr(self.settings, "get_foundry_model", None)
            if not aliases and getter is not None:
                aliases = [getter()]
            self.model.addItems(aliases)
            if same:
                self.model.setCurrentText(self.saved["model"])
            elif aliases:
                self.model.setCurrentText(aliases[0])
        elif provider == "custom":
            target = (
                self._current_device_label(self.saved)
                if same
                else self.settings.get_custom_model_target()
            )
            model = target.get("model", self.settings.get_custom_model())
            if model:
                self.model.addItem(model, model)
                restore_model_target(
                    self.model, target or {"provider": "custom", "model": model}
                )
                if "device" in target:
                    self.model.setItemText(
                        self.model.currentIndex(),
                        model + " — " + target.get("device_name", "Poste choisi"),
                    )
        if (
            same
            and provider in {"openai", "foundry"}
            and self.model.findText(self.saved["model"]) < 0
        ):
            self.model.addItem(self.saved["model"])
            self.model.setCurrentIndex(self.model.count() - 1)
        self.help.setText(
            "Ce prompt utilisera le moteur et le modèle des réglages généraux."
            if provider == "default"
            else (
                self._server_help()
                if provider == "custom"
                else "Ce choix s’applique uniquement à ce prompt."
            )
        )

    def _server_help(self):
        endpoint = str(self._endpoint() or "").strip()
        if not endpoint:
            return "Renseignez le serveur dans Réglages > Texte, puis enregistrez-le."
        return (
            "Serveur des réglages Texte : "
            + endpoint
            + ". Ce prompt suivra ce serveur s’il change. Actualisez, puis choisissez le modèle et son poste."
        )

    def _current_device_label(self, target):
        """Name the saved device on the configured server, not on an old one.

        The prompt follows the server of the Text settings, so a stored label
        such as "Sur 192.168.1.20" may describe a previous server, and an
        imported prompt carries none.
        """
        if "device" not in target:
            return target
        endpoint = str(self._endpoint() or "").strip()
        device = target["device"]
        if device is None:
            # The server's own machine: always described by the current server.
            label = device_label(None, {}, endpoint)
        else:
            getter = getattr(self.settings, "get_model_device_names", None)
            names = getter(endpoint) if getter is not None and endpoint else {}
            if not names.get(device):
                return target
            label = device_label(device, names, endpoint)
        return {**target, "device_name": label}

    # The prompt always follows the server of the Text settings: a server
    # stored by an older version or an imported file is never reused.
    def _endpoint(self):
        return self.settings.get_custom_endpoint()

    def _endpoint_type(self):
        return self.settings.get_custom_endpoint_type()

    def target(self):
        provider = self.provider.currentData()
        if provider == "default":
            return {}
        if provider == "apple":
            return {"provider": "apple", "model": "apple-foundation"}
        if provider == "custom":
            # An empty choice stays invalid instead of meaning "default".
            target = without_server(selected_model_target(self.model)) or {
                "provider": "custom",
                "model": "",
            }
            if "device" in target and self._endpoint_type() != "lmstudio":
                raise ValueError("Le choix du poste nécessite un serveur LM Studio.")
        else:
            target = {"provider": provider, "model": selected_model_id(self.model)}
        return normalize_model_target(target)

    def is_valid(self):
        try:
            self.target()
            return True
        except ValueError as exc:
            self.help.setText(str(exc))
            return False

    def refresh(self):
        if self.worker is not None and self.worker.isRunning():
            return
        endpoint = self._endpoint().strip()
        if not endpoint:
            self.help.setText(
                "Renseignez le serveur dans Réglages > Texte, puis enregistrez-le."
            )
            return
        key = self.settings.get_custom_endpoint_api_key()
        worker = self.worker = CatalogWorker(endpoint, self._endpoint_type(), key)
        _catalog_workers.add(worker)
        worker.result.connect(self._loaded)
        worker.finished.connect(self._finished)
        worker.finished.connect(
            lambda: (_catalog_workers.discard(worker), worker.deleteLater())
        )
        self.refresh_button.setEnabled(False)
        self.help.setText("Recherche des modèles et des postes…")
        worker.start()

    def _finished(self):
        self.worker = None
        self.refresh_button.setEnabled(True)

    def _loaded(self, result):
        endpoint, endpoint_type, ok, models = result
        if (
            self.provider.currentData() != "custom"
            or endpoint != self._endpoint()
            or endpoint_type != self._endpoint_type()
        ):
            return
        if not ok:
            self.help.setText(str(models))
            return
        populate_model_catalog(
            self.model,
            models,
            lmstudio=endpoint_type == "lmstudio",
            endpoint=endpoint,
            settings=self.settings,
        )
        self.device_name_button.refresh()
        self.help.setText(
            "Choisissez une ligne : le modèle sera chargé sur ce poste uniquement lorsque vous lancerez ce prompt."
        )
