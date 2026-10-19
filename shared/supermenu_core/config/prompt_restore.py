"""Restore a prompt library without resetting providers or user preferences."""

import json
import os
from copy import deepcopy
from datetime import datetime

from .prompts import normalize_prompt_collection, repair_prompt_collection

# Copies kept per library ("prompts_backups" / "voice_prompts_backups"), newest
# first. Each restore, import or repair adds one, so a second operation no
# longer erases the only copy of personal prompts.
BACKUP_SUFFIX = "_backups"
BACKUP_LIMIT = 5
BACKUP_REASONS = {
    "restore": "avant la restauration des prompts d’origine",
    "import": "avant un import",
    "repair": "configuration partiellement illisible",
    "undo": "avant le retour à une copie",
}
WRITE_ERROR = (
    "La configuration n’a pas pu être enregistrée (fichier en lecture seule, "
    "verrouillé ou disque plein). Aucune modification n’a été appliquée."
)


def _library_key(voice):
    return "voice_prompts" if voice else "prompts"


def _write_status(store):
    status = getattr(store, "status", None)
    if not callable(status):
        return None
    try:
        return status()
    except Exception:
        return None


def _file_state(store):
    """Identify the configuration file on disk, or None when it cannot be known."""
    file_name = getattr(store, "fileName", None)
    if not callable(file_name):
        return None
    try:
        path = file_name()
    except Exception:
        return None
    if not isinstance(path, str) or not path:
        return None
    try:
        info = os.stat(path)
    except FileNotFoundError:
        # Not written yet. A path outside any folder (registry) says nothing.
        return "absent" if os.path.isdir(os.path.dirname(path) or ".") else None
    except (OSError, ValueError):
        return None
    # A successful sync replaces the file (new identifier, date or size).
    return (info.st_mtime_ns, info.st_size, info.st_ino)


def sync_settings_or_raise(settings):
    """Write pending values and raise when the configuration file refused them.

    QSettings never raises: a failed write only shows in ``status()``, which
    then stays in error even after later successful writes. A change from "no
    error" is reported; with an older error, the file itself must have been
    rewritten, so an old error neither hides a new failure nor blocks every
    later operation.
    """
    before = _write_status(settings.settings)
    file_before = _file_state(settings.settings)
    settings.sync()
    after = _write_status(settings.settings)
    # QSettings.Status.NoError, read from the enum itself to keep this module
    # independent of Qt.
    no_error = getattr(type(before), "NoError", None)
    if no_error is None or after in (None, no_error):
        return
    if before == no_error:
        raise OSError(WRITE_ERROR)
    if file_before is not None and _file_state(settings.settings) == file_before:
        raise OSError(WRITE_ERROR)


def _raw_text(value):
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        # A hand-edited INI value containing commas is read back as a list.
        return ", ".join(value)
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def _read_backups(store, key):
    try:
        backups = json.loads(store.value(key + BACKUP_SUFFIX, "[]"))
    except (TypeError, ValueError):
        return []
    if not isinstance(backups, list):
        return []
    return [
        backup
        for backup in backups
        if isinstance(backup, dict) and isinstance(backup.get("value"), str)
    ]


def _is_empty_library(raw):
    try:
        return json.loads(raw) == {}
    except (TypeError, ValueError):
        return False


def backup_prompt_library(settings, key, value, reason):
    """Keep a copy of a stored library before it is replaced or repaired.

    Returns True when a new copy was added. An empty library, or a value that
    is already kept, is not copied again, so calling this on every read is cheap.
    """
    raw = _raw_text(value)
    if raw is None or not raw.strip() or _is_empty_library(raw):
        return False
    store = settings.settings
    backups = _read_backups(store, key)
    if any(backup["value"] == raw for backup in backups):
        return False
    backups.insert(
        0,
        {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "reason": reason if reason in BACKUP_REASONS else "repair",
            "value": raw,
        },
    )
    store.setValue(
        key + BACKUP_SUFFIX,
        json.dumps(backups[:BACKUP_LIMIT], ensure_ascii=False),
    )
    return True


def _count(raw, voice):
    try:
        prompts, _problems = repair_prompt_collection(json.loads(raw), voice=voice)
    except (TypeError, ValueError):
        return None
    return len(prompts)


def prompt_backups(settings, *, voice=False):
    """Describe the kept copies, newest first, without their content."""
    return [
        {
            "saved_at": backup.get("saved_at", ""),
            "reason": BACKUP_REASONS.get(backup.get("reason"), BACKUP_REASONS["repair"]),
            "count": _count(backup["value"], voice),
        }
        for backup in _read_backups(settings.settings, _library_key(voice))
    ]


