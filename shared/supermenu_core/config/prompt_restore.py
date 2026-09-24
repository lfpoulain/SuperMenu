"""Restore a prompt library without resetting providers or user preferences."""

import json
from copy import deepcopy


def restore_prompt_defaults(settings, *, voice=False):
    key = "voice_prompts" if voice else "prompts"
    defaults = settings.default_voice_prompts if voice else settings.default_prompts
    previous = settings.settings.value(key, "{}")
    backup_key = key + "_before_restore"
    previous_backup = settings.settings.value(backup_key)
    try:
        settings.settings.setValue(backup_key, previous)
        settings.settings.setValue(
            key, json.dumps(deepcopy(defaults), ensure_ascii=False)
        )
        settings.sync()
    except Exception:
        settings.settings.setValue(key, previous)
        if previous_backup is None:
            settings.settings.remove(backup_key)
        else:
            settings.settings.setValue(backup_key, previous_backup)
        settings.sync()
        raise
