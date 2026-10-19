"""Text prompt storage shared by the Windows and macOS settings."""

import json
import logging
import uuid

from .prompt_restore import backup_prompt_library
from .prompts import normalize_prompt_collection, repair_prompt_collection

logger = logging.getLogger("SuperMenu.core.config")

DEFAULT_TEXT_PROMPT_STATUS = "Traitement en cours…"


class TextPromptSettingsMixin:
    """Read and edit the text prompts kept under the ``prompts`` key.

    The host provides ``settings`` (a QSettings) and ``default_prompts``.
    A read repairs or leaves out each invalid entry without hiding the others;
    the stored value is then left untouched until the next edit, and a copy
    is kept in ``prompts_backups`` first. A valid library whose schema only
    had to migrate is stored back. Writes refuse invalid data and shared
    hotkeys instead of saving an empty library or clearing another prompt's
    hotkey.

    ``TEXT_PROMPTS_FALL_BACK_TO_DEFAULTS`` makes an empty or unreadable
    library read as the default catalog instead of an empty one; the macOS
    library comes back this way once its last prompt is deleted.
    """

    TEXT_PROMPTS_FALL_BACK_TO_DEFAULTS = False

    def get_prompts(self):
        stored = self.settings.value("prompts", "{}")
        try:
            raw = json.loads(stored) if isinstance(stored, str) else stored
            prompts, problems = repair_prompt_collection(raw)
        except (TypeError, ValueError) as exc:
            # Keep the unreadable value: the next edit replaces this key.
            backup_prompt_library(self, "prompts", stored, "repair")
            logger.error("Configuration de prompts invalide: %s", exc)
            prompts = {}
        else:
            if problems:
                if backup_prompt_library(self, "prompts", stored, "repair"):
                    logger.warning(
                        "%d anomalie(s) dans les prompts : prompts réparés "
                        "ou ignorés, copie conservée dans prompts_backups",
                        len(problems),
                    )
            elif prompts != raw:
                self.settings.setValue(
                    "prompts", json.dumps(prompts, ensure_ascii=False)
                )
        if not prompts and self.TEXT_PROMPTS_FALL_BACK_TO_DEFAULTS:
            return repair_prompt_collection(self.default_prompts)[0]
        return prompts

    def get_prompt(self, prompt_id):
        return self.get_prompts().get(prompt_id)

    def set_prompts(self, prompts):
        if isinstance(prompts, str):
            prompts = json.loads(prompts)
        normalized = normalize_prompt_collection(prompts, reject_duplicate_hotkeys=True)
        self.settings.setValue("prompts", json.dumps(normalized, ensure_ascii=False))

    def update_prompt(
        self,
        prompt_id,
        name,
        prompt,
        status,
        insert_directly=False,
        position=None,
        hotkey="",
        reasoning_mode=None,
        model_target=None,
    ):
        """Replace a prompt, or create it under this id when it is missing."""
        prompts = self.get_prompts()
        current = prompts.get(prompt_id, {})
        hotkey = str(hotkey or "").strip()
        self._check_prompt_hotkey(prompts, hotkey, prompt_id)
        prompts[prompt_id] = self._text_prompt_entry(
            current,
            name=name or prompt_id,
            prompt=prompt,
            status=status,
            insert_directly=insert_directly,
            position=current.get("position", 999) if position is None else position,
            hotkey=hotkey,
            reasoning_mode=reasoning_mode,
            model_target=model_target,
        )
        self.set_prompts(prompts)

    def add_prompt(
        self,
        prompt_id,
        name,
        prompt,
        status,
        insert_directly=False,
        position=999,
        hotkey="",
        reasoning_mode=None,
        model_target=None,
    ):
        """Add a prompt and return its id, suffixed when ``prompt_id`` is taken."""
        prompts = self.get_prompts()
        base = str(prompt_id or uuid.uuid4().hex).strip()
        identifier, counter = base, 1
        while identifier in prompts:
            identifier = f"{base}_{counter}"
            counter += 1
        hotkey = str(hotkey or "").strip()
        self._check_prompt_hotkey(prompts, hotkey, identifier)
        prompts[identifier] = self._text_prompt_entry(
            {},
            name=name or "Nouveau prompt",
            prompt=prompt,
            status=status,
            insert_directly=insert_directly,
            position=position,
            hotkey=hotkey,
            reasoning_mode=reasoning_mode,
            model_target=model_target,
        )
        self.set_prompts(prompts)
        return identifier

    def delete_prompt(self, prompt_id):
        prompts = self.get_prompts()
        if prompt_id not in prompts:
            return False
        del prompts[prompt_id]
        self.set_prompts(prompts)
        return True

    def _check_prompt_hotkey(self, prompts, hotkey, prompt_id):
        """Hook run before an edit; ``set_prompts`` refuses shared hotkeys anyway."""

    @staticmethod
    def _text_prompt_entry(
        current,
        *,
        name,
        prompt,
        status,
        insert_directly,
        position,
        hotkey,
        reasoning_mode,
        model_target,
    ):
        return {
            "model_target": (
                current.get("model_target", {}) if model_target is None else model_target
            ),
            "reasoning_mode": (
                current.get("reasoning_mode", "default")
                if reasoning_mode is None
                else reasoning_mode
            ),
            "name": str(name),
            "prompt": str(prompt or ""),
            "status": str(status or DEFAULT_TEXT_PROMPT_STATUS),
            "insert_directly": bool(insert_directly),
            "position": int(position),
            "hotkey": hotkey,
        }
