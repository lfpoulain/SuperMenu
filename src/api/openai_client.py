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
import uuid
from urllib.parse import urlparse
from PySide6.QtCore import QObject, Signal, Slot
from src.utils.logger import log
from src.config.settings import (
    CUSTOM_REASONING_EFFORTS,
    OLLAMA_GPT_OSS_THINK_EFFORTS,
)
from src.config.openai_models import (
    get_openai_model_capabilities,
    normalize_openai_model,
    normalize_reasoning_effort,
)

# Constante pour le timeout des requêtes API
DEFAULT_API_TIMEOUT = 60
LMSTUDIO_API_TIMEOUT = 300
DEFAULT_MAX_TOKENS = 2048
THINK_BLOCK_RE = re.compile(
    r"<think\b[^>]*>(.*?)</think>",
    re.IGNORECASE | re.DOTALL,
)
THINK_TAG_RE = re.compile(r"</?think\b[^>]*>", re.IGNORECASE)
BRACKET_THINK_BLOCK_RE = re.compile(
    r"\[think\](.*?)\[/think\]",
    re.IGNORECASE | re.DOTALL,
)
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

    for suffix in (
        "/api/v1/chat",
        "/api/v1/models",
        "/v1/chat/completions",
        "/v1/models",
        "/v1",
        "/api/v1",
    ):
        if base.endswith(suffix):
            return base[: -len(suffix)]
    return base


