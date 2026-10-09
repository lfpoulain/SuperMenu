"""Shared model selector with distinct, persisted model/device choices."""

import json
import sys
from urllib.parse import urlsplit

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QComboBox, QPushButton, QInputDialog

TARGET_ROLE = Qt.ItemDataRole.UserRole + 1


def configure_model_combo(combo):
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.setMinimumContentsLength(24)
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setToolTip("Choisissez le modèle et le poste qui exécutera ce modèle.")


def selected_model_id(combo):
    index = combo.currentIndex()
    if index >= 0 and combo.currentText() == combo.itemText(index):
        return combo.itemData(index) or combo.currentText().strip()
    return combo.currentText().strip()


def selected_model_target(combo):
    index = combo.currentIndex()
    if index >= 0 and combo.currentText() == combo.itemText(index):
        value = combo.itemData(index, TARGET_ROLE)
        if isinstance(value, dict):
            return dict(value)
    identifier = selected_model_id(combo)
    return {"provider": "custom", "model": identifier} if identifier else {}


def target_key(target):
    return json.dumps(
        {key: target[key] for key in ("provider", "model", "device") if key in target},
        sort_keys=True,
    )


def restore_model_target(combo, target):
    if not target:
        return
    index = combo.currentIndex()
    if index < 0:
        combo.addItem(target["model"], target["model"])
        index = combo.count() - 1
    combo.setItemData(index, dict(target), TARGET_ROLE)
    combo.setCurrentIndex(index)


def device_label(device, names, endpoint="", fallback="Appareil distant"):
    if device is None:
        host = urlsplit(endpoint).hostname
        if host in {"localhost", "127.0.0.1", "::1"} or not host:
            return "Sur ce Mac" if sys.platform == "darwin" else "Sur ce PC"
        return "Sur " + (names.get(None) or host)
    return "Sur " + (names.get(device) or fallback) + " (LM Link)"


def source_label(sources):
    # Compatibility helper for consumers without a catalog. Never expose raw IDs.
    if not sources:
        return "Poste non précisé par LM Studio"
    return " / ".join(
        "Ce poste" if source is None else "Appareil distant" for source in sources
    )


def model_summary(details, *, lmstudio=False):
    if not lmstudio:
        return ""
    if not details:
        return "Actualisez la liste pour choisir le poste qui exécutera le modèle."
    if "device" not in details:
        return "Choix automatique : LM Studio choisit le poste. Sélectionnez une ligne locale ou distante pour fixer ce choix."
    place = details.get("device_label", "Poste choisi")
    state = (
        "Déjà chargé"
        if details["device"] in details.get("loaded_sources", [])
        else "Chargé à la demande"
    )
    return f"{place} · {state}. Aucun basculement automatique vers un autre poste."


def populate_model_catalog(
    combo, model_details, *, lmstudio=False, endpoint="", settings=None
):
    current = selected_model_target(combo)
    catalog = {}
    devices = sorted(
        {
            device
            for details in model_details
            if isinstance(details, dict)
            for device in details.get("sources", [])
            if isinstance(device, str)
        }
    )
    fallback_names = {
        device: f"Appareil distant {index + 1}" for index, device in enumerate(devices)
    }
    aliases = settings.get_model_device_names(endpoint) if settings is not None else {}
    automatic = object()
    for details in model_details:
        if (
            not isinstance(details, dict)
            or not isinstance(details.get("id"), str)
            or not details["id"]
        ):
            continue
        identifier = details["id"]
        sources = details.get("sources", []) if lmstudio else []
        for device in sources or [automatic]:
            target = {"provider": "custom", "model": identifier}
            row = dict(details)
            if device is not automatic:
                names = {**details.get("device_names", {}), **aliases}
                label = device_label(
                    device,
                    names,
                    endpoint,
                    fallback_names.get(device, "Appareil distant"),
                )
                target.update(device=device, device_name=label)
                row.update(device=device, device_label=label)
            else:
                label = "Choix automatique (LM Studio)"
            row["target"] = target
            row["label"] = identifier + (" — " + label if lmstudio else "")
            catalog[target_key(target)] = row
    with QSignalBlocker(combo):
        combo.clear()
        for row in catalog.values():
            combo.addItem(row["label"], row["id"])
            index = combo.count() - 1
            combo.setItemData(index, row["target"], TARGET_ROLE)
            combo.setItemData(
                index,
                model_summary(row, lmstudio=lmstudio),
                Qt.ItemDataRole.ToolTipRole,
            )
        key = target_key(current)
        if current and key not in catalog:
            label = current["model"]
            if "device" in current:
                label += (
                    " — "
                    + current.get("device_name", "Poste choisi")
                    + " (indisponible)"
                )
            elif lmstudio:
                label += " — Choix automatique (LM Studio)"
            combo.addItem(label, current["model"])
            combo.setItemData(combo.count() - 1, current, TARGET_ROLE)
            combo.setCurrentIndex(combo.count() - 1)
        elif current:
            combo.setCurrentIndex(list(catalog).index(key))
        elif combo.count():
            combo.setCurrentIndex(0)
        combo.lineEdit().setCursorPosition(0)
    return catalog


