#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import threading
import os
import base64
import time
import logging
import tempfile
import re
from urllib.parse import urlparse
from PySide6.QtCore import QObject, Signal, QTimer, Slot
from src.utils.logger import log
from src.config.settings import (
    CUSTOM_REASONING_EFFORTS,
    OLLAMA_GPT_OSS_THINK_EFFORTS,
    is_gpt5_model,
    normalize_reasoning_effort,
    supports_reasoning,
)

# Constante pour le timeout des requêtes API
DEFAULT_API_TIMEOUT = 60
DEFAULT_MAX_TOKENS = 2048
THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.IGNORECASE | re.DOTALL)
THINK_TAG_RE = re.compile(r"</?think\b[^>]*>", re.IGNORECASE)
BRACKET_THINK_BLOCK_RE = re.compile(r"\[think\].*?\[/think\]", re.IGNORECASE | re.DOTALL)
BRACKET_THINK_TAG_RE = re.compile(r"\[/?think\]", re.IGNORECASE)


def _looks_like_ollama_endpoint(endpoint_url):
    parsed = urlparse(endpoint_url or "")
    host = (parsed.hostname or "").lower()
    port = parsed.port
    path = (parsed.path or "").lower()
    return port == 11434 or "ollama" in host or path.startswith("/api")


def _models_base_url(endpoint_url, is_ollama):
    base = (endpoint_url or "").rstrip("/")
    if is_ollama:
        if base.endswith("/api/chat"):
            return base[: -len("/api/chat")]
        if base.endswith("/api"):
            return base[: -len("/api")]
        return base

    if base.endswith("/v1/chat/completions"):
        return base[: -len("/v1/chat/completions")]
    if base.endswith("/v1"):
        return base[: -len("/v1")]
    return base


