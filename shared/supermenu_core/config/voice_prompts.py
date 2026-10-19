"""Voice prompt persistence and request composition, independent of the OS."""

import json
import logging
import uuid

from .prompt_restore import backup_prompt_library
from .prompts import (
    default_voice_prompts,
    normalize_prompt_collection,
    repair_prompt_collection,
)

# A child of the "SuperMenu" logger, the only one both platforms write to file.
logger = logging.getLogger("SuperMenu.core.config")

VOICE_ORDER_CHOICES = (
    ("Instruction → Dictée → Sélection", "prompt_transcription_selected"),
    ("Instruction → Sélection → Dictée", "prompt_selected_transcription"),
    ("Sélection → Instruction → Dictée", "selected_prompt_transcription"),
    ("Dictée → Instruction → Sélection", "transcription_prompt_selected"),
    ("Dictée → Sélection → Instruction", "transcription_selected_prompt"),
    ("Sélection → Dictée → Instruction", "selected_transcription_prompt"),
)


def compose_voice_prompt(prompt, transcription, selected_text=""):
    """Keep the Windows request format, including its selection opt-in."""
    instruction = prompt["prompt"]
    if not prompt.get("include_selected_text", False) or not selected_text:
        return f"{instruction}\n\n{transcription}"
    parts = {
        "prompt": instruction,
        "transcription": f"Texte transcrit: {transcription}",
        "selected": f"Texte sélectionné: {selected_text}",
    }
    order = prompt.get("prompt_order", "prompt_transcription_selected")
    if order not in {value for _, value in VOICE_ORDER_CHOICES}:
        order = "prompt_transcription_selected"
    return "\n\n".join(parts[key] for key in order.split("_"))


class VoicePromptSettingsMixin:
    def initialize_voice_prompts(self):
        self.default_voice_prompts = default_voice_prompts()
        if not self.settings.contains("voice_prompts"):
            self.set_voice_prompts(self.default_voice_prompts)

    def get_voice_prompts(self):
        stored = self.settings.value("voice_prompts", "{}")
        try:
            raw = json.loads(stored)
            normalized, problems = repair_prompt_collection(raw, voice=True)
        except (TypeError, ValueError):
            # Keep the unreadable value: the next edit replaces this key.
            backup_prompt_library(self, "voice_prompts", stored, "repair")
            logger.error(
                "Configuration de prompts vocaux invalide"
            )
            return {}
        if problems:
            # Show every readable prompt, but leave the stored value untouched
            # until the next edit; a copy of it is kept first.
            if backup_prompt_library(self, "voice_prompts", stored, "repair"):
                logger.warning(
                    "%d anomalie(s) dans les prompts vocaux : copie conservée dans "
                    "voice_prompts_backups",
                    len(problems),
                )
        elif normalized != raw:
            self.set_voice_prompts(normalized)
        return normalized

    def get_voice_prompt(self, prompt_id):
        return self.get_voice_prompts().get(prompt_id)

    def set_voice_prompts(self, prompts):
        normalized = normalize_prompt_collection(prompts, voice=True)
        self.settings.setValue(
            "voice_prompts", json.dumps(normalized, ensure_ascii=False)
        )
        self.sync()

    def update_voice_prompt(
        self,
        prompt_id,
        name,
        prompt,
        status,
        insert_directly=False,
        position=None,
        include_selected_text=False,
        prompt_order="prompt_transcription_selected",
        reasoning_mode=None,
        model_target=None,
    ):
        prompts = self.get_voice_prompts()
        prompts[prompt_id] = {
            **prompts.get(prompt_id, {}),
            "model_target": model_target if model_target is not None else prompts.get(prompt_id, {}).get("model_target", {}),
            "reasoning_mode": reasoning_mode if reasoning_mode is not None else prompts.get(prompt_id, {}).get("reasoning_mode", "default"),
            "name": name,
            "prompt": prompt,
            "status": status,
            "insert_directly": insert_directly,
            "position": (
                position
                if position is not None
                else prompts.get(prompt_id, {}).get("position", 999)
            ),
            "include_selected_text": include_selected_text,
            "prompt_order": prompt_order,
        }
        self.set_voice_prompts(prompts)

    def add_voice_prompt(
        self,
        prompt_id,
        name,
        prompt,
        status,
        insert_directly=False,
        position=999,
        include_selected_text=False,
        prompt_order="prompt_transcription_selected",
        reasoning_mode=None,
        model_target=None,
    ):
        prompts = self.get_voice_prompts()
        identifier = str(prompt_id or uuid.uuid4().hex)
        suffix, base = 1, identifier
        while identifier in prompts:
            identifier = f"{base}_{suffix}"
            suffix += 1
        self.update_voice_prompt(
            identifier,
            name,
            prompt,
            status,
            insert_directly,
            position,
            include_selected_text,
            prompt_order,
            reasoning_mode=reasoning_mode,
            model_target=model_target,
        )
        return identifier

    def delete_voice_prompt(self, prompt_id):
        prompts = self.get_voice_prompts()
        if prompt_id not in prompts:
            return False
        del prompts[prompt_id]
        self.set_voice_prompts(prompts)
        return True