class DeviceNameButton(QPushButton):
    """Optional friendly aliases, scoped to the configured LM Studio server."""

    def __init__(self, combo, settings, endpoint, parent=None):
        super().__init__("Nommer ce poste distant…", parent)
        self.combo, self.settings, self.endpoint = combo, settings, endpoint
        self.dialog = None
        self.setToolTip("Donnez un nom clair à ce poste, par exemple Serveur Apple.")
        combo.currentTextChanged.connect(self.refresh)
        self.clicked.connect(self.rename)
        self.refresh()

    def refresh(self, *_args):
        self.setVisible(
            isinstance(selected_model_target(self.combo).get("device"), str)
        )

    def rename(self):
        target = selected_model_target(self.combo)
        device = target.get("device")
        if not isinstance(device, str):
            return
        endpoint = self.endpoint()
        dialog = self.dialog = QInputDialog(self)
        dialog.setWindowTitle("Nom du poste distant")
        dialog.setLabelText(
            "Nom affiché dans SuperMenu (ex. Serveur Apple)\nIdentifiant LM Link : "
            + device
        )
        dialog.setTextValue(
            self.settings.get_model_device_names(endpoint).get(device, "")
        )
        dialog.setOkButtonText("Enregistrer")
        dialog.setCancelButtonText("Annuler")

        def save(name):
            if not name.strip():
                return
            self.settings.set_model_device_name(endpoint, device, name)
            for index in range(self.combo.count()):
                value = self.combo.itemData(index, TARGET_ROLE)
                if isinstance(value, dict) and value.get("device") == device:
                    label = device_label(device, {device: name.strip()[:80]}, endpoint)
                    self.combo.setItemData(
                        index, {**value, "device_name": label}, TARGET_ROLE
                    )
                    self.combo.setItemText(index, value["model"] + " — " + label)

        dialog.textValueSelected.connect(save)
        dialog.finished.connect(dialog.deleteLater)
        dialog.open()


def selected_model_details(combo, catalog):
    return catalog.get(target_key(selected_model_target(combo)))


def selection_summary(combo, catalog, *, lmstudio=False):
    if not lmstudio:
        return ""
    details = selected_model_details(combo, catalog)
    target = selected_model_target(combo)
    if details is not None and target.get("device_name"):
        details = {**details, "device_label": target["device_name"]}
    if details is None and "device" in target:
        return (
            target.get("device_name", "Poste choisi")
            + " : disponibilité à vérifier. Actualisez la liste. Aucun autre poste ne sera utilisé."
        )
    return model_summary(
        details or ({"id": target["model"]} if target else None), lmstudio=True
    )


def clear_model_provenance(combo):
    current = selected_model_id(combo)
    with QSignalBlocker(combo):
        combo.clear()
        if current:
            combo.addItem(current, current)
            combo.setCurrentIndex(0)
