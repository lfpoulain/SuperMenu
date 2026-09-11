"""Prompt defaults, schemas and migrations shared by desktop clients."""

from copy import deepcopy
from .prompt_reasoning import normalize_reasoning_mode

LEGACY_INSTANT_HOTKEY = "Ctrl+Alt+I"
VOICE_PROMPT_ORDERS = {
    "prompt_transcription_selected",
    "prompt_selected_transcription",
    "transcription_prompt_selected",
    "transcription_selected_prompt",
    "selected_prompt_transcription",
    "selected_transcription_prompt",
}

_DEFAULT_TEXT_PROMPTS = {
    "corriger": {
        "name": "Corriger",
        "prompt": (
            "Envoi directement le résultat : Corrige l'orthographe, la grammaire "
            "et la conjugaison de ce texte. Conserve le ton, le style et le "
            "formatage :"
        ),
        "status": "En cours de correction...",
        "insert_directly": False,
        "position": 10,
    },
    "corrections_montage": {
        "name": "Corrections Montage",
        "prompt": (
            "Envoi directement le résultat : Corrige l'orthographe, la grammaire "
            "et la conjugaison de ce texte, sans me parler, en tenant compte du "
            "contexte spécifique : il s'agit de phrases ou de mots qui seront "
            "affichés en surimpression sur des vidéos YouTube majoritairement en "
            "rapport avec l'électronique, le DIY, le Bricolage, la domotique et "
            "l'impression 3D. Parfois, un seul mot peut être employé donc utilise "
            "le contexte pour le corriger. "
            "Conserve le ton, le style et le formatage :"
        ),
        "status": "En cours de correction pour montage...",
        "insert_directly": False,
        "position": 20,
    },
    "reformuler": {
        "name": "Reformuler",
        "prompt": (
            "Envoi directement le résultat : Reformule le texte ou le paragraphe "
            "suivant pour assurer la clarté, la concision et un flux naturel. "
            "La révision doit préserver le ton, le style et le formatage du texte "
            "original :"
        ),
        "status": "En cours de reformulation...",
        "insert_directly": False,
        "position": 30,
    },
    "resumer": {
        "name": "Résumer",
        "prompt": (
            "Résume ce qui suit tout en conservant l'intégralité des "
            "informations importantes et pertinentes :"
        ),
        "status": "En cours de résumé...",
        "insert_directly": False,
        "position": 40,
    },
    "expliquer": {
        "name": "Expliquer",
        "prompt": "Explique ce qui suit :",
        "status": "En cours d'explication...",
        "insert_directly": False,
        "position": 50,
    },
    "extraire_passages_importants": {
        "name": "Extraire Passages Importants",
        "prompt": (
            "Voici un texte issu d'une vidéo YouTube en cours de montage en "
            "rapport avec l'électronique, le DIY, le Bricolage, la domotique ou "
            "l'impression 3D. Extrait de ce texte une liste chronologiquement "
            "logique des passages importants à inclure dans le montage de la "
            "vidéo. Pour chaque passage, explique en une phrase pourquoi il est "
            "pertinent. Voici le texte de la vidéo :"
        ),
        "status": "Extraction des passages importants en cours...",
        "insert_directly": False,
        "position": 60,
    },
    "developper": {
        "name": "Développer",
        "prompt": (
            "En considérant le ton, le style et le formatage original, aide-moi à "
            "exprimer l'idée suivante de manière plus claire et plus articulée. Le "
            "style du message peut être formel, informel, décontracté, empathique, "
            "assertif ou persuasif, selon le contexte du message original. Il n'y "
            "a pas de longueur minimale ou maximale définie. Voici ce que j'essaie "
            "de dire :"
        ),
        "status": "En cours de développement...",
        "insert_directly": False,
        "position": 70,
    },
    "generer_reponse": {
        "name": "Générer une réponse",
        "prompt": (
            "Rédige une réponse à tout message donné. La réponse doit respecter "
            "le ton, le style, le formatage et le contexte culturel ou régional "
            "de l'expéditeur initial. Maintiens le même niveau de formalité et de "
            "ton émotionnel que le message original. Les réponses peuvent avoir "
            "n'importe quelle longueur, à condition qu'elles communiquent "
            "efficacement la réponse à l'expéditeur initial :"
        ),
        "status": "En cours de génération de réponse...",
        "insert_directly": False,
        "position": 80,
    },
    "trouver_actions": {
        "name": "Trouver les actions à faire",
        "prompt": "Trouve les actions à faire et présente-les dans une liste :",
        "status": "En cours de recherche des actions à faire...",
        "insert_directly": False,
        "position": 90,
    },
    "traduire_en_anglais": {
        "name": "Traduire en anglais",
        "prompt": (
            "Génère une traduction en anglais du texte suivant, en veillant à ce "
            "que la traduction transmette avec précision le sens ou l'idée voulue. "
            "La traduction doit préserver le ton, le style et le formatage du "
            "texte original :"
        ),
        "status": "En cours de traduction en anglais...",
        "insert_directly": False,
        "position": 100,
    },
    "traduire_en_francais": {
        "name": "Traduire en français",
        "prompt": (
            "Génère une traduction en français du texte suivant, en veillant à "
            "ce que la traduction transmette avec précision le sens ou l'idée "
            "voulue. La traduction doit préserver le ton, le style et le "
            "formatage du texte original :"
        ),
        "status": "En cours de traduction en français...",
        "insert_directly": False,
        "position": 110,
    },
}

