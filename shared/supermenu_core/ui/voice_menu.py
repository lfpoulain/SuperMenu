"""Common voice actions; platforms retain their own target and menu lifecycle."""

from .controls import populate_prompt_menu


def populate_voice_menu(menu, prompts, data_for):
    action = menu.addAction("Dicter du texte…")
    action.setData(data_for("voice", None))
    menu.addSeparator()
    populate_prompt_menu(menu, prompts, lambda key: data_for("voice_prompt", key))
    menu.addSeparator()
    action = menu.addAction("Prompt vocal personnalisé…")
    action.setData(data_for("voice_godmode", None))
