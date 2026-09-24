"""Common factory-reset confirmation for the text and voice libraries."""

from supermenu_core.config.prompt_restore import restore_prompt_defaults
from .confirmations import confirm_action


def restore_library(parent, settings, refreshed, *, voice=False):
    label = "vocaux" if voice else "texte"

    def restore():
        restore_prompt_defaults(settings, voice=voice)
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
