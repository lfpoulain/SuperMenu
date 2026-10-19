"""One JSON format for Windows and Mac, with support for older Mac exports."""

import json
from pathlib import Path

from .model_target import without_server
from .prompt_restore import (
    BACKUP_SUFFIX,
    backup_prompt_library,
    sync_settings_or_raise,
)
from .prompts import normalize_prompt_collection

# Display label of the chosen device ("Sur 192.168.1.20", an LM Link machine
# name): it describes the exporting server, so it is neither shared nor
# trusted. The editor rebuilds it from the configured server.
_LOCAL_LABEL_KEYS = ("device_name",)


def _follow_configured_server(prompts):
    """Drop the server stored in model choices; keep the model and device.

    A prompt always runs on the server of the Text settings. An exported file
    therefore never reveals local server addresses or machine names, and an
    imported file can never send text to a server the user did not configure.
    """
    result = {}
    for prompt_id, prompt in prompts.items():
        if isinstance(prompt, dict) and isinstance(prompt.get("model_target"), dict):
            target = without_server(prompt["model_target"])
            for key in _LOCAL_LABEL_KEYS:
                target.pop(key, None)
            prompt = {**prompt, "model_target": target}
        result[prompt_id] = prompt
    return result


def export_prompt_bundle(settings, file_path):
    payload = {
        "schema_version": 1,
        "text_prompts": _follow_configured_server(settings.get_prompts()),
        "voice_prompts": _follow_configured_server(settings.get_voice_prompts()),
    }
    Path(file_path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def import_prompt_bundle(settings, file_path):
    # utf-8-sig also reads files saved with a BOM by Windows tools.
    payload = json.loads(Path(file_path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("La racine du fichier doit être un objet JSON.")
    text_key = "text_prompts" if "text_prompts" in payload else "prompts"
    if text_key not in payload and "voice_prompts" not in payload:
        raise ValueError("Le fichier ne contient aucune collection de prompts.")
    updates = {}
    if text_key in payload:
        updates["prompts"] = _follow_configured_server(
            normalize_prompt_collection(payload[text_key], require_non_empty=True)
        )
    if "voice_prompts" in payload:
        updates["voice_prompts"] = _follow_configured_server(
            normalize_prompt_collection(
                payload["voice_prompts"], voice=True, require_non_empty=True
            )
        )
    # Validate every collection before the first write. Missing collections are
    # preserved, including voice prompts when importing an old text-only file.
    store = settings.settings
    original = {}
    for key in updates:
        for stored_key in (key, key + BACKUP_SUFFIX):
            original[stored_key] = store.value(stored_key)
    try:
        for key, prompts in updates.items():
            # The replaced library stays available as a copy.
            backup_prompt_library(settings, key, original[key], "import")
            store.setValue(key, json.dumps(prompts, ensure_ascii=False))
        sync_settings_or_raise(settings)
    except Exception:
        for key, value in original.items():
            if value is None:
                store.remove(key)
            else:
                store.setValue(key, value)
        settings.sync()
        raise
    return sum(len(prompts) for prompts in updates.values())
