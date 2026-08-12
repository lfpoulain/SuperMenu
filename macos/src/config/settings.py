"""Persistent settings for the independent macOS application."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

import keyring
from PySide6.QtCore import QSettings

from src.api.model_capabilities import normalize_reasoning_option
from src.config.build_info import BUILD_CHANNEL
from src.config.openai_models import (
    DEFAULT_OPENAI_MODEL,
    get_default_reasoning_effort_for_model,
    normalize_openai_model,
    normalize_reasoning_effort,
)
from src.utils.logger import log
from src.utils.paths import settings_file


CUSTOM_REASONING_EFFORTS = ["none", "low", "medium", "high"]
OLLAMA_GPT_OSS_THINK_EFFORTS = ["low", "medium", "high"]
UPDATE_CHANNELS = ("stable", "beta")
KEYRING_SERVICE = "SuperMenu macOS"


def _normalize_update_channel(value) -> str:
    return "beta" if str(value or "").strip().lower() == "beta" else "stable"


def _default_prompts() -> dict[str, dict]:
    return {
        "corriger": {
            "name": "Corriger",
            "prompt": "Corrige l'orthographe, la grammaire et la conjugaison de ce texte. Conserve le ton, le style et le formatage :",
            "status": "Correction en cours…",
            "insert_directly": False,
            "hotkey": "",
            "position": 10,
        },
        "reformuler": {
            "name": "Reformuler",
            "prompt": "Reformule le texte suivant pour améliorer sa clarté et sa concision tout en préservant son ton et son formatage :",
            "status": "Reformulation en cours…",
            "insert_directly": False,
            "hotkey": "",
            "position": 20,
        },
        "resumer": {
            "name": "Résumer",
            "prompt": "Résume ce qui suit en conservant les informations importantes :",
            "status": "Résumé en cours…",
            "insert_directly": False,
            "hotkey": "",
            "position": 30,
        },
        "expliquer": {
            "name": "Expliquer",
            "prompt": "Explique clairement ce qui suit :",
            "status": "Explication en cours…",
            "insert_directly": False,
            "hotkey": "",
            "position": 40,
        },
        "developper": {
            "name": "Développer",
            "prompt": "Développe l'idée suivante de manière claire et naturelle, en conservant le ton original :",
            "status": "Développement en cours…",
            "insert_directly": False,
            "hotkey": "",
            "position": 50,
        },
        "generer_reponse": {
            "name": "Générer une réponse",
            "prompt": "Rédige une réponse adaptée au message suivant, à son ton et à son niveau de formalité :",
            "status": "Génération en cours…",
            "insert_directly": False,
            "hotkey": "",
            "position": 60,
        },
        "traduire_en_anglais": {
            "name": "Traduire en anglais",
            "prompt": "Traduis précisément le texte suivant en anglais en préservant son ton et son formatage :",
            "status": "Traduction en cours…",
            "insert_directly": False,
            "hotkey": "",
            "position": 70,
        },
        "traduire_en_francais": {
            "name": "Traduire en français",
            "prompt": "Traduis précisément le texte suivant en français en préservant son ton et son formatage :",
            "status": "Traduction en cours…",
            "insert_directly": False,
            "hotkey": "",
            "position": 80,
        },
    }


def _normalize_prompts(value) -> dict[str, dict]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    if not isinstance(value, dict):
        return {}
    normalized = {}
    for prompt_id, prompt in value.items():
        if not isinstance(prompt, dict):
            continue
        identifier = str(prompt_id or "").strip()
        if not identifier:
            continue
        normalized[identifier] = {
            "name": str(prompt.get("name") or identifier),
            "prompt": str(prompt.get("prompt") or ""),
            "status": str(prompt.get("status") or "Traitement en cours…"),
            "insert_directly": bool(prompt.get("insert_directly", False)),
            "hotkey": str(prompt.get("hotkey") or "").strip(),
            "position": int(prompt.get("position", 999)),
        }
    return normalized


class Settings:
    def __init__(self, config_path: str | None = None):
        self.config_path = str(config_path or settings_file())
        Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)
        self.settings = QSettings(self.config_path, QSettings.Format.IniFormat)
        self.default_prompts = _default_prompts()
        self.default_hotkey = "Cmd+Shift+Space"
        self.default_custom_hotkey = "Cmd+Shift+M"
        self.default_model = DEFAULT_OPENAI_MODEL
        self.default_reasoning_effort = get_default_reasoning_effort_for_model(
            self.default_model
        )
        self.default_custom_reasoning_effort = "none"
        self.default_update_channel = _normalize_update_channel(BUILD_CHANNEL)
        self.default_theme = "dark"
        self._initialize_settings()

    def _initialize_settings(self) -> None:
        defaults = {
            "hotkey": self.default_hotkey,
            "custom_hotkey": self.default_custom_hotkey,
            "model": self.default_model,
            "openai_reasoning_effort": self.default_reasoning_effort,
            "custom_reasoning_effort": self.default_custom_reasoning_effort,
            "custom_endpoint": "",
            "custom_endpoint_type": "ollama",
            "custom_model": "",
            "use_custom_endpoint": False,
            "theme": self.default_theme,
            "update_channel": self.default_update_channel,
            "last_update_check_date": "",
            "prompts": json.dumps(self.default_prompts, ensure_ascii=False),
        }
        for key, value in defaults.items():
            if not self.settings.contains(key):
                self.settings.setValue(key, value)
        self.settings.sync()

    def get_api_key(self) -> str:
        try:
            return keyring.get_password(KEYRING_SERVICE, "openai_api_key") or ""
        except Exception as exc:
            log(f"Lecture de la clé API impossible : {exc}", logging.WARNING)
            return ""

    def set_api_key(self, api_key: str) -> None:
        value = str(api_key or "").strip()
        if value:
            keyring.set_password(KEYRING_SERVICE, "openai_api_key", value)
            return
        try:
            keyring.delete_password(KEYRING_SERVICE, "openai_api_key")
        except keyring.errors.PasswordDeleteError:
            pass

    def get_model(self) -> str:
        model = normalize_openai_model(self.settings.value("model"))
        if model != self.settings.value("model"):
            self.set_model(model)
        return model

    def set_model(self, model: str) -> None:
        self.settings.setValue("model", normalize_openai_model(model))

    def get_openai_reasoning_effort(self, model=None) -> str:
        selected_model = normalize_openai_model(model or self.get_model())
        return normalize_reasoning_effort(
            selected_model,
            self.settings.value(
                "openai_reasoning_effort",
                get_default_reasoning_effort_for_model(selected_model),
            ),
        )

    def set_openai_reasoning_effort(self, effort, model=None) -> None:
        selected_model = normalize_openai_model(model or self.get_model())
        self.settings.setValue(
            "openai_reasoning_effort",
            normalize_reasoning_effort(selected_model, effort),
        )

    def get_custom_reasoning_effort(self) -> str:
        value = normalize_reasoning_option(
            self.settings.value("custom_reasoning_effort", "none")
        )
        return value if value in CUSTOM_REASONING_EFFORTS else "none"

    def set_custom_reasoning_effort(self, effort) -> None:
        normalized = normalize_reasoning_option(effort)
        if normalized not in CUSTOM_REASONING_EFFORTS:
            normalized = "none"
        self.settings.setValue("custom_reasoning_effort", normalized)

    def get_reasoning_effort(self) -> str:
        if self.get_use_custom_endpoint():
            return self.get_custom_reasoning_effort()
        return self.get_openai_reasoning_effort()

    def get_custom_endpoint(self) -> str:
        return str(self.settings.value("custom_endpoint", "") or "").strip()

    def set_custom_endpoint(self, endpoint: str) -> None:
        self.settings.setValue("custom_endpoint", str(endpoint or "").strip())

    def get_custom_endpoint_type(self) -> str:
        value = str(
            self.settings.value("custom_endpoint_type", "ollama") or "ollama"
        ).lower()
        return value if value in {"ollama", "lmstudio"} else "ollama"

    def set_custom_endpoint_type(self, endpoint_type: str) -> None:
        normalized = str(endpoint_type or "").lower()
        self.settings.setValue(
            "custom_endpoint_type",
            normalized if normalized in {"ollama", "lmstudio"} else "ollama",
        )

    def get_custom_model(self) -> str:
        return str(self.settings.value("custom_model", "") or "").strip()

    def set_custom_model(self, model: str) -> None:
        self.settings.setValue("custom_model", str(model or "").strip())

    def get_use_custom_endpoint(self) -> bool:
        return self.settings.value("use_custom_endpoint", False, type=bool)

    def set_use_custom_endpoint(self, enabled: bool) -> None:
        self.settings.setValue("use_custom_endpoint", bool(enabled))

    def get_hotkey(self) -> str:
        return str(self.settings.value("hotkey", self.default_hotkey))

    def set_hotkey(self, hotkey: str) -> None:
        self.settings.setValue("hotkey", str(hotkey or "").strip())

    def get_custom_hotkey(self) -> str:
        return str(self.settings.value("custom_hotkey", self.default_custom_hotkey))

    def set_custom_hotkey(self, hotkey: str) -> None:
        self.settings.setValue("custom_hotkey", str(hotkey or "").strip())

    def get_theme(self) -> str:
        theme = str(self.settings.value("theme", self.default_theme)).lower()
        return theme if theme in {"dark", "light", "auto"} else self.default_theme

    def set_theme(self, theme: str) -> None:
        normalized = str(theme or "").lower()
        if normalized not in {"dark", "light", "auto"}:
            normalized = self.default_theme
        self.settings.setValue("theme", normalized)

    def get_last_update_check_date(self) -> str:
        return str(self.settings.value("last_update_check_date", "") or "")

    def set_last_update_check_date(self, date_value: str) -> None:
        self.settings.setValue("last_update_check_date", str(date_value or ""))

    def get_update_channel(self) -> str:
        return _normalize_update_channel(
            self.settings.value("update_channel", self.default_update_channel)
        )

    def set_update_channel(self, channel: str) -> None:
        self.settings.setValue("update_channel", _normalize_update_channel(channel))

    def get_prompts(self) -> dict[str, dict]:
        prompts = _normalize_prompts(self.settings.value("prompts", "{}"))
        return prompts or _normalize_prompts(self.default_prompts)

    def get_prompt(self, prompt_id: str):
        return self.get_prompts().get(prompt_id)

    @staticmethod
    def _assert_unique_hotkeys(prompts: dict[str, dict]) -> None:
        seen = {}
        for prompt_id, prompt in prompts.items():
            hotkey = str(prompt.get("hotkey") or "").strip().casefold()
            if not hotkey:
                continue
            if hotkey in seen:
                raise ValueError(
                    f"Le raccourci est déjà utilisé par le prompt '{seen[hotkey]}'."
                )
            seen[hotkey] = prompt_id

    def set_prompts(self, prompts: dict[str, dict]) -> None:
        normalized = _normalize_prompts(prompts)
        self._assert_unique_hotkeys(normalized)
        self.settings.setValue(
            "prompts",
            json.dumps(normalized, ensure_ascii=False),
        )

    def update_prompt(
        self,
        prompt_id: str,
        name: str,
        prompt: str,
        status: str,
        insert_directly: bool = False,
        position: int | None = None,
        hotkey: str = "",
    ) -> None:
        prompts = self.get_prompts()
        if prompt_id not in prompts:
            raise KeyError(prompt_id)
        prompts[prompt_id] = {
            "name": str(name or prompt_id),
            "prompt": str(prompt or ""),
            "status": str(status or "Traitement en cours…"),
            "insert_directly": bool(insert_directly),
            "hotkey": str(hotkey or "").strip(),
            "position": int(
                position
                if position is not None
                else prompts[prompt_id].get("position", 999)
            ),
        }
        self.set_prompts(prompts)

    def add_prompt(
        self,
        prompt_id: str | None,
        name: str,
        prompt: str,
        status: str,
        insert_directly: bool = False,
        position: int = 999,
        hotkey: str = "",
    ) -> str:
        prompts = self.get_prompts()
        identifier = str(prompt_id or uuid.uuid4().hex).strip()
        if identifier in prompts:
            raise ValueError("Cet identifiant de prompt existe déjà.")
        prompts[identifier] = {
            "name": str(name or "Nouveau prompt"),
            "prompt": str(prompt or ""),
            "status": str(status or "Traitement en cours…"),
            "insert_directly": bool(insert_directly),
            "hotkey": str(hotkey or "").strip(),
            "position": int(position),
        }
        self.set_prompts(prompts)
        return identifier

    def delete_prompt(self, prompt_id: str) -> None:
        prompts = self.get_prompts()
        prompts.pop(prompt_id, None)
        self.set_prompts(prompts)

    def export_prompts(self, file_path: str) -> None:
        payload = {"schema_version": 1, "prompts": self.get_prompts()}
        Path(file_path).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def import_prompts(self, file_path: str) -> int:
        payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
        prompts = payload.get("prompts") if isinstance(payload, dict) else None
        normalized = _normalize_prompts(prompts)
        if not normalized:
            raise ValueError("Le fichier ne contient aucun prompt valide.")
        self.set_prompts(normalized)
        return len(normalized)

    def reset_to_defaults(self) -> None:
        self.settings.clear()
        self._initialize_settings()

    def sync(self) -> None:
        self.settings.sync()