_DEFAULT_VOICE_PROMPTS = {
    "decrire_reponse": {
        "name": "Décrire une réponse",
        "prompt": (
            "Analyse et décris en détail ce qui suit, en fournissant un contexte "
            "pertinent et des explications claires :"
        ),
        "status": "Analyse de la réponse vocale en cours...",
        "insert_directly": True,
        "position": 10,
        "include_selected_text": False,
        "prompt_order": "prompt_transcription_selected",
    },
    "resumer_vocal": {
        "name": "Résumer",
        "prompt": (
            "Résume ce qui suit tout en conservant l'intégralité des "
            "informations importantes et pertinentes :"
        ),
        "status": "Résumé de la réponse vocale en cours...",
        "insert_directly": True,
        "position": 20,
        "include_selected_text": False,
        "prompt_order": "prompt_transcription_selected",
    },
    "traduire_en_anglais_vocal": {
        "name": "Traduire en anglais",
        "prompt": (
            "Génère une traduction en anglais du texte suivant, en veillant à ce "
            "que la traduction transmette avec précision le sens ou l'idée voulue :"
        ),
        "status": "Traduction en anglais en cours...",
        "insert_directly": True,
        "position": 30,
        "include_selected_text": False,
        "prompt_order": "prompt_transcription_selected",
    },
}


def default_text_prompts():
    """Return an isolated copy of the cross-platform text prompt catalog."""
    prompts = deepcopy(_DEFAULT_TEXT_PROMPTS)
    for prompt in prompts.values():
        prompt.setdefault("hotkey", "")
    return prompts


def default_voice_prompts():
    """Return an isolated copy of the current voice prompt catalog."""
    return deepcopy(_DEFAULT_VOICE_PROMPTS)


def normalize_prompt_collection(raw_prompts, *, voice=False, require_non_empty=False):
    """Validate and migrate a prompt collection without mutating its input."""
    if not isinstance(raw_prompts, dict):
        raise ValueError("La collection de prompts doit être un objet JSON.")

    normalized = {}
    prompt_hotkeys = set()
    required_strings = ("name", "prompt", "status")
    for prompt_id, raw_prompt in raw_prompts.items():
        if not isinstance(prompt_id, str) or not prompt_id.strip():
            raise ValueError("Chaque prompt doit avoir un identifiant texte non vide.")
        if not isinstance(raw_prompt, dict):
            raise ValueError(f"Le prompt '{prompt_id}' doit être un objet JSON.")

        prompt = dict(raw_prompt)
        for field in required_strings:
            if not isinstance(prompt.get(field), str):
                raise ValueError(
                    f"Le champ '{field}' du prompt '{prompt_id}' doit être un texte."
                )
            if require_non_empty and not prompt[field].strip():
                raise ValueError(
                    f"Le champ '{field}' du prompt '{prompt_id}' "
                    "ne peut pas être vide dans un fichier importé."
                )

        position = prompt.get("position", 999)
        if isinstance(position, bool) or not isinstance(position, int):
            raise ValueError(
                f"La position du prompt '{prompt_id}' doit être un entier."
            )
        prompt["position"] = position

        insert_default = True if voice else False
        insert_directly = prompt.get("insert_directly", insert_default)
        if not isinstance(insert_directly, bool):
            raise ValueError(
                f"Le champ 'insert_directly' du prompt '{prompt_id}' "
                "doit être booléen."
            )
        prompt["insert_directly"] = insert_directly
        if "reasoning_mode" in prompt:
            prompt["reasoning_mode"] = normalize_reasoning_mode(prompt["reasoning_mode"])

        if voice:
            include_selected = prompt.get("include_selected_text", False)
            if not isinstance(include_selected, bool):
                raise ValueError(
                    f"Le champ 'include_selected_text' du prompt '{prompt_id}' "
                    "doit être booléen."
                )
            prompt["include_selected_text"] = include_selected

            prompt_order = prompt.get("prompt_order", "prompt_transcription_selected")
            if prompt_order not in VOICE_PROMPT_ORDERS:
                raise ValueError(
                    f"L'ordre des éléments du prompt '{prompt_id}' est invalide."
                )
            prompt["prompt_order"] = prompt_order
        else:
            legacy_instant = prompt.pop("instant_hotkey", False)
            if not isinstance(legacy_instant, bool):
                raise ValueError(
                    f"Le champ 'instant_hotkey' du prompt '{prompt_id}' "
                    "doit être booléen."
                )

            hotkey = prompt.get("hotkey", "")
            if not isinstance(hotkey, str):
                raise ValueError(
                    f"Le champ 'hotkey' du prompt '{prompt_id}' doit être un texte."
                )
            hotkey = hotkey.strip()
            if legacy_instant and not hotkey:
                hotkey = LEGACY_INSTANT_HOTKEY

            normalized_hotkey = hotkey.casefold()
            if normalized_hotkey and normalized_hotkey in prompt_hotkeys:
                if require_non_empty:
                    raise ValueError(
                        f"Le raccourci '{hotkey}' est associé à plusieurs prompts."
                    )
                hotkey = ""
                normalized_hotkey = ""
            if normalized_hotkey:
                prompt_hotkeys.add(normalized_hotkey)
            prompt["hotkey"] = hotkey

        normalized[prompt_id] = prompt

    return normalized
