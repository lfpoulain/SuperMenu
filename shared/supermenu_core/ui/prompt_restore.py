"""Common factory-reset confirmation for the text and voice libraries."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from supermenu_core.config.prompt_restore import (
    next_prompt_backup,
    prompt_backups,
    restore_prompt_backup,
    restore_prompt_defaults,
)
from .confirmations import confirm_action


def _notify(parent, icon, title, message):
    # Non-blocking like the confirmations, so it is safe from Cocoa callbacks.
    box = QMessageBox(icon, title, message, QMessageBox.StandardButton.Ok, parent)
    box.setOption(QMessageBox.Option.DontUseNativeDialog, True)
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    box.open()
    return box


def _report_failure(parent, title, exc):
    return _notify(parent, QMessageBox.Icon.Warning, title, str(exc))


def restore_library(parent, settings, refreshed, *, voice=False):
    label = "vocaux" if voice else "texte"

    def restore():
        try:
            restore_prompt_defaults(settings, voice=voice)
        except Exception as exc:
            _report_failure(parent, "Restauration impossible", exc)
            return
        refreshed()

    return confirm_action(
        parent,
        "Restaurer les prompts d’origine",
        f"Remplacer tous les prompts {label} par ceux d’origine ? "
        "Les modifications, les prompts personnels et leurs raccourcis seront retirés de cette liste. "
        "Les moteurs IA et les autres réglages sont conservés. "
        "Une copie de la liste actuelle sera conservée dans la configuration.",
        restore,
    )


def _format_date(saved_at):
    date, _separator, time = str(saved_at or "").partition("T")
    parts = date.split("-")
    if len(parts) != 3 or not time:
        return "date inconnue"
    return f"{parts[2]}/{parts[1]}/{parts[0]} à {time[:5]}"


def restore_previous_library(parent, settings, refreshed, *, voice=False):
    """Offer to go back to a kept copy (restore, import or repair).

    Each use moves one copy further back, skipping copies identical to the
    current list or unreadable, so every kept copy can be reached.
    """
    label = "vocaux" if voice else "texte"
    backups = prompt_backups(settings, voice=voice)
    if not backups:
        return _notify(
            parent,
            QMessageBox.Icon.Information,
            "Aucune copie disponible",
            f"Aucune copie précédente de la liste des prompts {label} n’est conservée.",
        )
    index = next_prompt_backup(settings, voice=voice)
    if index is None:
        return _notify(
            parent,
            QMessageBox.Icon.Information,
            "Aucune copie disponible",
            f"Les copies conservées de la liste des prompts {label} sont identiques "
            "à la liste actuelle ou illisibles.",
        )
    latest = backups[index]
    count = latest["count"]
    content = f"{count} prompt(s)"

    def restore():
        try:
            restore_prompt_backup(settings, voice=voice)
        except Exception as exc:
            _report_failure(parent, "Retour impossible", exc)
            return
        refreshed()

    return confirm_action(
        parent,
        "Revenir à la liste précédente",
        f"Remplacer les prompts {label} par la copie du {_format_date(latest['saved_at'])} "
        f"({latest['reason']}, {content}) ? "
        "La liste actuelle sera conservée en copie.",
        restore,
    )
