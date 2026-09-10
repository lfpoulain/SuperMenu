"""One JSON format for Windows and Mac, with support for older Mac exports."""

import json
from pathlib import Path

from .prompts import normalize_prompt_collection


def export_prompt_bundle(settings, file_path):
    payload = {
        "schema_version": 1,
        "text_prompts": settings.get_prompts(),
        "voice_prompts": settings.get_voice_prompts(),
    }
    Path(file_path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def import_prompt_bundle(settings, file_path):
    payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("La racine du fichier doit être un objet JSON.")
    text_key = "text_prompts" if "text_prompts" in payload else "prompts"
    if text_key not in payload and "voice_prompts" not in payload:
        raise ValueError("Le fichier ne contient aucune collection de prompts.")
    updates = {}
    if text_key in payload:
        updates["prompts"] = normalize_prompt_collection(
            payload[text_key], require_non_empty=True
        )
    if "voice_prompts" in payload:
        updates["voice_prompts"] = normalize_prompt_collection(
            payload["voice_prompts"], voice=True, require_non_empty=True
        )
    # Validate every collection before the first write. Missing collections are
    # preserved, including voice prompts when importing an old text-only file.
    original = {key: settings.settings.value(key, "{}") for key in updates}
    try:
        for key, prompts in updates.items():
            settings.settings.setValue(key, json.dumps(prompts, ensure_ascii=False))
        settings.sync()
    except Exception:
        for key, value in original.items():
            settings.settings.setValue(key, value)
        settings.sync()
        raise
    return sum(len(prompts) for prompts in updates.values())