def _same_library(raw, defaults, voice):
    try:
        stored = json.loads(raw)
        if stored == defaults:
            return True
        return normalize_prompt_collection(stored, voice=voice) == (
            normalize_prompt_collection(defaults, voice=voice)
        )
    except (TypeError, ValueError):
        return False


def _same_as_current(raw, current, voice):
    """Whether bringing this copy back would leave the library unchanged."""
    if current is None:
        return False
    if raw == current:
        return True
    try:
        return _same_library(raw, json.loads(current), voice)
    except (TypeError, ValueError):
        return False


def next_prompt_backup(settings, *, voice=False):
    """Index of the copy that "going back" brings back, or None.

    The search starts after the copy matching the current library, so going
    back again moves further back through every kept copy instead of switching
    between the last two lists. Copies identical to the current library or
    unreadable are skipped.
    """
    key = _library_key(voice)
    store = settings.settings
    backups = _read_backups(store, key)
    current = _raw_text(store.value(key))
    same = [_same_as_current(backup["value"], current, voice) for backup in backups]
    start = same.index(True) + 1 if True in same else 0
    for index in (*range(start, len(backups)), *range(start)):
        if not same[index] and _count(backups[index]["value"], voice) is not None:
            return index
    return None


def keep_library_copy(settings, *, voice=False, reason="restore"):
    """Copy the current library before it is replaced, unless it is the default one."""
    key = _library_key(voice)
    defaults = settings.default_voice_prompts if voice else settings.default_prompts
    current = settings.settings.value(key)
    if current is None or _same_library(current, defaults, voice):
        return False
    return backup_prompt_library(settings, key, current, reason)


def _snapshot(store, keys):
    return {key: store.value(key) for key in keys}


def _rollback(settings, snapshot):
    store = settings.settings
    for key, value in snapshot.items():
        if value is None:
            store.remove(key)
        else:
            store.setValue(key, value)
    settings.sync()


def restore_prompt_defaults(settings, *, voice=False):
    key = _library_key(voice)
    defaults = settings.default_voice_prompts if voice else settings.default_prompts
    store = settings.settings
    previous = store.value(key, "{}")
    backup_key = key + "_before_restore"
    snapshot = _snapshot(store, (key, backup_key, key + BACKUP_SUFFIX))
    try:
        # Restoring twice must not replace the copy of personal prompts by the
        # defaults themselves.
        if not _same_library(previous, defaults, voice):
            store.setValue(backup_key, previous)
            backup_prompt_library(settings, key, previous, "restore")
        store.setValue(key, json.dumps(deepcopy(defaults), ensure_ascii=False))
        sync_settings_or_raise(settings)
    except Exception:
        _rollback(settings, snapshot)
        raise


def restore_prompt_backup(settings, *, voice=False, index=None):
    """Put a kept copy back; the current library is kept as a copy in turn.

    Without ``index``, the copy given by ``next_prompt_backup`` is used. The
    copy put back stays in the history: going back again then moves to an
    older copy, and reading a repaired copy does not add it a second time.
    """
    key = _library_key(voice)
    store = settings.settings
    backups = _read_backups(store, key)
    if index is None:
        index = next_prompt_backup(settings, voice=voice)
        if index is None:
            raise ValueError(
                "Aucune autre copie de cette liste de prompts n’est disponible."
            )
    if not 0 <= index < len(backups):
        raise ValueError("Aucune copie de cette liste de prompts n’est disponible.")
    chosen = backups[index]
    try:
        prompts, _problems = repair_prompt_collection(
            json.loads(chosen["value"]), voice=voice
        )
    except (TypeError, ValueError):
        raise ValueError("Cette copie de la liste de prompts est illisible.") from None
    snapshot = _snapshot(store, (key, key + BACKUP_SUFFIX))
    try:
        current = _raw_text(store.value(key))
        if (
            current is not None
            and current.strip()
            and not _is_empty_library(current)
            and not any(
                _same_as_current(backup["value"], current, voice) for backup in backups
            )
        ):
            backups.insert(
                0,
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "reason": "undo",
                    "value": current,
                },
            )
            while len(backups) > BACKUP_LIMIT:
                # The oldest copy goes, never the one being put back.
                del backups[
                    max(i for i, backup in enumerate(backups) if backup is not chosen)
                ]
        store.setValue(key + BACKUP_SUFFIX, json.dumps(backups, ensure_ascii=False))
        # The raw copy is written back as is: values unknown to this version
        # stay available for the version that wrote them.
        store.setValue(key, chosen["value"])
        sync_settings_or_raise(settings)
    except Exception:
        _rollback(settings, snapshot)
        raise
    return len(prompts)
