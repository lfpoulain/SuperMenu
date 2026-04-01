#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
import keyring
from PySide6.QtCore import QSettings
from src.utils.logger import log

# Constantes pour les modèles OpenAI
AVAILABLE_MODELS = ["gpt-5.4", "gpt-5.4-nano", "gpt-5.4-mini", "gpt-5.2", "gpt-5-mini", "gpt-4.1-mini"]
GPT5_MODELS_PREFIX = "gpt-5"  # Préfixe pour les modèles nécessitant max_completion_tokens
REASONING_EFFORTS = ["none", "low", "medium", "high"]
REASONING_MODELS = {"gpt-5.4", "gpt-5.4-nano", "gpt-5.4-mini", "gpt-5.2", "gpt-5-mini"}
REASONING_MODELS_NO_NONE = {"gpt-5.4-nano"}


def is_gpt5_model(model_name: str) -> bool:
    """Vérifie si le modèle est un modèle GPT-5 nécessitant des paramètres spécifiques.
    
    Args:
        model_name: Nom du modèle à vérifier
        
    Returns:
        True si c'est un modèle GPT-5, False sinon
    """
    return GPT5_MODELS_PREFIX in model_name.lower() if model_name else False


def supports_reasoning(model_name: str) -> bool:
    """Vérifie si le modèle supporte le paramètre reasoning_effort."""
    if not model_name:
        return False
    return model_name.lower() in REASONING_MODELS


def get_reasoning_efforts_for_model(model_name: str):
    """Retourne la liste des efforts de raisonnement autorisés pour un modèle."""
    if not supports_reasoning(model_name):
        return []
    if model_name.lower() in REASONING_MODELS_NO_NONE:
        return [effort for effort in REASONING_EFFORTS if effort != "none"]
    return list(REASONING_EFFORTS)


