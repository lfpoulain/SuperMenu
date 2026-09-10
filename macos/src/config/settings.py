"""Persistent settings for the macOS application composition."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from PySide6.QtCore import QSettings
from supermenu_core.audio.settings import SpeechSettingsMixin
from supermenu_core.config.voice_prompts import VoicePromptSettingsMixin
from supermenu_core.config.prompt_transfer import export_prompt_bundle, import_prompt_bundle

from supermenu_core.api.model_capabilities import normalize_reasoning_option
from supermenu_core.config.prompts import (
    default_text_prompts,
    normalize_prompt_collection,
)
from supermenu_core.config.provider_settings import normalize_update_channel
from src.config.build_info import BUILD_CHANNEL
from supermenu_core.config.openai_models import (
    DEFAULT_OPENAI_MODEL,
    get_default_reasoning_effort_for_model,
    normalize_openai_model,
    normalize_reasoning_effort,
)
from src.utils.logger import log
from src.utils.paths import settings_file


API_KEY_SETTING = "openai_api_key"
CUSTOM_ENDPOINT_API_KEY_SETTING = "custom_endpoint_api_key"


_normalize_update_channel = normalize_update_channel


def _normalize_prompts(value) -> dict[str, dict]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    try:
        return normalize_prompt_collection(value)
    except (TypeError, ValueError):
        return {}


class Settings(SpeechSettingsMixin, VoicePromptSettingsMixin):
    def __init__(self, config_path: str | None = None):
        self.config_path = str(config_path or settings_file())
        Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)
        self.settings = QSettings(self.config_path, QSettings.Format.IniFormat)
        self.default_prompts = default_text_prompts()
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
            API_KEY_SETTING: "",
            CUSTOM_ENDPOINT_API_KEY_SETTING: "",
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
        self.initialize_voice_prompts()
        self.settings.sync()
        self._secure_config_file()

    def get_api_key(self) -> str:
        return str(self.settings.value(API_KEY_SETTING, "") or "").strip()

    def set_api_key(self, api_key: str) -> None:
        self.settings.setValue(API_KEY_SETTING, str(api_key or "").strip())

    def get_custom_endpoint_api_key(self) -> str:
        return str(
            self.settings.value(CUSTOM_ENDPOINT_API_KEY_SETTING, "") or ""
        ).strip()

    def set_custom_endpoint_api_key(self, api_key: str) -> None:
        self.settings.setValue(
            CUSTOM_ENDPOINT_API_KEY_SETTING,
            str(api_key or "").strip(),
        )

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
        raw_value = self.settings.value("custom_reasoning_effort", "none")
        value = normalize_reasoning_option(
            raw_value,
            "none",
        )
        if value != raw_value:
            self.settings.setValue("custom_reasoning_effort", value)
        return value

    def set_custom_reasoning_effort(self, effort) -> None:
        normalized = normalize_reasoning_option(effort, "none")
        self.settings.setValue("custom_reasoning_effort", normalized)

    def get_reasoning_effort(self) -> str:
        if self.get_ai_provider() == "apple":
            return "none"
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

    def get_ai_provider(self) -> str:
        provider = self.settings.value("ai_provider", "")
        if provider in {"openai", "custom", "apple"}:
            return provider
        # Migrate existing installations without changing their selected provider.
        return "custom" if self.get_use_custom_endpoint() else "openai"

    def set_ai_provider(self, provider: str) -> None:
        if provider not in {"openai", "custom", "apple"}:
            raise ValueError("Fournisseur IA inconnu.")
        self.settings.setValue("ai_provider", provider)
        self.set_use_custom_endpoint(provider == "custom")

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
        export_prompt_bundle(self, file_path)

    def import_prompts(self, file_path: str) -> int:
        return import_prompt_bundle(self, file_path)

    def reset_to_defaults(self) -> None:
        self.settings.clear()
        self._initialize_settings()

    def sync(self) -> None:
        self.settings.sync()
        self._secure_config_file()

    def _secure_config_file(self) -> None:
        try:
            Path(self.config_path).chmod(0o600)
        except OSError as exc:
            log(
                f"Impossible de restreindre les permissions de configuration : {exc}",
                logging.WARNING,
            )