class OpenAIClient(QObject):
    """Client for OpenAI API interactions"""
    
    # Signals publics
    request_started = Signal()
    request_finished = Signal(str)
    request_error = Signal(str)
    request_started_scoped = Signal(str, bool)
    request_finished_scoped = Signal(str, str, bool, object)
    request_error_scoped = Signal(str, str)
    
    # Signaux internes pour communication inter-threads (thread-safe)
    _internal_finished = Signal(str, str, bool, object)
    _internal_error = Signal(str, str)
    
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
        self._ollama_capabilities_checked = False
        self._ollama_capabilities = None
        self._lmstudio_catalog_checked = False
        self._lmstudio_reasoning_options = None
        self._lmstudio_compat_url = ""
        
        # Si on utilise un endpoint personnalisé et qu'on a un custom_model dans les settings, l'utiliser
        if self.use_custom_endpoint:
            custom_model = settings.get_custom_model()
            self.model = model if model else (custom_model or "")
            if self.use_ollama_api:
                endpoint_kind = "Ollama"
            elif self.use_lmstudio_api:
                endpoint_kind = "LM Studio"
            else:
                endpoint_kind = "personnalisé"
            log(f"OpenAIClient: Utilisation du modèle {endpoint_kind} '{self.model}' avec endpoint {self.custom_endpoint}", logging.INFO)
        else:
            # Sinon utiliser le modèle OpenAI
            self.model = normalize_openai_model(model or settings.get_model())
            log(f"OpenAIClient: Utilisation du modèle OpenAI '{self.model}'", logging.INFO)
        
        # Connecter les signaux internes aux méthodes d'émission
        self._internal_finished.connect(self._emit_finished)
        self._internal_error.connect(self._emit_error)
        
        # Configurer l'URL de l'API
        if self.use_custom_endpoint:
            if not self.custom_endpoint:
                self.api_url = ""
            elif self.use_ollama_api:
                self.api_url = self._build_custom_chat_url(self.custom_endpoint, ollama=True)
            elif self.use_lmstudio_api:
                base_url = _models_base_url(self.custom_endpoint, False)
                self.api_url = f"{base_url}/api/v1/chat"
                self._lmstudio_compat_url = f"{base_url}/v1/chat/completions"
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

    def _ensure_lmstudio_model_capabilities(self, timeout=10):
        """Cache the reasoning controls advertised for the selected LM Studio model."""
        if not self.use_lmstudio_api or self._lmstudio_catalog_checked:
            return

        self._lmstudio_catalog_checked = True
        try:
            headers = self._build_headers()
            base_url = _models_base_url(self.custom_endpoint, False)
            response = requests.get(
                f"{base_url}/api/v1/models",
                headers=headers,
                timeout=timeout,
            )
            if response.status_code != 200:
                return

            payload = response.json()
            if not isinstance(payload, dict):
                return
            models = payload.get("models", [])
            if not isinstance(models, list):
                return
            selected = None
            for model_info in models:
                if not isinstance(model_info, dict):
                    continue
                identifiers = {
                    model_info.get("key"),
                    model_info.get("id"),
                    model_info.get("name"),
                    model_info.get("display_name"),
                }
                for instance in model_info.get("loaded_instances", []) or []:
                    if isinstance(instance, dict):
                        identifiers.add(instance.get("id"))
                        identifiers.add(instance.get("model_key"))
                if self.model in identifiers:
                    selected = model_info
                    break

            if selected is None:
                return

            capabilities = selected.get("capabilities", {})
            if not isinstance(capabilities, dict):
                return
            reasoning = capabilities.get("reasoning", {})
            if not isinstance(reasoning, dict):
                return
            options = reasoning.get("allowed_options", [])
            if isinstance(options, list):
                normalized = {
                    str(option).strip().lower()
                    for option in options
                    if str(option).strip()
                }
                if normalized:
                    self._lmstudio_reasoning_options = normalized
        except (requests.RequestException, ValueError, TypeError) as e:
            log(
                f"Impossible de lire les capacités LM Studio: {e}",
                logging.DEBUG,
            )

    def _build_lmstudio_reasoning_value(self):
        """Translate SuperMenu's effort into the selected model's native option."""
        requested = (
            self._get_provider_reasoning_effort() or "none"
        ).strip().lower()
        options = self._lmstudio_reasoning_options

        if not options:
            return "off" if requested == "none" else requested

        if requested == "none":
            if "off" in options:
                return "off"
            if "none" in options:
                return "none"
            if "low" in options:
                return "low"
            return None

        if requested in options:
            return requested
        if "on" in options:
            return "on"
        return None

    @staticmethod
    def _is_gpt_oss_model(model_name):
        return "gpt-oss" in str(model_name or "").lower()

    def _ensure_ollama_model_capabilities(self, timeout=10):
        """Cache Ollama's advertised capabilities for the selected model."""
        if not self.use_ollama_api or self._ollama_capabilities_checked:
            return

        self._ollama_capabilities_checked = True
        try:
            base_url = _models_base_url(self.custom_endpoint, True)
            response = requests.post(
                f"{base_url}/api/show",
                headers=self._build_headers(),
                data=json.dumps({"model": self.model, "verbose": False}),
                timeout=timeout,
            )
            if response.status_code != 200:
                return

            payload = response.json()
            if not isinstance(payload, dict):
                return
            capabilities = payload.get("capabilities", [])
            if isinstance(capabilities, list):
                self._ollama_capabilities = {
                    str(capability).strip().lower()
                    for capability in capabilities
                    if str(capability).strip()
                }
        except (requests.RequestException, ValueError, TypeError) as e:
            log(
                f"Impossible de lire les capacités Ollama: {e}",
                logging.DEBUG,
            )

    def _get_provider_reasoning_effort(self):
        """Read the reasoning setting for the active provider."""
        if self.use_custom_endpoint:
            getter = getattr(self.settings, "get_custom_reasoning_effort", None)
            if getter:
                return getter()
        else:
            getter = getattr(self.settings, "get_openai_reasoning_effort", None)
            if getter:
                return getter(self.model)
        return self.settings.get_reasoning_effort()

    def _build_ollama_think_value(self):
        """Construit la valeur du paramètre think pour Ollama."""
        effort = (self._get_provider_reasoning_effort() or "none").strip().lower()
        if self._is_gpt_oss_model(self.model):
            if effort in OLLAMA_GPT_OSS_THINK_EFFORTS:
                return effort
            # GPT-OSS cannot disable its trace; low is the documented
            # latency-minimizing fallback when the UI asks for "none".
            return "low"

        if (
            self._ollama_capabilities is not None
            and "thinking" not in self._ollama_capabilities
        ):
            return None

        if effort == "none":
            return False

        # Qwen 3, DeepSeek R1/v3.1 and other Ollama thinking models use the
        # documented boolean switch. Effort strings are GPT-OSS-specific.
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
        visible, _reasoning = OpenAIClient._split_inline_thinking(text)
        return visible

    @staticmethod
    def _split_inline_thinking(text):
        """Separate inline think blocks, including an unclosed final block."""
        if not isinstance(text, str) or not text:
            return "", ""

        reasoning_parts = [
            match.group(1).strip()
            for match in THINK_BLOCK_RE.finditer(text)
            if match.group(1).strip()
        ]
        reasoning_parts.extend(
            match.group(1).strip()
            for match in BRACKET_THINK_BLOCK_RE.finditer(text)
            if match.group(1).strip()
        )

        visible = THINK_BLOCK_RE.sub("", text)
        visible = BRACKET_THINK_BLOCK_RE.sub("", visible)

        unclosed = re.search(r"<think\b[^>]*>", visible, re.IGNORECASE)
        if unclosed:
            tail = visible[unclosed.end():].strip()
            if tail:
                reasoning_parts.append(tail)
            visible = visible[:unclosed.start()]

        unclosed_bracket = re.search(r"\[think\]", visible, re.IGNORECASE)
        if unclosed_bracket:
            tail = visible[unclosed_bracket.end():].strip()
            if tail:
                reasoning_parts.append(tail)
            visible = visible[:unclosed_bracket.start()]

        visible = THINK_TAG_RE.sub("", visible)
        visible = BRACKET_THINK_TAG_RE.sub("", visible)
        return visible.strip(), "\n\n".join(reasoning_parts).strip()

    @staticmethod
    def _normalize_response_parts(content, reasoning):
        """Normalize provider quirks and keep a usable answer when only one channel exists."""
        visible_content, inline_reasoning = OpenAIClient._split_inline_thinking(
            content
        )
        reasoning_parts = []
        for part in (reasoning, inline_reasoning):
            part = part.strip() if isinstance(part, str) else ""
            if part and part not in reasoning_parts:
                reasoning_parts.append(part)
        normalized_reasoning = "\n\n".join(reasoning_parts)

        # Some local model templates put their useful answer in the reasoning
        # channel and leave the final channel empty. Treat the only available
        # text as the answer instead of displaying a false "no final answer".
        if not visible_content and normalized_reasoning:
            return normalized_reasoning, ""

        return visible_content, normalized_reasoning

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
            return self._normalize_response_parts(content, thinking)

        if self.use_lmstudio_api:
            output = response_data.get("output", []) if isinstance(response_data, dict) else []
            if isinstance(output, list) and output:
                messages = []
                reasoning_parts = []
                for item in output:
                    if not isinstance(item, dict):
                        continue
                    item_type = str(item.get("type", "")).lower()
                    item_text = self._content_to_text(
                        item.get("content", item.get("text", ""))
                    )
                    if item_type == "message" and item_text:
                        messages.append(item_text)
                    elif item_type == "reasoning":
                        reasoning_text = self._reasoning_value_to_text(
                            item.get("content", item.get("text", ""))
                        )
                        if reasoning_text:
                            reasoning_parts.append(reasoning_text)
                return self._normalize_response_parts(
                    "\n".join(messages),
                    "\n\n".join(reasoning_parts),
                )

            choices = response_data.get("choices", []) if isinstance(response_data, dict) else []
            if not choices:
                return self._normalize_response_parts(
                    "",
                    self._extract_reasoning_text(response_data),
                )

            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            content = self._content_to_text(message.get("content", "")) if isinstance(message, dict) else ""
            reasoning = self._extract_reasoning_text(response_data)
            return self._normalize_response_parts(content, reasoning)

        if isinstance(response_data, dict) and response_data.get("output_text"):
            return self._normalize_response_parts(
                self._content_to_text(response_data.get("output_text")),
                self._extract_reasoning_text(response_data),
            )

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
            return self._normalize_response_parts(
                "\n".join(parts),
                self._extract_reasoning_text(response_data),
            )

        choices = response_data.get("choices", []) if isinstance(response_data, dict) else []
        if not choices:
            return self._normalize_response_parts(
                "",
                self._extract_reasoning_text(response_data),
            )

        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = self._content_to_text(message.get("content", "")) if isinstance(message, dict) else ""
        reasoning = self._extract_reasoning_text(response_data)
        return self._normalize_response_parts(content, reasoning)

    def _extract_response_text(self, response_data, include_reasoning=True):
        content, reasoning = self._extract_response_parts(response_data)
        if include_reasoning:
            return self._combine_thinking(content, reasoning)
        return content

    def _should_include_reasoning_by_default(self, insert_directly):
        if insert_directly:
            return False

        if self.use_custom_endpoint:
            effort = (self._get_provider_reasoning_effort() or "none").strip().lower()
            if effort == "none":
                return False

        return True

    def set_api_key(self, api_key):
        """Set the API key"""
        self.api_key = api_key
    
    def set_model(self, model):
        """Set the model to use"""
        self.model = model
    
    def send_request(
        self,
        prompt,
        content,
        insert_directly=False,
        include_reasoning=None,
        request_id=None,
        target=None,
    ):
        """Envoie une requête à l'API OpenAI en arrière-plan"""
        request_id = request_id or uuid.uuid4().hex

        if self.use_custom_endpoint and (not self.custom_endpoint or not self.model):
            message = (
                "Configuration personnalisée incomplète. "
                "Renseignez obligatoirement l'endpoint et le modèle."
            )
            self.request_error.emit(message)
            self.request_error_scoped.emit(request_id, message)
            return request_id

        # Vérifier si une clé API est requise
        if not self.use_custom_endpoint and not self.api_key:
            message = (
                "Clé API non configurée. Veuillez configurer votre clé API "
                "dans les paramètres."
            )
            self.request_error.emit(message)
            self.request_error_scoped.emit(request_id, message)
            return request_id
        
        # Émettre le signal que la requête a commencé
        self.request_started.emit()
        self.request_started_scoped.emit(request_id, insert_directly)
        
        # Lancer la requête dans un thread séparé
        if include_reasoning is None:
            include_reasoning = self._should_include_reasoning_by_default(insert_directly)

        threading.Thread(
            target=self._process_request_thread,
            args=(
                request_id,
                prompt,
                content,
                insert_directly,
                include_reasoning,
                target,
            ),
            daemon=True
        ).start()
        return request_id
    
    def _make_request_with_retry(self, headers, data, timeout=60, api_url=None):
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
        request_url = api_url or self.api_url
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    request_url,
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
            
            except Exception:
                # Pour les autres exceptions, ne pas réessayer
                raise
        
        # Si on arrive ici, toutes les tentatives ont échoué
        if last_exception:
            raise last_exception
        raise Exception("All retry attempts failed")

    def _build_lmstudio_compat_data(self, native_data):
        """Convert a native LM Studio request for pre-0.4 compatible servers."""
        native_input = native_data.get("input", "")
        if isinstance(native_input, str):
            message_content = native_input
        else:
            content_parts = []
            for item in native_input if isinstance(native_input, list) else []:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "message":
                    text_content = item.get("content")
                    if isinstance(text_content, str):
                        content_parts.append(
                            {"type": "text", "text": text_content}
                        )
                elif item.get("type") == "image":
                    data_url = item.get("data_url")
                    if isinstance(data_url, str):
                        content_parts.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            }
                        )
            message_content = content_parts

        data = {
            "model": native_data.get("model", self.model),
            "messages": [{"role": "user", "content": message_content}],
            # LM Studio's compatible API uses -1 for no artificial output cap.
            "max_tokens": -1,
        }
        effort = (
            self._get_provider_reasoning_effort() or "none"
        ).strip().lower()
        if effort in {"low", "medium", "high"}:
            data["reasoning"] = {"effort": effort}
        elif self._is_gpt_oss_model(self.model):
            data["reasoning"] = {"effort": "low"}
        return data

    def _perform_request(self, headers, data, timeout):
        """Send a request, retry unsupported reasoning, then fall back if needed."""
        response = self._make_request_with_retry(
            headers,
            data,
            timeout=timeout,
        )
        if not self.use_lmstudio_api:
            return response

        if response.status_code == 400 and "reasoning" in data:
            without_reasoning = dict(data)
            without_reasoning.pop("reasoning", None)
            response = self._make_request_with_retry(
                headers,
                without_reasoning,
                timeout=timeout,
            )

        if response.status_code not in {404, 405}:
            return response

        compat_data = self._build_lmstudio_compat_data(data)
        response = self._make_request_with_retry(
            headers,
            compat_data,
            timeout=timeout,
            api_url=self._lmstudio_compat_url,
        )
        if response.status_code == 400 and "reasoning" in compat_data:
            compat_data.pop("reasoning", None)
            response = self._make_request_with_retry(
                headers,
                compat_data,
                timeout=timeout,
                api_url=self._lmstudio_compat_url,
            )
        return response

    @staticmethod
    def _response_was_truncated(response_data):
        """Detect explicit server-side token/context cutoffs."""
        if not isinstance(response_data, dict):
            return False

        reasons = [
            response_data.get("finish_reason"),
            response_data.get("stop_reason"),
        ]
        choices = response_data.get("choices", [])
        if isinstance(choices, list):
            reasons.extend(
                choice.get("finish_reason")
                for choice in choices
                if isinstance(choice, dict)
            )
        stats = response_data.get("stats", {})
        if isinstance(stats, dict):
            reasons.extend((stats.get("finish_reason"), stats.get("stop_reason")))

        cutoff_markers = ("length", "max_token", "context")
        return any(
            any(marker in str(reason).lower() for marker in cutoff_markers)
            for reason in reasons
            if reason
        )
    
    def _process_request_thread(
        self,
        request_id,
        prompt,
        content,
        insert_directly=False,
        include_reasoning=True,
        target=None,
    ):
        """Traite la requête dans un thread séparé"""
        image_path = None
        try:
            # Préparer les en-têtes et les données de la requête
            headers = self._build_headers()
            self._ensure_ollama_model_capabilities()
            self._ensure_lmstudio_model_capabilities()
            data, image_path = self._build_request_data(prompt, content)
            
            # Envoyer la requête avec retry logic
            timeout = (
                LMSTUDIO_API_TIMEOUT
                if self.use_lmstudio_api
                else DEFAULT_API_TIMEOUT
            )
            response = self._perform_request(headers, data, timeout=timeout)
            
            # Vérifier si la requête a réussi
            if response.status_code == 200:
                # Analyser la réponse
                response_data = response.json()
                if self.use_lmstudio_api and self._response_was_truncated(
                    response_data
                ):
                    raise RuntimeError(
                        "LM Studio a interrompu la réponse car la fenêtre de "
                        "contexte du modèle est pleine. Rechargez le modèle avec "
                        "un Context Length plus élevé, puis réessayez."
                    )
                response_content = self._extract_response_text(response_data, include_reasoning=include_reasoning)
                if not response_content.strip():
                    raise RuntimeError("Le fournisseur a renvoyé une réponse vide.")
                
                # Route every completion through the Qt thread. Direct insertion
                # must not manipulate focus or the clipboard from this worker.
                self._internal_finished.emit(
                    request_id,
                    response_content,
                    insert_directly,
                    target,
                )
            else:
                # Gérer l'erreur via signal interne thread-safe
                error_message = f"Erreur {response.status_code}: {response.text}"
                self._internal_error.emit(request_id, error_message)
        
        except Exception as e:
            # Gérer l'exception via signal interne thread-safe
            self._internal_error.emit(request_id, f"Erreur: {str(e)}")
        
        finally:
            # Nettoyer l'image temporaire APRÈS la requête (succès ou échec)
            if image_path:
                self._cleanup_image(image_path)
    
    @Slot(str, str, bool, object)
    def _emit_finished(self, request_id, content, insert_directly, target):
        """Émet le signal finished dans le thread Qt principal"""
        try:
            self.request_finished_scoped.emit(
                request_id, content, insert_directly, target
            )
            if not insert_directly:
                self.request_finished.emit(content)
        except Exception as e:
            log(f"Error emitting finished signal: {e}", logging.ERROR)
    
    @Slot(str, str)
    def _emit_error(self, request_id, error_message):
        """Émet le signal error dans le thread Qt principal"""
        try:
            self.request_error_scoped.emit(request_id, error_message)
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
            }
            think_value = self._build_ollama_think_value()
            if think_value is not None:
                data["think"] = think_value
            return data, image_path

        if self.use_lmstudio_api:
            native_input = full_prompt
            if image_data_url:
                native_input = [
                    {"type": "message", "content": prompt},
                    {"type": "image", "data_url": image_data_url},
                ]

            data = {
                "model": self.model,
                "input": native_input,
                "stream": False,
                "store": False,
            }
            reasoning = self._build_lmstudio_reasoning_value()
            if reasoning:
                data["reasoning"] = reasoning
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

        if not self.use_custom_endpoint:
            capabilities = get_openai_model_capabilities(self.model)
            if capabilities is None:
                raise ValueError(f"Modèle OpenAI non supporté: {self.model}")

            data[capabilities.max_tokens_parameter] = DEFAULT_MAX_TOKENS
            effort = normalize_reasoning_effort(
                self.model,
                self._get_provider_reasoning_effort(),
            )
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
            self._ensure_ollama_model_capabilities()
            self._ensure_lmstudio_model_capabilities()
            data, image_path = self._build_request_data(prompt, content)

            timeout = (
                LMSTUDIO_API_TIMEOUT
                if self.use_lmstudio_api
                else DEFAULT_API_TIMEOUT
            )
            response = self._perform_request(headers, data, timeout=timeout)

            if response.status_code == 200:
                response_data = response.json()
                if self.use_lmstudio_api and self._response_was_truncated(
                    response_data
                ):
                    raise RuntimeError(
                        "LM Studio a atteint la limite de sa fenêtre de contexte."
                    )
                response_text = self._extract_response_text(response_data)
                if not response_text.strip():
                    raise RuntimeError("Le fournisseur a renvoyé une réponse vide.")
                return response_text

            raise Exception(f"Erreur {response.status_code}: {response.text}")
        except Exception as e:
            raise Exception(f"Erreur lors de la requête API: {str(e)}")
        finally:
            if image_path:
                self._cleanup_image(image_path)

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
            elif endpoint_type == "lmstudio":
                candidates.append(f"{base_url}/api/v1/models")
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
                            model_id = (
                                model_info.get("key")
                                or model_info.get("name")
                                or model_info.get("id")
                            )
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