class OpenAIClient(QObject):
    """Client for OpenAI API interactions"""
    
    # Signals publics
    request_started = Signal()
    request_finished = Signal(str)
    request_error = Signal(str)
    
    # Signaux internes pour communication inter-threads (thread-safe)
    _internal_finished = Signal(str)
    _internal_error = Signal(str)
    
    def __init__(self, settings, api_key=None, model=None, max_retries=3, retry_delay=1.0):
        super().__init__()
        self.api_key = api_key
        self.settings = settings
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Déterminer le modèle à utiliser
        self.use_custom_endpoint = settings.get_use_custom_endpoint()
        self.custom_endpoint = settings.get_custom_endpoint() if self.use_custom_endpoint else None
        self.custom_endpoint_type = settings.get_custom_endpoint_type() if self.use_custom_endpoint else None
        self.use_ollama_api = self.use_custom_endpoint and self.custom_endpoint_type == "ollama"
        self.use_lmstudio_api = self.use_custom_endpoint and self.custom_endpoint_type == "lmstudio"
        
        # Si on utilise un endpoint personnalisé et qu'on a un custom_model dans les settings, l'utiliser
        if self.use_custom_endpoint:
            custom_model = settings.get_custom_model()
            self.model = model if model else (custom_model if custom_model else "llama2")
            if self.use_ollama_api:
                endpoint_kind = "Ollama"
            elif self.use_lmstudio_api:
                endpoint_kind = "LM Studio"
            else:
                endpoint_kind = "personnalisé"
            log(f"OpenAIClient: Utilisation du modèle {endpoint_kind} '{self.model}' avec endpoint {self.custom_endpoint}", logging.INFO)
        else:
            # Sinon utiliser le modèle OpenAI
            self.model = model if model else settings.get_model()
            log(f"OpenAIClient: Utilisation du modèle OpenAI '{self.model}'", logging.INFO)
        
        # Connecter les signaux internes aux méthodes d'émission
        self._internal_finished.connect(self._emit_finished)
        self._internal_error.connect(self._emit_error)
        
        # Configurer l'URL de l'API
        if self.use_custom_endpoint and self.custom_endpoint:
            if self.use_ollama_api:
                self.api_url = self._build_custom_chat_url(self.custom_endpoint, ollama=True)
            else:
                self.api_url = self._build_custom_chat_url(self.custom_endpoint)
        else:
            # Utiliser OpenAI par défaut
            self.api_url = "https://api.openai.com/v1/chat/completions"

    @staticmethod
    def _build_custom_chat_url(endpoint_url, ollama=False):
        """Construit l'URL de chat adaptée au type d'endpoint."""
        base = (endpoint_url or "").rstrip("/")
        if not base:
            return base

        if ollama:
            if base.endswith("/api/chat"):
                return base
            if base.endswith("/api"):
                return f"{base}/chat"
            return f"{base}/api/chat"

        if base.endswith("/v1/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    def _build_ollama_think_value(self):
        """Construit la valeur du paramètre think pour Ollama."""
        effort = (self.settings.get_reasoning_effort() or "none").strip().lower()
        if effort == "none":
            return False

        model_name = (self.model or "").lower()
        if "gpt-oss" in model_name:
            if effort in OLLAMA_GPT_OSS_THINK_EFFORTS:
                return effort
            return "low"

        return True if effort in CUSTOM_REASONING_EFFORTS else False

    @staticmethod
    def _combine_thinking(content, thinking):
        """Combine le raisonnement et la réponse pour l'affichage."""
        parts = []
        if thinking:
            parts.append(f"<think>{thinking}</think>")
        if content:
            parts.append(content)

        if not parts:
            return content or thinking or ""

        return "\n\n".join(parts)

    @staticmethod
    def _strip_inline_thinking(text):
        """Supprime les blocs de raisonnement inclus dans le contenu final."""
        if not isinstance(text, str) or not text:
            return ""

        stripped = THINK_BLOCK_RE.sub("", text)
        stripped = BRACKET_THINK_BLOCK_RE.sub("", stripped)
        stripped = THINK_TAG_RE.sub("", stripped)
        stripped = BRACKET_THINK_TAG_RE.sub("", stripped)
        return stripped.strip()

    @staticmethod
    def _content_to_text(content):
        """Convertit les formats de contenu OpenAI-compatible en texte."""
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(part for part in parts if part)

        return ""

    @staticmethod
    def _reasoning_value_to_text(value):
        """Normalise un champ de raisonnement qui peut etre str, dict ou list."""
        if isinstance(value, str):
            return value.strip()

        if isinstance(value, dict):
            for nested_key in ("text", "content", "summary", "reasoning_content", "value"):
                nested_value = OpenAIClient._reasoning_value_to_text(value.get(nested_key))
                if nested_value:
                    return nested_value
            return ""

        if isinstance(value, list):
            parts = []
            for item in value:
                item_text = OpenAIClient._reasoning_value_to_text(item)
                if item_text:
                    parts.append(item_text)
            return "\n\n".join(parts)

        return ""

    @staticmethod
    def _extract_reasoning_text(response_data):
        """Extrait le texte de raisonnement depuis une réponse OpenAI-compatible."""
        if not isinstance(response_data, dict):
            return ""

        candidates = [response_data]

        choices = response_data.get("choices", [])
        if choices and isinstance(choices[0], dict):
            candidates.append(choices[0])
            message = choices[0].get("message", {})
            if isinstance(message, dict):
                candidates.append(message)

        for item in candidates:
            if not isinstance(item, dict):
                continue

            for key in ("reasoning_content", "reasoning", "thinking"):
                value = OpenAIClient._reasoning_value_to_text(item.get(key))
                if value:
                    return value

        return ""

    def _extract_response_parts(self, response_data):
        """Extrait la reponse finale et le raisonnement expose par le fournisseur."""
        if self.use_ollama_api:
            message = response_data.get("message", {}) if isinstance(response_data, dict) else {}
            content = self._content_to_text(message.get("content", "")) if isinstance(message, dict) else ""
            thinking = self._reasoning_value_to_text(message.get("thinking", "")) if isinstance(message, dict) else ""
            return content, thinking

        if self.use_lmstudio_api:
            choices = response_data.get("choices", []) if isinstance(response_data, dict) else []
            if not choices:
                return "", self._extract_reasoning_text(response_data)

            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            content = self._content_to_text(message.get("content", "")) if isinstance(message, dict) else ""
            reasoning = self._extract_reasoning_text(response_data)
            return content, reasoning

        if isinstance(response_data, dict) and response_data.get("output_text"):
            return self._content_to_text(response_data.get("output_text")), self._extract_reasoning_text(response_data)

        if isinstance(response_data, dict) and isinstance(response_data.get("output"), list):
            parts = []
            for output_item in response_data.get("output", []):
                if not isinstance(output_item, dict):
                    continue
                for content_item in output_item.get("content", []) or []:
                    if isinstance(content_item, dict):
                        text = content_item.get("text") or content_item.get("content")
                        if isinstance(text, str):
                            parts.append(text)
            return "\n".join(parts), self._extract_reasoning_text(response_data)

        choices = response_data.get("choices", []) if isinstance(response_data, dict) else []
        if not choices:
            return "", self._extract_reasoning_text(response_data)

        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = self._content_to_text(message.get("content", "")) if isinstance(message, dict) else ""
        reasoning = self._extract_reasoning_text(response_data)
        return content, reasoning

    def _extract_response_text(self, response_data, include_reasoning=True):
        content, reasoning = self._extract_response_parts(response_data)
        if include_reasoning:
            return self._combine_thinking(content, reasoning)
        return self._strip_inline_thinking(content)

    def _should_include_reasoning_by_default(self, insert_directly):
        if insert_directly:
            return False

        if self.use_custom_endpoint:
            effort = (self.settings.get_reasoning_effort() or "none").strip().lower()
            if effort == "none":
                return False

        return True

    def set_api_key(self, api_key):
        """Set the API key"""
        self.api_key = api_key
    
    def set_model(self, model):
        """Set the model to use"""
        self.model = model
    
    def send_request(self, prompt, content, insert_directly=False, include_reasoning=None):
        """Envoie une requête à l'API OpenAI en arrière-plan"""
        # Vérifier si une clé API est requise
        if not self.use_custom_endpoint and not self.api_key:
            self.request_error.emit("Clé API non configurée. Veuillez configurer votre clé API dans les paramètres.")
            return
        
        # Émettre le signal que la requête a commencé
        self.request_started.emit()
        
        # Lancer la requête dans un thread séparé
        if include_reasoning is None:
            include_reasoning = self._should_include_reasoning_by_default(insert_directly)

        threading.Thread(
            target=self._process_request_thread,
            args=(prompt, content, insert_directly, include_reasoning),
            daemon=True
        ).start()
    
    def _make_request_with_retry(self, headers, data, timeout=60):
        """Effectue une requête avec retry logic.
        
        Args:
            headers (dict): En-têtes de la requête
            data (dict): Données JSON à envoyer
            timeout (int): Timeout en secondes
            
        Returns:
            requests.Response: Réponse de l'API
            
        Raises:
            Exception: Si toutes les tentatives échouent
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    data=json.dumps(data),
                    timeout=timeout
                )
                
                # Si succès, retourner immédiatement
                if response.status_code == 200:
                    return response
                
                # Si erreur 429 (rate limit) ou 503 (service unavailable), réessayer
                if response.status_code in [429, 503, 502, 504]:
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (2 ** attempt)  # Backoff exponentiel
                        log(f"API error {response.status_code}, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})...", logging.WARNING)
                        time.sleep(wait_time)
                        continue
                
                # Pour d'autres erreurs, retourner la réponse pour traitement
                return response
                
            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    log(f"Request timeout, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})...", logging.WARNING)
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Request timed out after {self.max_retries} attempts") from e
            
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    log(f"Connection error, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})...", logging.WARNING)
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Connection failed after {self.max_retries} attempts") from e
            
            except Exception as e:
                # Pour les autres exceptions, ne pas réessayer
                raise
        
        # Si on arrive ici, toutes les tentatives ont échoué
        if last_exception:
            raise last_exception
        raise Exception("All retry attempts failed")
    
    def _process_request_thread(self, prompt, content, insert_directly=False, include_reasoning=True):
        """Traite la requête dans un thread séparé"""
        image_path = None
        try:
            # Préparer les en-têtes et les données de la requête
            headers = self._build_headers()
            data, image_path = self._build_request_data(prompt, content)
            
            # Envoyer la requête avec retry logic
            response = self._make_request_with_retry(headers, data, timeout=DEFAULT_API_TIMEOUT)
            
            # Vérifier si la requête a réussi
            if response.status_code == 200:
                # Analyser la réponse
                response_data = response.json()
                response_content = self._extract_response_text(response_data, include_reasoning=include_reasoning)
                
                if insert_directly:
                    # Insérer directement le résultat
                    from src.utils.text_inserter import TextInserter
                    inserter = TextInserter()
                    inserter.insert_text(response_content)
                else:
                    # Envoyer le contenu à la fenêtre de réponse via signal interne thread-safe
                    self._internal_finished.emit(response_content)
            else:
                # Gérer l'erreur via signal interne thread-safe
                error_message = f"Erreur {response.status_code}: {response.text}"
                self._internal_error.emit(error_message)
        
        except Exception as e:
            # Gérer l'exception via signal interne thread-safe
            self._internal_error.emit(f"Erreur: {str(e)}")
        
        finally:
            # Nettoyer l'image temporaire APRÈS la requête (succès ou échec)
            if insert_directly and image_path:
                self._cleanup_image(image_path)
    
    @Slot(str)
    def _emit_finished(self, content):
        """Émet le signal finished dans le thread Qt principal"""
        try:
            self.request_finished.emit(content)
        except Exception as e:
            log(f"Error emitting finished signal: {e}", logging.ERROR)
    
    @Slot(str)
    def _emit_error(self, error_message):
        """Émet le signal error dans le thread Qt principal"""
        try:
            self.request_error.emit(error_message)
        except Exception as e:
            log(f"Error emitting error signal: {e}", logging.ERROR)
    
    def _cleanup_image(self, image_path):
        """Nettoyer l'image temporaire après utilisation"""
        try:
            if not image_path or not os.path.exists(image_path):
                return

            basename = os.path.basename(image_path)
            if "supermenu_screenshot_" not in basename:
                return

            temp_dir = os.path.abspath(tempfile.gettempdir())
            image_dir = os.path.abspath(os.path.dirname(image_path))
            if image_dir != temp_dir:
                return
            
            os.remove(image_path)
            log(f"Image temporaire supprimée après traitement API: {image_path}", logging.DEBUG)
        except Exception as e:
            log(f"Erreur lors de la suppression de l'image après traitement API: {e}", logging.WARNING)

    @staticmethod
    def _data_url_to_base64(data_url):
        if not isinstance(data_url, str) or ";base64," not in data_url:
            return None
        return data_url.split(";base64,", 1)[1]

    def _build_request_data(self, prompt, content):
        """Construit les données de requête API.
        
        Args:
            prompt: Le prompt à envoyer
            content: Le contenu (texte, data URL d'image, ou chemin d'image)
            
        Returns:
            tuple: (data dict, image_path si image, None sinon)
        """
        image_path = None
        image_base64 = None
        image_data_url = None

        if isinstance(content, str) and content.startswith("data:image/") and ";base64," in content:
            image_data_url = content
            image_base64 = self._data_url_to_base64(content)
        elif isinstance(content, str) and os.path.isfile(content) and content.lower().endswith((".png", ".jpg", ".jpeg")):
            with open(content, "rb") as image_file:
                image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

            image_path = content
            ext = os.path.splitext(content)[1].lower()
            mime = "image/png" if ext == ".png" else "image/jpeg"
            image_data_url = f"data:{mime};base64,{image_base64}"

        full_prompt = f"{prompt}\n\n{content}" if content and not image_data_url else prompt

        if self.use_ollama_api:
            message = {"role": "user", "content": full_prompt}
            if image_base64:
                message["images"] = [image_base64]

            data = {
                "model": self.model,
                "messages": [message],
                "stream": False,
                "think": self._build_ollama_think_value(),
                "options": {"num_predict": DEFAULT_MAX_TOKENS},
            }
            return data, image_path

        if image_data_url:
            data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_data_url}},
                        ],
                    }
                ],
            }
        else:
            data = {"model": self.model, "messages": [{"role": "user", "content": full_prompt}]}

        if self.use_lmstudio_api:
            effort = (self.settings.get_reasoning_effort() or "none").strip().lower()
            if effort in CUSTOM_REASONING_EFFORTS and effort != "none":
                data["reasoning"] = {"effort": effort}

        if not self.use_custom_endpoint and is_gpt5_model(self.model):
            data["max_completion_tokens"] = DEFAULT_MAX_TOKENS
            if supports_reasoning(self.model):
                effort = normalize_reasoning_effort(self.model, self.settings.get_reasoning_effort())
                data["reasoning_effort"] = effort
        else:
            data["max_tokens"] = DEFAULT_MAX_TOKENS

        return data, image_path

    def _build_headers(self):
        """Construit les en-têtes de requête.
        
        Returns:
            dict: En-têtes HTTP
        """
        headers = {"Content-Type": "application/json"}

        if not self.use_custom_endpoint or (self.use_custom_endpoint and self.api_key):
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def process_request(self, prompt, content):
        """Méthode obsolète pour la compatibilité - utiliser send_request à la place"""
        self.send_request(prompt, content)

    def send_request_sync(self, prompt, content):
        """Envoie une requête à l'API OpenAI de manière synchrone et renvoie la réponse"""
        if not self.use_custom_endpoint and not self.api_key:
            raise Exception("Clé API non configurée. Veuillez configurer votre clé API dans les paramètres.")

        image_path = None
        try:
            headers = self._build_headers()
            data, image_path = self._build_request_data(prompt, content)

            response = self._make_request_with_retry(headers, data, timeout=DEFAULT_API_TIMEOUT)

            if response.status_code == 200:
                response_data = response.json()
                return self._extract_response_text(response_data)

            raise Exception(f"Erreur {response.status_code}: {response.text}")
        except Exception as e:
            raise Exception(f"Erreur lors de la requête API: {str(e)}")
        finally:
            if image_path:
                self._cleanup_image(image_path)

    @staticmethod
    def _is_ollama_endpoint(endpoint_url):
        return _looks_like_ollama_endpoint(endpoint_url)

    @staticmethod
    def _models_base_url(endpoint_url, is_ollama):
        return _models_base_url(endpoint_url, is_ollama)

    @staticmethod
    def fetch_available_models(endpoint_url, api_key=None, timeout=10, endpoint_type=None):
        """Récupère la liste des modèles disponibles depuis un endpoint compatible OpenAI."""
        try:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            endpoint_type = (endpoint_type or "").strip().lower()
            is_ollama = endpoint_type == "ollama" or (
                endpoint_type != "lmstudio" and _looks_like_ollama_endpoint(endpoint_url)
            )
            candidates = []
            base_url = _models_base_url(endpoint_url, is_ollama)
            if is_ollama:
                candidates.append(f"{base_url}/api/tags")
            candidates.append(f"{base_url}/v1/models")
            if not is_ollama:
                candidates.append(f"{base_url}/api/tags")

            last_error = None
            for models_url in candidates:
                response = requests.get(models_url, headers=headers, timeout=timeout)

                if response.status_code != 200:
                    last_error = f"Erreur {response.status_code}: {response.text}"
                    continue

                data = response.json()
                models = []

                if "data" in data and isinstance(data["data"], list):
                    for model_info in data["data"]:
                        if isinstance(model_info, dict):
                            model_id = model_info.get("id") or model_info.get("name")
                            if model_id:
                                models.append(model_id)

                if not models and "models" in data and isinstance(data["models"], list):
                    for model_info in data["models"]:
                        if isinstance(model_info, dict):
                            model_id = model_info.get("name") or model_info.get("id")
                            if model_id:
                                models.append(model_id)

                if models:
                    log(f"Modèles récupérés avec succès: {models}", logging.INFO)
                    return True, models

                last_error = "Aucun modèle trouvé dans la réponse de l'API"

            return False, last_error or "Aucun modèle trouvé dans la réponse de l'API"

        except requests.exceptions.Timeout:
            return False, "Timeout lors de la connexion au serveur"
        except requests.exceptions.ConnectionError:
            return False, "Impossible de se connecter au serveur"
        except Exception as e:
            return False, f"Erreur: {str(e)}"