def normalize_reasoning_effort(model_name: str, effort: str) -> str:
    """Normalise l'effort de raisonnement selon le modèle."""
    if not supports_reasoning(model_name):
        return "none"
    effort = (effort or "").strip().lower()
    allowed = get_reasoning_efforts_for_model(model_name)
    if effort in allowed:
        return effort
    return "low" if "low" in allowed else allowed[0]


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
        self.default_model = "gpt-5.2"
        self.default_reasoning_effort = "none"
        self.default_custom_endpoint = ""
        self.default_custom_model = ""
        self.default_use_custom_endpoint = False
        self.default_microphone_index = -1
        self.default_describe_response_prompt = "Analyse et décris en détail ce qui suit, en fournissant un contexte pertinent et des explications claires :"
        self.default_theme = "dark"
        self.available_themes = ["dark", "light", "auto"]  # Thèmes modernes avec pyqtdarktheme
        
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
        
        if not self.settings.contains("theme"):
            self.settings.setValue("theme", self.default_theme)  # Default theme
        
        if not self.settings.contains("prompts"):
            self.settings.setValue("prompts", json.dumps(self.default_prompts))
        
        if not self.settings.contains("voice_prompts"):
            self.settings.setValue("voice_prompts", json.dumps(self.default_voice_prompts))
        
        if not self.settings.contains("model"):
            self.settings.setValue("model", self.default_model)  # Default model

        if not self.settings.contains("reasoning_effort"):
            self.settings.setValue("reasoning_effort", self.default_reasoning_effort)
            
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
            
        if not self.settings.contains("describe_response_prompt"):
            self.settings.setValue("describe_response_prompt", self.default_describe_response_prompt)
        
        if not self.settings.contains("voice_hotkey"):
            self.settings.setValue("voice_hotkey", self.default_voice_hotkey)  # Raccourci vocal par défaut

        if not self.settings.contains("custom_hotkey"):
            self.settings.setValue("custom_hotkey", self.default_custom_hotkey)  # Raccourci du mode personnalisé
    
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
        model = self.settings.value("model")
        if not model or model not in AVAILABLE_MODELS:
            model = self.default_model
            self.set_model(model)
        return model
    
    def set_model(self, model):
        """Set the OpenAI model"""
        self.settings.setValue("model", model)

    def get_reasoning_effort(self):
        """Get the reasoning effort"""
        effort = self.settings.value("reasoning_effort", self.default_reasoning_effort)
        if effort not in REASONING_EFFORTS:
            effort = self.default_reasoning_effort
            self.set_reasoning_effort(effort)
        normalized_effort = normalize_reasoning_effort(self.get_model(), effort)
        if normalized_effort != effort:
            self.set_reasoning_effort(normalized_effort)
        return normalized_effort

    def set_reasoning_effort(self, effort):
        """Set the reasoning effort"""
        normalized_effort = normalize_reasoning_effort(self.get_model(), effort)
        self.settings.setValue("reasoning_effort", normalized_effort)

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
            prompts = json.loads(prompts_json)
            
            # Migration et validation des prompts existants
            for prompt_id, prompt_data in prompts.items():
                # S'assurer que tous les champs nécessaires sont présents
                if "position" not in prompt_data:
                    prompts[prompt_id]["position"] = 999  # Valeur par défaut
                if "insert_directly" not in prompt_data:
                    prompts[prompt_id]["insert_directly"] = False  # Valeur par défaut
            
            # Sauvegarder les prompts mis à jour
            self.set_prompts(prompts)
            
            return prompts
        except json.JSONDecodeError:
            log("Erreur de décodage JSON pour les prompts", logging.ERROR)
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
        
        return prompt
    
    def get_voice_prompts(self):
        """Get all voice prompts"""
        prompts_json = self.settings.value("voice_prompts", "{}")
        try:
            prompts = json.loads(prompts_json)
            
            # Migration et validation des prompts vocaux existants
            for prompt_id, prompt_data in prompts.items():
                # S'assurer que tous les champs nécessaires sont présents
                if "position" not in prompt_data:
                    prompts[prompt_id]["position"] = 999  # Valeur par défaut
                if "insert_directly" not in prompt_data:
                    prompts[prompt_id]["insert_directly"] = True  # Valeur par défaut pour les prompts vocaux
                if "include_selected_text" not in prompt_data:
                    prompts[prompt_id]["include_selected_text"] = False  # Valeur par défaut
                if "prompt_order" not in prompt_data:
                    prompts[prompt_id]["prompt_order"] = "prompt_transcription_selected"  # Valeur par défaut
                if "status" not in prompt_data:
                    prompts[prompt_id]["status"] = "Traitement en cours..."  # Valeur par défaut
            
            # Sauvegarder les prompts mis à jour
            self.set_voice_prompts(prompts)
            
            return prompts
        except json.JSONDecodeError:
            log("Erreur de décodage JSON pour les prompts vocaux", logging.ERROR)
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
    
    def update_prompt(self, prompt_id, name, prompt, status, insert_directly=False, position=None):
        """Update a specific prompt"""
        prompts = self.get_prompts()
        
        # Si aucune position n'est fournie, conserver la position existante ou utiliser une valeur par défaut
        if position is None:
            position = prompts.get(prompt_id, {}).get("position", 999)
            
        prompts[prompt_id] = {
            "name": name,
            "prompt": prompt,
            "status": status,
            "insert_directly": insert_directly,
            "position": position
        }
        self.set_prompts(prompts)
    
    def add_prompt(self, prompt_id, name, prompt, status, insert_directly=False, position=999):
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
        prompts[prompt_id] = {
            "name": name,
            "prompt": prompt,
            "status": status,
            "insert_directly": insert_directly,
            "position": position
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
    
    def get_describe_response_prompt(self):
        """Get the prompt for describing a response"""
        return self.settings.value("describe_response_prompt", self.default_describe_response_prompt)
    
    def set_describe_response_prompt(self, prompt):
        """Set the prompt for describing a response"""
        self.settings.setValue("describe_response_prompt", prompt)
    
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
            
            if "text_prompts" in imported_data:
                self.set_prompts(imported_data["text_prompts"])
            else:
                # Si les prompts textuels ne sont pas dans le fichier, on peut choisir de les vider
                # ou de les laisser tels quels. Ici, on les vide pour un remplacement complet.
                self.set_prompts({})

            if "voice_prompts" in imported_data:
                self.set_voice_prompts(imported_data["voice_prompts"])
            else:
                self.set_voice_prompts({})
            
            return True, "Prompts importés avec succès."
        except FileNotFoundError:
            return False, "Fichier d'importation non trouvé."
        except json.JSONDecodeError:
            return False, "Erreur de décodage du fichier JSON. Le format est peut-être incorrect."
        except Exception as e:
            return False, f"Erreur lors de l'importation des prompts: {e}"

    def reset_to_defaults(self):
        """Reset all settings to defaults"""
        self.set_hotkey(self.default_hotkey)
        self.set_screenshot_hotkey(self.default_screenshot_hotkey)
        self.set_custom_hotkey(self.default_custom_hotkey)
        self.set_theme(self.default_theme)
        self.set_prompts(self.default_prompts)
        self.set_voice_prompts(self.default_voice_prompts)
        self.set_model(self.default_model)
        self.set_reasoning_effort(self.default_reasoning_effort)
        self.set_custom_endpoint_type(self.default_custom_endpoint_type)
        self.set_custom_endpoint(self.default_custom_endpoint)
        self.set_custom_model(self.default_custom_model)
        self.set_use_custom_endpoint(self.default_use_custom_endpoint)
        self.set_microphone_index(self.default_microphone_index)
        self.set_describe_response_prompt(self.default_describe_response_prompt)
