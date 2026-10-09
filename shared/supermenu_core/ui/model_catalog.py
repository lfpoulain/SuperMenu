"""Shared model selector: presentation labels never become API identifiers."""

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QComboBox


def configure_model_combo(combo):
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.setMinimumContentsLength(24)
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setToolTip(
        "Local au serveur : sur la machine qui héberge l’endpoint.\n"
        "LM Link : sur un autre appareil relié à ce serveur.\n"
        "Actualiser relève la provenance et les instances chargées à cet instant."
    )


def selected_model_id(combo):
    index = combo.currentIndex()
    if index >= 0 and combo.currentText() == combo.itemText(index):
        return combo.itemData(index) or combo.currentText().strip()
    return combo.currentText().strip()


def source_label(sources):
    if not sources:
        return "Provenance inconnue"
    parts = []
    if None in sources:
        parts.append("Local au serveur")
    remote = [source for source in sources if source is not None]
    if remote:
        parts.append("LM Link : " + ", ".join(remote))
    return " + ".join(parts)


def model_summary(details, *, lmstudio=False):
    if not lmstudio:
        return ""
    if not details:
        return "Actualisez les modèles pour connaître leur provenance."
    text = "Disponible : " + source_label(details.get("sources")) + "."
    if details.get("loaded_sources"):
        text += (
            "\nChargé lors de l’actualisation : "
            + source_label(details["loaded_sources"])
            + "."
        )
    if not details.get("sources"):
        text += "\nLe serveur ne communique pas la provenance local / LM Link."
    if len(details.get("sources", [])) > 1:
        text += "\nLe poste préféré dans LM Studio détermine le routage."
    return text


def populate_model_catalog(combo, model_details, *, lmstudio=False):
    current = selected_model_id(combo)
    catalog = {}
    # Aggregate duplicate route IDs rather than overwriting an origin with
    # another. REST cannot target two different devices using the same ID.
    for details in model_details:
        if not isinstance(details, dict) or not isinstance(details.get("id"), str):
            continue
        identifier = details["id"]
        if not identifier:
            continue
        if identifier not in catalog:
            catalog[identifier] = dict(details)
        else:
            for field in ("sources", "loaded_sources"):
                values = catalog[identifier].get(field, []) + details.get(field, [])
                catalog[identifier][field] = list(dict.fromkeys(values))
    with QSignalBlocker(combo):
        combo.clear()
        for identifier, details in catalog.items():
            label = identifier
            if lmstudio:
                label += " — " + source_label(details.get("sources"))
            combo.addItem(label, identifier)
            combo.setItemData(
                combo.count() - 1,
                model_summary(details, lmstudio=lmstudio),
                Qt.ItemDataRole.ToolTipRole,
            )
        if current:
            index = combo.findData(current)
            if index >= 0:
                combo.setCurrentIndex(index)
            else:
                # A disconnected remote model must not silently switch to local.
                combo.setEditText(current)
        elif combo.count():
            combo.setCurrentIndex(0)
        combo.lineEdit().setCursorPosition(0)
    return catalog


def clear_model_provenance(combo):
    current = selected_model_id(combo)
    with QSignalBlocker(combo):
        combo.clear()
        if current:
            combo.addItem(current, current)
            combo.setCurrentIndex(0)
