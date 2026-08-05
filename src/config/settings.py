#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging

import keyring
from PySide6.QtCore import QSettings
from src.config.build_info import BUILD_CHANNEL
from src.config.openai_models import (
    DEFAULT_OPENAI_MODEL,
    get_default_reasoning_effort_for_model,
    normalize_openai_model,
    normalize_reasoning_effort,
)
from src.utils.logger import log

CUSTOM_REASONING_EFFORTS = ["none", "low", "medium", "high"]
OLLAMA_GPT_OSS_THINK_EFFORTS = ["low", "medium", "high"]
UPDATE_CHANNELS = ("stable", "beta")
LEGACY_INSTANT_HOTKEY = "Ctrl+Alt+I"
VOICE_PROMPT_ORDERS = {
    "prompt_transcription_selected",
    "prompt_selected_transcription",
    "transcription_prompt_selected",
    "transcription_selected_prompt",
    "selected_prompt_transcription",
    "selected_transcription_prompt",
}


def _normalize_update_channel(value):
    normalized = str(value or "").strip().lower()
    return normalized if normalized in UPDATE_CHANNELS else "stable"


def _normalize_prompt_collection(
    raw_prompts, *, voice=False, require_non_empty=False
):
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
            raise ValueError(f"La position du prompt '{prompt_id}' doit être un entier.")
        prompt["position"] = position

        insert_default = True if voice else False
        insert_directly = prompt.get("insert_directly", insert_default)
        if not isinstance(insert_directly, bool):
            raise ValueError(
                f"Le champ 'insert_directly' du prompt '{prompt_id}' doit être booléen."
            )
        prompt["insert_directly"] = insert_directly

        if voice:
            include_selected = prompt.get("include_selected_text", False)
            if not isinstance(include_selected, bool):
                raise ValueError(
                    f"Le champ 'include_selected_text' du prompt '{prompt_id}' doit être booléen."
                )
            prompt["include_selected_text"] = include_selected

            prompt_order = prompt.get(
                "prompt_order", "prompt_transcription_selected"
            )
            if prompt_order not in VOICE_PROMPT_ORDERS:
                raise ValueError(
                    f"L'ordre des éléments du prompt '{prompt_id}' est invalide."
                )
            prompt["prompt_order"] = prompt_order
        else:
            legacy_instant = prompt.pop("instant_hotkey", False)
            if not isinstance(legacy_instant, bool):
                raise ValueError(
                    f"Le champ 'instant_hotkey' du prompt '{prompt_id}' doit être booléen."
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


class Settings:
    """Manage application settings"""
    
    def __init__(self):
        # Utiliser un fichier INI dans le dossier utilisateur au lieu du registre Windows
        # Cela rend l'application plus portable et évite les problèmes d'accès au registre
        self.settings = QSettings(os.path.join(os.path.expanduser("~"), "SuperMenu.ini"), QSettings.Format.IniFormat)
        self.default_prompts = {
            "corriger": {
                "name": "Corriger",
                "prompt": "Envoi directement le résultat : Corrige l'orthographe, la grammaire et la conjugaison de ce texte. Conserve le ton, le style et le formatage :",
                "status": "En cours de correction...",
                "insert_directly": False,
                "position": 10
            },
            "corrections_montage": {
                "name": "Corrections Montage",
                "prompt": "Envoi directement le résultat : Corrige l'orthographe, la grammaire et la conjugaison de ce texte, sans me parler, en tenant compte du contexte spécifique : il s'agit de phrases ou de mots qui seront affichés en surimpression sur des vidéos YouTube majoritairement en rapport avec l'électronique, le DIY, le Bricolage, la domotique et l'impression 3D. Parfois, un seul mot peut être employé donc utilise le contexte pour le corriger. Conserve le ton, le style et le formatage :",
                "status": "En cours de correction pour montage...",
                "insert_directly": False,
                "position": 20
            },
            "reformuler": {
                "name": "Reformuler",
                "prompt": "Envoi directement le résultat : Reformule le texte ou le paragraphe suivant pour assurer la clarté, la concision et un flux naturel. La révision doit préserver le ton, le style et le formatage du texte original :",
                "status": "En cours de reformulation...",
                "insert_directly": False,
                "position": 30
            },
            "resumer": {
                "name": "Résumer",
                "prompt": "Résume ce qui suit tout en conservant l'intégralité des informations importantes et pertinentes :",
                "status": "En cours de résumé...",
                "insert_directly": False,
                "position": 40
            },
            "expliquer": {
                "name": "Expliquer",
                "prompt": "Explique ce qui suit :",
                "status": "En cours d'explication...",
                "insert_directly": False,
                "position": 50
            },
            "extraire_passages_importants": {
                "name": "Extraire Passages Importants",
                "prompt": "Voici un texte issu d'une vidéo YouTube en cours de montage en rapport avec l'électronique, le DIY, le Bricolage, la domotique ou l'impression 3D. Extrait de ce texte une liste chronologiquement logique des passages importants à inclure dans le montage de la vidéo. Pour chaque passage, explique en une phrase pourquoi il est pertinent. Voici le texte de la vidéo :",
                "status": "Extraction des passages importants en cours...",
                "insert_directly": False,
                "position": 60
            },
            "developper": {
                "name": "Développer",
                "prompt": "En considérant le ton, le style et le formatage original, aide-moi à exprimer l'idée suivante de manière plus claire et plus articulée. Le style du message peut être formel, informel, décontracté, empathique, assertif ou persuasif, selon le contexte du message original. Il n'y a pas de longueur minimale ou maximale définie. Voici ce que j'essaie de dire :",
                "status": "En cours de développement...",
                "insert_directly": False,
                "position": 70
            },
            "generer_reponse": {
                "name": "Générer une réponse",
                "prompt": "Rédige une réponse à tout message donné. La réponse doit respecter le ton, le style, le formatage et le contexte culturel ou régional de l'expéditeur initial. Maintiens le même niveau de formalité et de ton émotionnel que le message original. Les réponses peuvent avoir n'importe quelle longueur, à condition qu'elles communiquent efficacement la réponse à l'expéditeur initial :",
                "status": "En cours de génération de réponse...",
                "insert_directly": False,
                "position": 80
            },
            "trouver_actions": {
                "name": "Trouver les actions à faire",
                "prompt": "Trouve les actions à faire et présente-les dans une liste :",
                "status": "En cours de recherche des actions à faire...",
                "insert_directly": False,
                "position": 90
            },
            "traduire_en_anglais": {
                "name": "Traduire en anglais",
                "prompt": "Génère une traduction en anglais du texte suivant, en veillant à ce que la traduction transmette avec précision le sens ou l'idée voulue. La traduction doit préserver le ton, le style et le formatage du texte original :",
                "status": "En cours de traduction en anglais...",
                "insert_directly": False,
                "position": 100
            },
            "traduire_en_francais": {
                "name": "Traduire en français",
                "prompt": "Génère une traduction en français du texte suivant, en veillant à ce que la traduction transmette avec précision le sens ou l'idée voulue. La traduction doit préserver le ton, le style et le formatage du texte original :",
                "status": "En cours de traduction en français...",
                "insert_directly": False,
                "position": 110
            }
        }
        for default_prompt in self.default_prompts.values():
            default_prompt.setdefault("hotkey", "")
        
        # Prompts vocaux par défaut
        self.default_voice_prompts = {
            "decrire_reponse": {
                "name": "Décrire une réponse",
                "prompt": "Analyse et décris en détail ce qui suit, en fournissant un contexte pertinent et des explications claires :",
                "status": "Analyse de la réponse vocale en cours...",
                "insert_directly": True,
                "position": 10,
                "include_selected_text": False,
                "prompt_order": "prompt_transcription_selected"  # Ordre par défaut: prompt, transcription, texte sélectionné
            },
            "resumer_vocal": {
                "name": "Résumer",
                "prompt": "Résume ce qui suit tout en conservant l'intégralité des informations importantes et pertinentes :",
                "status": "Résumé de la réponse vocale en cours...",
                "insert_directly": True,
                "position": 20,
                "include_selected_text": False,
                "prompt_order": "prompt_transcription_selected"
            },
            "traduire_en_anglais_vocal": {
                "name": "Traduire en anglais",
                "prompt": "Génère une traduction en anglais du texte suivant, en veillant à ce que la traduction transmette avec précision le sens ou l'idée voulue :",
                "status": "Traduction en anglais en cours...",
                "insert_directly": True,
                "position": 30,
                "include_selected_text": False,
                "prompt_order": "prompt_transcription_selected"
            }
        }
        
        self.default_hotkey = "Ctrl+²"
        self.default_screenshot_hotkey = "Ctrl+Alt+&"
        self.default_voice_hotkey = "Ctrl+Alt+²"
        self.default_custom_hotkey = "Ctrl+Alt+M"
        self.default_screenshot_capture_mode = "fullscreen"
        self.default_custom_endpoint_type = "ollama"
        self.default_model = DEFAULT_OPENAI_MODEL
        self.default_reasoning_effort = get_default_reasoning_effort_for_model(
            self.default_model
        )
        self.default_custom_reasoning_effort = "none"
        self.default_custom_endpoint = ""
        self.default_custom_model = ""
        self.default_use_custom_endpoint = False
        self.default_microphone_index = -1
        self.default_transcription_languages = "fr"
        self.default_transcription_prompt = ""
        self.default_transcription_keywords = ""
        self.default_theme = "dark"
        self.available_themes = ["dark", "light", "auto"]  # Thèmes modernes avec pyqtdarktheme
        self.default_update_channel = _normalize_update_channel(BUILD_CHANNEL)
        
        # Initialize settings if they don't exist
        self._initialize_settings()
    
    def _initialize_settings(self):
        """Initialize default settings if they don't exist"""
        if not self.settings.contains("hotkey"):
            self.settings.setValue("hotkey", self.default_hotkey)  # Raccourci par défaut
        
        if not self.settings.contains("screenshot_hotkey"):
            self.settings.setValue("screenshot_hotkey", self.default_screenshot_hotkey)  # Raccourci de capture d'écran par défaut

        if not self.settings.contains("screenshot_capture_mode"):
            self.settings.setValue("screenshot_capture_mode", self.default_screenshot_capture_mode)

        # L'ancien sélecteur Qt/Win32 ne pilotait pas le menu contextuel et
        # ajoutait des stratégies d'ouverture divergentes. La fenêtre de
        # réponse utilise désormais une stratégie hybride unique.
        if self.settings.contains("response_window_open_mode"):
            self.settings.remove("response_window_open_mode")
        
        if not self.settings.contains("theme"):
            self.settings.setValue("theme", self.default_theme)  # Default theme

        if not self.settings.contains("update_channel"):
            self.settings.setValue(
                "update_channel",
                self.default_update_channel,
            )
        
        if not self.settings.contains("prompts"):
            self.settings.setValue("prompts", json.dumps(self.default_prompts))
        self._migrate_legacy_instant_hotkey()
        
        if not self.settings.contains("voice_prompts"):
            self.settings.setValue("voice_prompts", json.dumps(self.default_voice_prompts))
        
        if not self.settings.contains("model"):
            self.settings.setValue("model", self.default_model)  # Default model
        else:
            self.get_model()

        legacy_reasoning_effort = (
            self.settings.value("reasoning_effort")
            if self.settings.contains("reasoning_effort")
            else None
        )
        if not self.settings.contains("openai_reasoning_effort"):
            initial_effort = (
                legacy_reasoning_effort
                if legacy_reasoning_effort is not None
                else get_default_reasoning_effort_for_model(self.get_model())
            )
            self.set_openai_reasoning_effort(initial_effort)

        if not self.settings.contains("custom_reasoning_effort"):
            initial_custom_effort = (
                legacy_reasoning_effort
                if legacy_reasoning_effort in CUSTOM_REASONING_EFFORTS
                else self.default_custom_reasoning_effort
            )
            self.set_custom_reasoning_effort(initial_custom_effort)
            
        if not self.settings.contains("custom_endpoint"):
            self.settings.setValue("custom_endpoint", self.default_custom_endpoint)

        if not self.settings.contains("custom_endpoint_type"):
            self.settings.setValue("custom_endpoint_type", self.default_custom_endpoint_type)
            
        if not self.settings.contains("custom_model"):
            self.settings.setValue("custom_model", self.default_custom_model)
            
        if not self.settings.contains("use_custom_endpoint"):
            self.settings.setValue("use_custom_endpoint", self.default_use_custom_endpoint)
            
        if not self.settings.contains("microphone_index"):
            self.settings.setValue("microphone_index", self.default_microphone_index)  # -1 = utiliser le microphone par défaut

        if not self.settings.contains("transcription_languages"):
            self.settings.setValue(
                "transcription_languages",
                self.default_transcription_languages,
            )

        if not self.settings.contains("transcription_prompt"):
            self.settings.setValue(
                "transcription_prompt",
                self.default_transcription_prompt,
            )

        if not self.settings.contains("transcription_keywords"):
            self.settings.setValue(
                "transcription_keywords",
                self.default_transcription_keywords,
            )
            
        if not self.settings.contains("voice_hotkey"):
            self.settings.setValue("voice_hotkey", self.default_voice_hotkey)  # Raccourci vocal par défaut

        if not self.settings.contains("custom_hotkey"):
            self.settings.setValue("custom_hotkey", self.default_custom_hotkey)  # Raccourci du mode personnalisé

    def _migrate_legacy_instant_hotkey(self):
        """Move the former single instant hotkey onto its assigned prompt."""
        try:
            raw_prompts = json.loads(self.settings.value("prompts", "{}"))
            if not isinstance(raw_prompts, dict):
                return

            legacy_hotkey = self.settings.value(
                "instant_hotkey",
                LEGACY_INSTANT_HOTKEY,
            )
            changed = False
            for prompt in raw_prompts.values():
                if not isinstance(prompt, dict):
                    continue
                had_legacy_field = "instant_hotkey" in prompt
                legacy_enabled = prompt.pop("instant_hotkey", False)
                if legacy_enabled and not prompt.get("hotkey"):
                    prompt["hotkey"] = str(legacy_hotkey or LEGACY_INSTANT_HOTKEY)
                    changed = True
                if "hotkey" not in prompt:
                    prompt["hotkey"] = ""
                    changed = True
                changed = changed or had_legacy_field

            if changed:
                self.settings.setValue("prompts", json.dumps(raw_prompts))
            if self.settings.contains("instant_hotkey"):
                self.settings.remove("instant_hotkey")
            self.settings.sync()
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            log(f"Migration du raccourci instantané impossible: {e}", logging.WARNING)
    
    def get_api_key(self):
        """Get the OpenAI API key"""
        try:
            return keyring.get_password("SuperMenu", "openai_api_key")
        except Exception as e:
            log(f"Error retrieving API key from keyring: {e}", logging.WARNING)
            return ""
    
    def set_api_key(self, api_key):
        """Set the OpenAI API key"""
        keyring.set_password("SuperMenu", "openai_api_key", api_key)
    
    def get_model(self):
        """Get the OpenAI model"""
        saved_model = self.settings.value("model")
        model = normalize_openai_model(saved_model)
        if model != saved_model:
            self.set_model(model)
        return model
    
    def set_model(self, model):
        """Set the OpenAI model"""
        self.settings.setValue("model", normalize_openai_model(model))

    def get_openai_reasoning_effort(self, model=None):
        """Get and validate the OpenAI effort independently of local providers."""
        model = normalize_openai_model(model or self.get_model())
        default = get_default_reasoning_effort_for_model(model)
        effort = self.settings.value("openai_reasoning_effort", default)
        normalized = normalize_reasoning_effort(model, effort)
        if normalized != effort:
            self.settings.setValue("openai_reasoning_effort", normalized)
        return normalized

    def set_openai_reasoning_effort(self, effort, model=None):
        """Persist an effort supported by the selected OpenAI model."""
        model = normalize_openai_model(model or self.get_model())
        normalized = normalize_reasoning_effort(model, effort)
        self.settings.setValue("openai_reasoning_effort", normalized)

    def get_custom_reasoning_effort(self):
        """Get the local-provider think effort without touching OpenAI settings."""
        effort = self.settings.value(
            "custom_reasoning_effort",
            self.default_custom_reasoning_effort,
        )
        if effort not in CUSTOM_REASONING_EFFORTS:
            effort = self.default_custom_reasoning_effort
            self.settings.setValue("custom_reasoning_effort", effort)
        return effort

    def set_custom_reasoning_effort(self, effort):
        """Persist the local-provider think effort independently."""
        normalized = (
            effort
            if effort in CUSTOM_REASONING_EFFORTS
            else self.default_custom_reasoning_effort
        )
        self.settings.setValue("custom_reasoning_effort", normalized)

    def get_reasoning_effort(self):
        """Get the effort for the active provider."""
        if self.get_use_custom_endpoint():
            return self.get_custom_reasoning_effort()
        return self.get_openai_reasoning_effort()

    def set_reasoning_effort(self, effort):
        """Set the effort for the active provider."""
        if self.get_use_custom_endpoint():
            self.set_custom_reasoning_effort(effort)
        else:
            self.set_openai_reasoning_effort(effort)

    def sync(self):
        """Force l'écriture des paramètres persistés."""
        self.settings.sync()
    
    def get_custom_endpoint(self):
        """Get the custom endpoint URL"""
        return self.settings.value("custom_endpoint", self.default_custom_endpoint)
    
    def set_custom_endpoint(self, endpoint):
        """Set the custom endpoint URL"""
        self.settings.setValue("custom_endpoint", endpoint)

    def get_custom_endpoint_type(self):
        """Get the custom endpoint type (ollama or lmstudio)"""
        endpoint_type = self.settings.value("custom_endpoint_type", "")
        if isinstance(endpoint_type, str):
            endpoint_type = endpoint_type.strip().lower()
        else:
            endpoint_type = ""

        if endpoint_type in ("ollama", "lmstudio"):
            return endpoint_type
        return self.default_custom_endpoint_type

    def set_custom_endpoint_type(self, endpoint_type):
        """Set the custom endpoint type"""
        endpoint_type = (endpoint_type or "").strip().lower()
        if endpoint_type not in ("ollama", "lmstudio"):
            endpoint_type = self.default_custom_endpoint_type
        self.settings.setValue("custom_endpoint_type", endpoint_type)
    
    def get_custom_model(self):
        """Get the custom model name"""
        return self.settings.value("custom_model", self.default_custom_model)
    
    def set_custom_model(self, model):
        """Set the custom model name"""
        self.settings.setValue("custom_model", model)
    
    def get_use_custom_endpoint(self):
        """Get whether to use custom endpoint"""
        use_custom = self.settings.value("use_custom_endpoint", self.default_use_custom_endpoint)
        # Convertir en booléen si c'est une chaîne
        if isinstance(use_custom, str):
            return use_custom.lower() == 'true'
        return bool(use_custom)
    
    def set_use_custom_endpoint(self, use_custom):
        """Set whether to use custom endpoint"""
        self.settings.setValue("use_custom_endpoint", bool(use_custom))
        
    def get_microphone_index(self):
        """Get the selected microphone index"""
        index = self.settings.value("microphone_index", self.default_microphone_index)
        try:
            index = int(index)
        except (ValueError, TypeError) as e:
            log(f"Invalid microphone index, using default: {e}", logging.WARNING)
            index = self.default_microphone_index
        return index if index >= 0 else None
    
    def set_microphone_index(self, index):
        """Set the microphone index"""
        self.settings.setValue("microphone_index", index if index is not None else -1)

    def get_hotkey(self):
        """Get the hotkey"""
        return self.settings.value("hotkey", self.default_hotkey)
    
    def set_hotkey(self, hotkey):
        """Set the hotkey"""
        self.settings.setValue("hotkey", hotkey)

    def get_screenshot_hotkey(self):
        """Get the screenshot hotkey"""
        return self.settings.value("screenshot_hotkey", self.default_screenshot_hotkey)
    
    def set_screenshot_hotkey(self, hotkey):
        """Set the screenshot hotkey"""
        self.settings.setValue("screenshot_hotkey", hotkey)

    def get_screenshot_capture_mode(self):
        mode = self.settings.value("screenshot_capture_mode", self.default_screenshot_capture_mode)
        if mode not in ("fullscreen", "region", "ask"):
            return self.default_screenshot_capture_mode
        return mode

    def set_screenshot_capture_mode(self, mode):
        if mode not in ("fullscreen", "region", "ask"):
            return
        self.settings.setValue("screenshot_capture_mode", mode)

    def get_transcription_languages(self):
        """Return expected language codes; an empty value enables detection."""
        value = self.settings.value(
            "transcription_languages",
            self.default_transcription_languages,
        )
        return str(value or "").strip()

    def set_transcription_languages(self, languages):
        self.settings.setValue(
            "transcription_languages",
            str(languages or "").strip(),
        )

    def get_transcription_prompt(self):
        """Return optional recording context sent to GPT Transcribe."""
        value = self.settings.value(
            "transcription_prompt",
            self.default_transcription_prompt,
        )
        return str(value or "").strip()

    def set_transcription_prompt(self, prompt):
        self.settings.setValue(
            "transcription_prompt",
            str(prompt or "").strip(),
        )

    def get_transcription_keywords(self):
        """Return comma/newline-separated literal vocabulary hints."""
        value = self.settings.value(
            "transcription_keywords",
            self.default_transcription_keywords,
        )
        return str(value or "").strip()

    def set_transcription_keywords(self, keywords):
        self.settings.setValue(
            "transcription_keywords",
            str(keywords or "").strip(),
        )
    
    def get_voice_hotkey(self):
        """Get the voice hotkey"""
        return self.settings.value("voice_hotkey", self.default_voice_hotkey)
    
    def set_voice_hotkey(self, hotkey):
        """Set the voice hotkey"""
        self.settings.setValue("voice_hotkey", hotkey)

    def get_custom_hotkey(self):
        """Get the custom mode hotkey"""
        return self.settings.value("custom_hotkey", self.default_custom_hotkey)

    def set_custom_hotkey(self, hotkey):
        """Set the custom mode hotkey"""
        self.settings.setValue("custom_hotkey", hotkey)

    def get_last_update_check_date(self):
        """Get the last automatic update check date as YYYY-MM-DD."""
        return self.settings.value("last_update_check_date", "")

    def set_last_update_check_date(self, date_value):
        """Set the last automatic update check date as YYYY-MM-DD."""
        self.settings.setValue("last_update_check_date", date_value or "")

    def get_update_channel(self):
        """Return the selected update channel, defaulting safely to stable."""
        channel = _normalize_update_channel(
            self.settings.value(
                "update_channel",
                self.default_update_channel,
            )
        )
        if channel != self.settings.value("update_channel"):
            self.settings.setValue("update_channel", channel)
        return channel

    def set_update_channel(self, channel):
        """Persist a validated stable or beta update channel."""
        self.settings.setValue(
            "update_channel",
            _normalize_update_channel(channel),
        )
    
    def get_theme(self):
        """Get the configured theme"""
        return self.settings.value("theme", self.default_theme)
    
    def set_theme(self, theme):
        """Set the theme"""
        if theme in self.available_themes:
            self.settings.setValue("theme", theme)
        else:
            log("Le thème spécifié n'est pas disponible.", logging.WARNING)
    
    def get_prompts(self):
        """Get all prompts"""
        prompts_json = self.settings.value("prompts", "{}")
        try:
            raw_prompts = json.loads(prompts_json)
            prompts = _normalize_prompt_collection(raw_prompts)
            if prompts != raw_prompts:
                self.set_prompts(prompts)
            return prompts
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            log(f"Configuration de prompts invalide: {e}", logging.ERROR)
            return {}
    
    def get_prompt(self, prompt_id):
        """Get a specific prompt"""
        prompts = self.get_prompts()
        prompt = prompts.get(prompt_id)
        
        # Assurer la compatibilité avec les anciens prompts
        if prompt:
            if "position" not in prompt:
                prompt["position"] = 999
            if "insert_directly" not in prompt:
                prompt["insert_directly"] = False
            if "hotkey" not in prompt:
                prompt["hotkey"] = ""
        
        return prompt
    
    def get_voice_prompts(self):
        """Get all voice prompts"""
        prompts_json = self.settings.value("voice_prompts", "{}")
        try:
            raw_prompts = json.loads(prompts_json)
            prompts = _normalize_prompt_collection(raw_prompts, voice=True)
            if prompts != raw_prompts:
                self.set_voice_prompts(prompts)
            return prompts
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            log(f"Configuration de prompts vocaux invalide: {e}", logging.ERROR)
            return {}
    
    def get_voice_prompt(self, prompt_id):
        """Get a specific voice prompt"""
        prompts = self.get_voice_prompts()
        prompt = prompts.get(prompt_id)
        
        # Assurer la compatibilité avec les anciens prompts vocaux
        if prompt:
            if "position" not in prompt:
                prompt["position"] = 999
            if "insert_directly" not in prompt:
                prompt["insert_directly"] = True
            if "include_selected_text" not in prompt:
                prompt["include_selected_text"] = False
            if "prompt_order" not in prompt:
                prompt["prompt_order"] = "prompt_transcription_selected"
            if "status" not in prompt:
                prompt["status"] = "Traitement en cours..."
        
        return prompt
    
    def set_prompts(self, prompts):
        """Set all prompts"""
        self.settings.setValue("prompts", json.dumps(prompts))
    
    def update_prompt(
        self,
        prompt_id,
        name,
        prompt,
        status,
        insert_directly=False,
        position=None,
        hotkey="",
    ):
        """Update a specific prompt"""
        prompts = self.get_prompts()
        
        # Si aucune position n'est fournie, conserver la position existante ou utiliser une valeur par défaut
        if position is None:
            position = prompts.get(prompt_id, {}).get("position", 999)
            
        normalized_hotkey = str(hotkey or "").strip()
        for existing_id, existing_prompt in prompts.items():
            if (
                existing_id != prompt_id
                and normalized_hotkey
                and str(existing_prompt.get("hotkey", "")).strip().casefold()
                == normalized_hotkey.casefold()
            ):
                raise ValueError(
                    f"Le raccourci '{normalized_hotkey}' est déjà utilisé par "
                    f"le prompt '{existing_prompt.get('name', existing_id)}'."
                )

        prompts[prompt_id] = {
            "name": name,
            "prompt": prompt,
            "status": status,
            "insert_directly": insert_directly,
            "position": position,
            "hotkey": normalized_hotkey,
        }
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
    ):
        """Ajouter un nouveau prompt"""
        prompts = self.get_prompts()
        
        # Vérifier si l'ID existe déjà
        if prompt_id in prompts:
            # Générer un nouvel ID unique
            base_id = prompt_id
            counter = 1
            while f"{base_id}_{counter}" in prompts:
                counter += 1
            prompt_id = f"{base_id}_{counter}"
        
        # Ajouter le nouveau prompt
        normalized_hotkey = str(hotkey or "").strip()
        for existing_id, existing_prompt in prompts.items():
            if (
                normalized_hotkey
                and str(existing_prompt.get("hotkey", "")).strip().casefold()
                == normalized_hotkey.casefold()
            ):
                raise ValueError(
                    f"Le raccourci '{normalized_hotkey}' est déjà utilisé par "
                    f"le prompt '{existing_prompt.get('name', existing_id)}'."
                )

        prompts[prompt_id] = {
            "name": name,
            "prompt": prompt,
            "status": status,
            "insert_directly": insert_directly,
            "position": position,
            "hotkey": normalized_hotkey,
        }
        
        self.set_prompts(prompts)
        return prompt_id
    
    def delete_prompt(self, prompt_id):
        """Supprimer un prompt"""
        prompts = self.get_prompts()
        
        # Vérifier si le prompt existe
        if prompt_id in prompts:
            del prompts[prompt_id]
            self.set_prompts(prompts)
            return True
        
        return False
    
    def set_voice_prompts(self, prompts):
        """Set all voice prompts"""
        self.settings.setValue("voice_prompts", json.dumps(prompts))
        self.settings.sync() # Assurer que les modifications sont écrites immédiatement

    def update_voice_prompt(self, prompt_id, name, prompt, status, insert_directly=False, position=None, include_selected_text=False, prompt_order="prompt_transcription_selected"):
        """Update a specific voice prompt"""
        voice_prompts = self.get_voice_prompts()
        
        # Si aucune position n'est fournie, conserver la position existante ou utiliser une valeur par défaut
        if position is None:
            position = voice_prompts.get(prompt_id, {}).get("position", 999)
            
        voice_prompts[prompt_id] = {
            "name": name,
            "prompt": prompt,
            "status": status,
            "insert_directly": insert_directly,
            "position": position,
            "include_selected_text": include_selected_text,
            "prompt_order": prompt_order
        }
        self.set_voice_prompts(voice_prompts)
    
    def add_voice_prompt(self, prompt_id, name, prompt, status, insert_directly=False, position=999, include_selected_text=False, prompt_order="prompt_transcription_selected"):
        """Add a new voice prompt"""
        voice_prompts = self.get_voice_prompts()
        
        # Vérifier si l'ID existe déjà
        if prompt_id in voice_prompts:
            # Générer un nouvel ID unique
            base_id = prompt_id
            counter = 1
            while f"{base_id}_{counter}" in voice_prompts:
                counter += 1
            prompt_id = f"{base_id}_{counter}"
        
        # Ajouter le nouveau prompt
        voice_prompts[prompt_id] = {
            "name": name,
            "prompt": prompt,
            "status": status,
            "insert_directly": insert_directly,
            "position": position,
            "include_selected_text": include_selected_text,
            "prompt_order": prompt_order
        }
        
        self.set_voice_prompts(voice_prompts)
        return prompt_id
    
    def delete_voice_prompt(self, prompt_id):
        """Supprimer un prompt vocal"""
        voice_prompts = self.get_voice_prompts()
        
        # Vérifier si le prompt existe
        if prompt_id in voice_prompts:
            del voice_prompts[prompt_id]
            self.set_voice_prompts(voice_prompts)
            return True
        
        return False
    
    def export_prompts(self, file_path):
        """Export text and voice prompts to a JSON file."""
        try:
            prompts_to_export = {
                "text_prompts": self.get_prompts(),
                "voice_prompts": self.get_voice_prompts()
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(prompts_to_export, f, indent=4, ensure_ascii=False)
            return True, "Prompts exportés avec succès."
        except Exception as e:
            return False, f"Erreur lors de l'exportation des prompts: {e}"

    def import_prompts(self, file_path):
        """Import text and voice prompts from a JSON file, replacing existing ones."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_data = json.load(f)

            if not isinstance(imported_data, dict):
                raise ValueError("La racine du fichier doit être un objet JSON.")

            # Validate both collections before changing either persisted value.
            text_prompts = _normalize_prompt_collection(
                imported_data.get("text_prompts", {}),
                require_non_empty=True,
            )
            voice_prompts = _normalize_prompt_collection(
                imported_data.get("voice_prompts", {}),
                voice=True,
                require_non_empty=True,
            )

            old_text = self.settings.value("prompts", "{}")
            old_voice = self.settings.value("voice_prompts", "{}")
            try:
                self.settings.setValue("prompts", json.dumps(text_prompts))
                self.settings.setValue("voice_prompts", json.dumps(voice_prompts))
                self.settings.sync()
            except Exception:
                self.settings.setValue("prompts", old_text)
                self.settings.setValue("voice_prompts", old_voice)
                self.settings.sync()
                raise

            return True, "Prompts importés avec succès."
        except FileNotFoundError:
            return False, "Fichier d'importation non trouvé."
        except json.JSONDecodeError:
            return False, "Erreur de décodage du fichier JSON. Le format est peut-être incorrect."
        except ValueError as e:
            return False, f"Format de prompts invalide: {e}"
        except Exception as e:
            return False, f"Erreur lors de l'importation des prompts: {e}"

    def reset_to_defaults(self):
        """Reset all settings to defaults"""
        self.set_hotkey(self.default_hotkey)
        self.set_screenshot_hotkey(self.default_screenshot_hotkey)
        self.set_voice_hotkey(self.default_voice_hotkey)
        self.set_custom_hotkey(self.default_custom_hotkey)
        self.set_screenshot_capture_mode(self.default_screenshot_capture_mode)
        self.set_theme(self.default_theme)
        self.set_update_channel(self.default_update_channel)
        self.set_last_update_check_date("")
        self.set_prompts(self.default_prompts)
        self.set_voice_prompts(self.default_voice_prompts)
        self.set_model(self.default_model)
        self.set_openai_reasoning_effort(self.default_reasoning_effort)
        self.set_custom_reasoning_effort(self.default_custom_reasoning_effort)
        self.set_custom_endpoint_type(self.default_custom_endpoint_type)
        self.set_custom_endpoint(self.default_custom_endpoint)
        self.set_custom_model(self.default_custom_model)
        self.set_use_custom_endpoint(self.default_use_custom_endpoint)
        self.set_microphone_index(self.default_microphone_index)
        self.set_transcription_languages(
            self.default_transcription_languages
        )
        self.set_transcription_prompt(self.default_transcription_prompt)
        self.set_transcription_keywords(
            self.default_transcription_keywords
        )
        self.settings.sync()
