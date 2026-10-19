#!/usr/bin/env python
# -*- coding: utf-8 -*-

from supermenu_core.config.prompt_reasoning import resolve_reasoning_effort, normalize_reasoning_mode
import requests
import base64
import json
import os
import threading
import tempfile
import time
import logging
import uuid
from PySide6.QtCore import QObject, Signal, Slot
from supermenu_core.config.openai_models import normalize_openai_model
from supermenu_core.api.model_capabilities import parse_lmstudio_model_catalog
from supermenu_core.api.providers import common, lmstudio, ollama, openai_compatible
from supermenu_core.api.providers.common import log, logger  # noqa: F401 - logger is part of this module's API.
from supermenu_core.utils.thinking import split_inline_thinking


# One pooled session for the whole process. Without it every prompt paid a
# fresh TCP and TLS handshake -- 100 to 300 ms of latency on an app whose only
# job is to feel instant. requests.Session is thread-safe for this usage: each
# request runs on its own worker thread and shares the connection pool.
_SESSION = requests.Session()


def _session():
    return _SESSION


# Constante pour le timeout des requêtes API.
# Requests are not streamed, so the read timeout covers the whole generation.
# A timed-out generation is not resent (the server may still be producing and
# billing it): one 180 s attempt replaces the former three 60 s attempts.
DEFAULT_API_TIMEOUT = 180
LMSTUDIO_API_TIMEOUT = 300
CONNECT_TIMEOUT = 10
# Output caps, defined with the chat-completions payloads.
DEFAULT_MAX_TOKENS = openai_compatible.DEFAULT_MAX_TOKENS
OPENAI_MAX_COMPLETION_TOKENS = openai_compatible.OPENAI_MAX_COMPLETION_TOKENS

# Model capabilities rarely change, while clients created for one prompt are
# short-lived: share a successful probe across clients for a while.
CAPABILITIES_CACHE_TTL = 300
# A failed probe (server still starting, network hiccup) is retried later
# instead of being trusted for the whole lifetime of the client.
CAPABILITIES_RETRY_DELAY = 30
_CAPABILITIES_CACHE = {}
_CAPABILITIES_CACHE_LOCK = threading.Lock()


def _cached_capabilities(key):
    with _CAPABILITIES_CACHE_LOCK:
        entry = _CAPABILITIES_CACHE.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.monotonic() - stored_at > CAPABILITIES_CACHE_TTL:
            _CAPABILITIES_CACHE.pop(key, None)
            return None
        return value


def _remember_capabilities(key, value):
    with _CAPABILITIES_CACHE_LOCK:
        _CAPABILITIES_CACHE[key] = (time.monotonic(), value)


def clear_capabilities_cache():
    """Forget every capability probe shared between clients."""
    with _CAPABILITIES_CACHE_LOCK:
        _CAPABILITIES_CACHE.clear()


# Historical module-level name of the Ollama endpoint heuristic.
_looks_like_ollama_endpoint = ollama.looks_like_ollama_endpoint


# Historical module-level name; OpenAIClient._models_base_url delegates to it.
_models_base_url = common.models_base_url


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

    def __init__(
        self,
        settings,
        api_key=None,
        model=None,
        max_retries=3,
        retry_delay=1.0,
        *,
        allow_images=False,
        endpoint_api_key=None,
    ):
        super().__init__()
        self.api_key = api_key
        if endpoint_api_key is None:
            getter = getattr(settings, "get_custom_endpoint_api_key", None)
            endpoint_api_key = getter() if getter is not None else None
        self.endpoint_api_key = str(endpoint_api_key or "").strip()
        self.settings = settings
        target_getter = getattr(settings, "get_custom_model_target", None)
        self.model_target = dict(target_getter() or {}) if target_getter else {}
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.allow_images = bool(allow_images)
        self._closing = threading.Event()

        # Déterminer le modèle à utiliser
        self.use_custom_endpoint = settings.get_use_custom_endpoint()
        self.custom_endpoint = (
            settings.get_custom_endpoint() if self.use_custom_endpoint else None
        )
        self.custom_endpoint_type = (
            settings.get_custom_endpoint_type() if self.use_custom_endpoint else None
        )
        self.use_ollama_api = (
            self.use_custom_endpoint and self.custom_endpoint_type == "ollama"
        )
        self.use_lmstudio_api = (
            self.use_custom_endpoint and self.custom_endpoint_type == "lmstudio"
        )
        self._ollama_capabilities_checked = False
        self._ollama_capabilities = None
        self._ollama_probe_failed_at = None
        self._lmstudio_catalog_checked = False
        self._lmstudio_probe_failed_at = None
        self._lmstudio_reasoning_supported = None
        self._lmstudio_reasoning_options = None
        self._lmstudio_reasoning_default = None
        self._lmstudio_compat_url = ""
        self._capabilities_lock = threading.Lock()
        # Effort resolved by send_request() on the calling thread, per worker.
        self._request_state = threading.local()

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
            log(
                f"OpenAIClient: Utilisation du modèle {endpoint_kind} '{self.model}' avec endpoint {self.custom_endpoint}",
                logging.INFO,
            )
        else:
            # Sinon utiliser le modèle OpenAI
            self.model = normalize_openai_model(model or settings.get_model())
            log(
                f"OpenAIClient: Utilisation du modèle OpenAI '{self.model}'",
                logging.INFO,
            )

        # Connecter les signaux internes aux méthodes d'émission
        self._internal_finished.connect(self._emit_finished)
        self._internal_error.connect(self._emit_error)

        # Configurer l'URL de l'API
        if self.use_custom_endpoint:
            if not self.custom_endpoint:
                self.api_url = ""
            elif self.use_ollama_api:
                self.api_url = self._build_custom_chat_url(
                    self.custom_endpoint, ollama=True
                )
            elif self.use_lmstudio_api:
                base_url = _models_base_url(self.custom_endpoint, False, lmstudio=True)
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

    @staticmethod
    def _probe_recently_failed(failed_at):
        return (
            failed_at is not None
            and time.monotonic() - failed_at < CAPABILITIES_RETRY_DELAY
        )

    def _ensure_lmstudio_model_capabilities(self, timeout=10):
        """Cache the reasoning controls advertised for the selected LM Studio model."""
        if not self.use_lmstudio_api:
            return
        with self._capabilities_lock:
            if self._lmstudio_catalog_checked:
                return
            if self._probe_recently_failed(self._lmstudio_probe_failed_at):
                return
            base_url = _models_base_url(self.custom_endpoint, False, lmstudio=True)
            cache_key = ("lmstudio", base_url, self.model)
            cached = _cached_capabilities(cache_key)
            if cached is not None:
                supported, options, default = cached
                self._lmstudio_reasoning_supported = supported
                self._lmstudio_reasoning_options = list(options)
                self._lmstudio_reasoning_default = default
                self._lmstudio_catalog_checked = True
                return
            try:
                headers = self._build_headers()
                payload = lmstudio.request_model_catalog(
                    _session(),
                    base_url,
                    headers,
                    timeout,
                )
                if payload is None:
                    self._lmstudio_probe_failed_at = time.monotonic()
                    return
                selected = lmstudio.find_catalog_model(payload, self.model)

                # Only a readable catalog is final for this client.
                self._lmstudio_catalog_checked = True
                self._lmstudio_probe_failed_at = None
                if selected is None:
                    return
                self._lmstudio_reasoning_supported = selected["reasoning_supported"]
                self._lmstudio_reasoning_options = selected["reasoning_options"]
                self._lmstudio_reasoning_default = selected["reasoning_default"]
                _remember_capabilities(
                    cache_key,
                    (
                        selected["reasoning_supported"],
                        tuple(selected["reasoning_options"] or ()),
                        selected["reasoning_default"],
                    ),
                )
            except (requests.RequestException, ValueError, TypeError) as e:
                self._lmstudio_probe_failed_at = time.monotonic()
                log(
                    f"Impossible de lire les capacités LM Studio: {e}",
                    logging.DEBUG,
                )

    def _build_lmstudio_reasoning_value(self, reasoning_mode="default"):
        """Translate SuperMenu's effort into the selected model's native option."""
        return lmstudio.build_reasoning_value(
            self._get_provider_reasoning_effort(reasoning_mode),
            self._lmstudio_reasoning_supported,
            self._lmstudio_reasoning_options,
            self._lmstudio_reasoning_default,
        )

    _is_gpt_oss_model = staticmethod(common.is_gpt_oss_model)

    def _ensure_ollama_model_capabilities(self, timeout=10):
        """Cache Ollama's advertised capabilities for the selected model."""
        if not self.use_ollama_api:
            return
        with self._capabilities_lock:
            if self._ollama_capabilities_checked:
                return
            if self._probe_recently_failed(self._ollama_probe_failed_at):
                return
            base_url = _models_base_url(self.custom_endpoint, True)
            cache_key = ("ollama", base_url, self.model)
            cached = _cached_capabilities(cache_key)
            if cached is not None:
                self._ollama_capabilities = set(cached)
                self._ollama_capabilities_checked = True
                return
            try:
                payload = ollama.request_model_details(
                    _session(),
                    base_url,
                    self._build_headers(),
                    self.model,
                    timeout,
                )
                if payload is None:
                    # Ollama not started yet or model still being pulled:
                    # probe again on a later request rather than sending
                    # think blindly for the whole lifetime of the client.
                    self._ollama_probe_failed_at = time.monotonic()
                    return

                self._ollama_capabilities_checked = True
                self._ollama_probe_failed_at = None
                capabilities = ollama.parse_capabilities(payload)
                if capabilities is not None:
                    self._ollama_capabilities = capabilities
                    _remember_capabilities(
                        cache_key, frozenset(self._ollama_capabilities)
                    )
            except (requests.RequestException, ValueError, TypeError) as e:
                self._ollama_probe_failed_at = time.monotonic()
                log(
                    f"Impossible de lire les capacités Ollama: {e}",
                    logging.DEBUG,
                )

    def _get_provider_reasoning_effort(self, reasoning_mode="default"):
        return resolve_reasoning_effort(self._get_default_reasoning_effort(), reasoning_mode)

    def _get_default_reasoning_effort(self):
        """Read the reasoning setting for the active provider."""
        # A request worker reuses the value read by send_request() on the Qt
        # thread: the shared QSettings object is not touched from the worker.
        state = getattr(self, "_request_state", None)
        snapshot = getattr(state, "default_effort", None)
        if snapshot is not None:
            return snapshot
        if self.use_custom_endpoint:
            getter = getattr(self.settings, "get_custom_reasoning_effort", None)
            if getter:
                return getter()
        else:
            getter = getattr(self.settings, "get_openai_reasoning_effort", None)
            if getter:
                return getter(self.model)
        return self.settings.get_reasoning_effort()

    def _build_ollama_think_value(self, reasoning_mode="default"):
        """Construit la valeur du paramètre think pour Ollama."""
        return ollama.build_think_value(
            self._get_provider_reasoning_effort(reasoning_mode),
            self.model,
            self._ollama_capabilities,
        )

    # Provider-neutral response helpers, kept as static methods for callers.
    _combine_thinking = staticmethod(common.combine_thinking)
    _strip_inline_thinking = staticmethod(common.strip_inline_thinking)

    @staticmethod
    def _split_inline_thinking(text):
        """Separate inline think blocks, including an unclosed final block."""
        return split_inline_thinking(text)

    _normalize_response_parts = staticmethod(common.normalize_response_parts)
    _content_to_text = staticmethod(common.content_to_text)
    _reasoning_value_to_text = staticmethod(common.reasoning_value_to_text)
    _extract_reasoning_text = staticmethod(common.extract_reasoning_text)

    def _extract_response_parts(self, response_data):
        """Extrait la reponse finale et le raisonnement expose par le fournisseur."""
        if self.use_ollama_api:
            return ollama.extract_response_parts(response_data)

        if self.use_lmstudio_api:
            return lmstudio.extract_response_parts(response_data)

        return openai_compatible.extract_response_parts(response_data)

    def _extract_response_text(self, response_data, include_reasoning=True):
        content, reasoning = self._extract_response_parts(response_data)
        if include_reasoning:
            return self._combine_thinking(content, reasoning)
        return content

    def _should_include_reasoning_by_default(self, insert_directly, reasoning_mode="default"):
        if insert_directly:
            return False

        if self.use_custom_endpoint:
            # Use the effort actually sent for this prompt: a prompt set to
            # "Avec raisonnement" makes the model think even when the engine
            # setting is "none", so its trace must stay viewable.
            effort = (
                self._get_provider_reasoning_effort(reasoning_mode) or "none"
            ).strip().lower()
            if effort in {"none", "off"}:
                return False

        return True

    def set_api_key(self, api_key):
        """Set the API key"""
        self.api_key = api_key

    def set_model(self, model):
        """Set the model to use"""
        selected_model = (
            str(model or "").strip()
            if self.use_custom_endpoint
            else normalize_openai_model(model)
        )
        with self._capabilities_lock:
            self.model = selected_model
            self._ollama_capabilities_checked = False
            self._ollama_capabilities = None
            self._ollama_probe_failed_at = None
            self._lmstudio_catalog_checked = False
            self._lmstudio_probe_failed_at = None
            self._lmstudio_reasoning_supported = None
            self._lmstudio_reasoning_options = None
            self._lmstudio_reasoning_default = None

    def send_request(
        self,
        prompt,
        content,
        insert_directly=False,
        include_reasoning=None,
        request_id=None,
        target=None,
        reasoning_mode="default",
    ):
        """Envoie une requête à l'API OpenAI en arrière-plan"""
        reasoning_mode = normalize_reasoning_mode(reasoning_mode)
        request_id = request_id or uuid.uuid4().hex

        if self._closing.is_set():
            return request_id

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

        if reasoning_mode == "off":
            include_reasoning = False
        # Lancer la requête dans un thread séparé
        if include_reasoning is None:
            include_reasoning = self._should_include_reasoning_by_default(
                insert_directly, reasoning_mode
            )
        # Settings are read here, on the calling thread, never by the worker.
        try:
            default_effort = self._get_default_reasoning_effort()
        except Exception:
            default_effort = None  # The worker reads it again and reports errors.

        threading.Thread(
            target=self._process_request_thread,
            args=(
                request_id,
                prompt,
                content,
                insert_directly,
                include_reasoning,
                target,
                reasoning_mode,
                default_effort,
            ),
            daemon=True,
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
        # Fail fast on an unreachable server, but give the (non-streamed)
        # generation the whole read timeout.
        if isinstance(timeout, (int, float)):
            request_timeout = (min(CONNECT_TIMEOUT, timeout), timeout)
            read_timeout = timeout
        else:
            request_timeout = timeout
            read_timeout = timeout[-1] if isinstance(timeout, tuple) else timeout

        for attempt in range(self.max_retries):
            if self._closing.is_set():
                raise RuntimeError("Client fermé")
            try:
                response = _session().post(
                    request_url,
                    headers=headers,
                    data=json.dumps(data),
                    timeout=request_timeout,
                )

                # Si succès, retourner immédiatement
                if response.status_code == 200:
                    return response

                # Si erreur 429 (rate limit) ou 503 (service unavailable), réessayer
                if response.status_code in [429, 503, 502, 504]:
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (
                            2**attempt
                        )  # Backoff exponentiel
                        log(
                            f"API error {response.status_code}, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})...",
                            logging.WARNING,
                        )
                        time.sleep(wait_time)
                        continue

                # Pour d'autres erreurs, retourner la réponse pour traitement
                return response

            except requests.exceptions.ReadTimeout as e:
                # The server accepted the request and may still be generating
                # (and billing) the answer: resending it would only stack
                # identical generations. Connection failures stay retried.
                raise Exception(
                    "Le serveur n'a pas terminé la réponse dans le délai prévu "
                    f"({read_timeout} s). "
                    "Réduisez le texte ou le niveau de raisonnement, puis réessayez."
                ) from e

            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)
                    log(
                        f"Request timeout, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})...",
                        logging.WARNING,
                    )
                    time.sleep(wait_time)
                else:
                    raise Exception(
                        f"Request timed out after {self.max_retries} attempts"
                    ) from e

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)
                    log(
                        f"Connection error, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})...",
                        logging.WARNING,
                    )
                    time.sleep(wait_time)
                else:
                    raise Exception(
                        f"Connection failed after {self.max_retries} attempts"
                    ) from e

            except Exception:
                # Pour les autres exceptions, ne pas réessayer
                raise

        # Si on arrive ici, toutes les tentatives ont échoué
        if last_exception:
            raise last_exception
        raise Exception("All retry attempts failed")

    def _build_lmstudio_compat_data(self, native_data, reasoning_mode="default"):
        """Convert a native LM Studio request for pre-0.4 compatible servers."""
        return lmstudio.build_compat_data(
            native_data,
            self.model,
            self._get_provider_reasoning_effort(reasoning_mode),
        )

    def _perform_request(self, headers, data, timeout, reasoning_mode="default"):
        """Send a request, retry unsupported reasoning, then fall back if needed."""
        if self.use_lmstudio_api and "device" in self.model_target:
            # LM Link routing to one device never falls back to REST.
            return lmstudio.targeted_completion_response(
                _models_base_url(self.custom_endpoint, False, lmstudio=True),
                self.endpoint_api_key,
                data, self.model_target["device"], cancelled=self._closing,
                timeout=timeout,
            )
        response = self._make_request_with_retry(
            headers,
            data,
            timeout=timeout,
        )
        if not self.use_lmstudio_api:
            if (
                getattr(self, "use_ollama_api", False)
                and response.status_code == 400
                and "think" in data
                and "think" in str(getattr(response, "text", "") or "").lower()
            ):
                # "<model> does not support thinking": the capability probe
                # was unavailable, so retry once with the model's default.
                without_think = dict(data)
                without_think.pop("think", None)
                response = self._make_request_with_retry(
                    headers,
                    without_think,
                    timeout=timeout,
                )
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

        compat_data = self._build_lmstudio_compat_data(data, reasoning_mode)
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

    _response_was_truncated = staticmethod(common.response_was_truncated)

    def _truncation_message(self):
        """Explain a server-side cutoff in terms of what the user can change."""
        if self.use_lmstudio_api:
            return lmstudio.TRUNCATION_MESSAGE
        if self.use_ollama_api:
            return ollama.TRUNCATION_MESSAGE
        if self.use_custom_endpoint:
            return openai_compatible.custom_truncation_message()
        return openai_compatible.OPENAI_TRUNCATION_MESSAGE

    def _process_request_thread(
        self,
        request_id,
        prompt,
        content,
        insert_directly=False,
        include_reasoning=True,
        target=None,
        reasoning_mode="default",
        default_reasoning_effort=None,
    ):
        """Traite la requête dans un thread séparé"""
        cleanup_path = None
        state = getattr(self, "_request_state", None)
        if state is not None:
            state.default_effort = default_reasoning_effort
        try:
            # Préparer les en-têtes et les données de la requête
            headers = self._build_headers()
            self._ensure_ollama_model_capabilities()
            self._ensure_lmstudio_model_capabilities()
            reasoning_options = (
                {"reasoning_mode": reasoning_mode} if reasoning_mode != "default" else {}
            )
            data, cleanup_path = self._build_request_data(
                prompt, content, **reasoning_options
            )

            # Envoyer la requête avec retry logic
            timeout = (
                LMSTUDIO_API_TIMEOUT if self.use_lmstudio_api else DEFAULT_API_TIMEOUT
            )
            response = self._perform_request(
                headers, data, timeout=timeout, **reasoning_options
            )

            # Vérifier si la requête a réussi
            if response.status_code == 200:
                # Analyser la réponse
                response_data = response.json()
                # A cut answer must never be inserted as if it were complete,
                # nor a partial reasoning trace promoted to the final answer.
                if self._response_was_truncated(response_data):
                    raise RuntimeError(self._truncation_message())
                response_content = self._extract_response_text(
                    response_data, include_reasoning=include_reasoning
                )
                if not response_content.strip():
                    raise RuntimeError("Le fournisseur a renvoyé une réponse vide.")

                # Route every completion through the Qt thread. Direct insertion
                # must not manipulate focus or the clipboard from this worker.
                if not self._closing.is_set():
                    self._internal_finished.emit(
                        request_id,
                        response_content,
                        insert_directly,
                        target,
                    )
            else:
                # Gérer l'erreur via signal interne thread-safe
                error_message = f"Erreur {response.status_code}: {response.text}"
                if not self._closing.is_set():
                    self._internal_error.emit(request_id, error_message)

        except Exception as e:
            # Gérer l'exception via signal interne thread-safe
            if not self._closing.is_set():
                self._internal_error.emit(request_id, f"Erreur: {str(e)}")
        finally:
            if state is not None:
                state.default_effort = None
            self._cleanup_owned_image(cleanup_path)

    @Slot(str, str, bool, object)
    def _emit_finished(self, request_id, content, insert_directly, target):
        """Émet le signal finished dans le thread Qt principal"""
        if self._closing.is_set():
            return
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
        if self._closing.is_set():
            return
        try:
            self.request_error_scoped.emit(request_id, error_message)
            self.request_error.emit(error_message)
        except Exception as e:
            log(f"Error emitting error signal: {e}", logging.ERROR)

    def close(self):
        """Prevent background requests from emitting into a closing Qt app."""
        self._closing.set()

    @staticmethod
    def _data_url_to_base64(data_url):
        if not isinstance(data_url, str) or ";base64," not in data_url:
            return None
        return data_url.split(";base64,", 1)[1]

    @staticmethod
    def _owned_temporary_image(image_path):
        """Return the path only for screenshots owned by SuperMenu."""
        if not image_path or not isinstance(image_path, str):
            return None
        try:
            absolute_path = os.path.abspath(image_path)
        except (TypeError, ValueError, OSError):
            # Arbitrary selected text (NUL bytes, overlong strings...).
            return None
        if os.path.dirname(absolute_path) != os.path.abspath(tempfile.gettempdir()):
            return None
        if not os.path.basename(absolute_path).startswith("supermenu_screenshot_"):
            return None
        return absolute_path

    def _cleanup_owned_image(self, image_path):
        owned_path = self._owned_temporary_image(image_path)
        if not owned_path:
            return
        try:
            os.remove(owned_path)
            log(
                f"Image temporaire supprimée après traitement API: {owned_path}",
                logging.DEBUG,
            )
        except FileNotFoundError:
            return
        except OSError as exc:
            log(
                f"Impossible de supprimer l'image temporaire: {exc}",
                logging.WARNING,
            )

    def _build_request_data(self, prompt, content, reasoning_mode="default"):
        """Build a provider payload and return its owned cleanup path."""
        image_path = None
        image_base64 = None
        image_data_url = None

        if self.allow_images and isinstance(content, str):
            if content.startswith("data:image/") and ";base64," in content:
                image_data_url = content
                image_base64 = self._data_url_to_base64(content)
            elif (
                # Selected text is never read as a file path: a pasted
                # "C:\...\scan.png" (or a UNC path) must stay text. Only
                # SuperMenu's own temporary screenshot may be loaded here.
                content.lower().endswith((".png", ".jpg", ".jpeg"))
                and self._owned_temporary_image(content)
                and os.path.isfile(content)
            ):
                with open(content, "rb") as image_file:
                    image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
                image_path = content
                extension = os.path.splitext(content)[1].lower()
                mime = "image/png" if extension == ".png" else "image/jpeg"
                image_data_url = f"data:{mime};base64,{image_base64}"

        full_prompt = (
            f"{prompt}\n\n{content}" if content and not image_data_url else prompt
        )

        if self.use_ollama_api:
            data = ollama.build_payload(
                self.model,
                full_prompt,
                image_base64,
                self._build_ollama_think_value(reasoning_mode),
            )
            return data, image_path

        if self.use_lmstudio_api:
            data = lmstudio.build_payload(
                self.model,
                prompt,
                full_prompt,
                image_data_url,
                self._build_lmstudio_reasoning_value(reasoning_mode),
            )
            return data, image_path

        if not self.use_custom_endpoint:
            # The effort is read only once the model is known to be
            # supported (reading it may store a normalized value).
            data = openai_compatible.build_openai_payload(
                self.model,
                prompt,
                full_prompt,
                image_data_url,
                lambda: self._get_provider_reasoning_effort(reasoning_mode),
            )
        else:
            data = openai_compatible.build_custom_payload(
                self.model,
                prompt,
                full_prompt,
                image_data_url,
            )

        return data, image_path

    def _build_headers(self):
        """Construit les en-têtes de requête.

        Returns:
            dict: En-têtes HTTP
        """
        headers = {"Content-Type": "application/json"}

        if self.use_custom_endpoint and self.endpoint_api_key:
            headers["Authorization"] = f"Bearer {self.endpoint_api_key}"
        elif not self.use_custom_endpoint and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    # Legacy surface kept for compatibility only. The applications use
    # send_request() and the *_scoped signals; nothing in production calls
    # process_request() or send_request_sync().
    def process_request(self, prompt, content):
        """Obsolète : utiliser send_request à la place."""
        self.send_request(prompt, content)

    def send_request_sync(self, prompt, content, reasoning_mode="default"):
        """Obsolète : envoie une requête de manière synchrone et renvoie la réponse.

        Applies the same checks as send_request(): complete custom
        configuration, per-prompt reasoning and cutoff detection.
        """
        reasoning_mode = normalize_reasoning_mode(reasoning_mode)
        if self.use_custom_endpoint and (not self.custom_endpoint or not self.model):
            raise Exception(
                "Configuration personnalisée incomplète. "
                "Renseignez obligatoirement l'endpoint et le modèle."
            )
        if not self.use_custom_endpoint and not self.api_key:
            raise Exception(
                "Clé API non configurée. Veuillez configurer votre clé API dans les paramètres."
            )

        cleanup_path = None
        try:
            headers = self._build_headers()
            self._ensure_ollama_model_capabilities()
            self._ensure_lmstudio_model_capabilities()
            reasoning_options = (
                {"reasoning_mode": reasoning_mode} if reasoning_mode != "default" else {}
            )
            data, cleanup_path = self._build_request_data(
                prompt, content, **reasoning_options
            )

            timeout = (
                LMSTUDIO_API_TIMEOUT if self.use_lmstudio_api else DEFAULT_API_TIMEOUT
            )
            response = self._perform_request(
                headers, data, timeout=timeout, **reasoning_options
            )

            if response.status_code == 200:
                response_data = response.json()
                if self._response_was_truncated(response_data):
                    raise RuntimeError(self._truncation_message())
                response_text = self._extract_response_text(
                    response_data,
                    include_reasoning=self._should_include_reasoning_by_default(
                        False, reasoning_mode
                    ),
                )
                if not response_text.strip():
                    raise RuntimeError("Le fournisseur a renvoyé une réponse vide.")
                return response_text
            http_error = f"{response.status_code}: {response.text}"
        except Exception as e:
            raise Exception(f"Erreur lors de la requête API: {str(e)}") from e
        finally:
            self._cleanup_owned_image(cleanup_path)
        raise Exception(f"Erreur lors de la requête API ({http_error})")

    @staticmethod
    def _models_base_url(endpoint_url, is_ollama, lmstudio=False):
        return _models_base_url(endpoint_url, is_ollama, lmstudio=lmstudio)

    @staticmethod
    def fetch_available_models(
        endpoint_url, api_key=None, timeout=10, endpoint_type=None
    ):
        """Return model IDs using an optional custom-endpoint credential."""
        success, result = OpenAIClient.fetch_available_model_details(
            endpoint_url,
            api_key=api_key,
            timeout=timeout,
            endpoint_type=endpoint_type,
        )
        if not success:
            return False, result
        return True, [model["id"] for model in result]

    @staticmethod
    def fetch_available_model_details(
        endpoint_url, api_key=None, timeout=10, endpoint_type=None
    ):
        """Fetch a catalog with an optional custom-endpoint credential."""
        try:
            headers = {"Content-Type": "application/json"}
            endpoint_api_key = str(api_key or "").strip()
            if endpoint_api_key:
                headers["Authorization"] = f"Bearer {endpoint_api_key}"
            endpoint_type = (endpoint_type or "").strip().lower()
            is_ollama = endpoint_type == "ollama" or (
                endpoint_type != "lmstudio"
                and _looks_like_ollama_endpoint(endpoint_url)
            )
            candidates = []
            base_url = _models_base_url(
                endpoint_url, is_ollama, lmstudio=endpoint_type == "lmstudio"
            )
            if is_ollama:
                candidates.append(f"{base_url}/api/tags")
            elif endpoint_type == "lmstudio":
                candidates.append(f"{base_url}/api/v1/models")
            candidates.append(f"{base_url}/v1/models")
            if not is_ollama:
                candidates.append(f"{base_url}/api/tags")

            last_error = None
            for models_url in candidates:
                response = _session().get(
                    models_url, headers=headers, timeout=timeout
                )

                if response.status_code != 200:
                    last_error = f"Erreur {response.status_code}: {response.text}"
                    continue

                data = response.json()
                model_details = []

                if models_url.endswith("/api/v1/models"):
                    model_details = parse_lmstudio_model_catalog(data)

                if (
                    not model_details
                    and "data" in data
                    and isinstance(data["data"], list)
                ):
                    for model_info in data["data"]:
                        if isinstance(model_info, dict):
                            model_id = model_info.get("id") or model_info.get("name")
                            if model_id:
                                model_details.append(
                                    OpenAIClient._basic_model_details(model_id)
                                )

                if (
                    not model_details
                    and "models" in data
                    and isinstance(data["models"], list)
                ):
                    for model_info in data["models"]:
                        if isinstance(model_info, dict):
                            model_id = (
                                model_info.get("key")
                                or model_info.get("name")
                                or model_info.get("id")
                            )
                            if model_id:
                                model_details.append(
                                    OpenAIClient._basic_model_details(model_id)
                                )

                if model_details:
                    if endpoint_type == "lmstudio":
                        from .lmstudio_provenance import (
                            enrich_provenance, fetch_provenance,
                        )
                        available, loaded = fetch_provenance(
                            base_url, endpoint_api_key or None, timeout=timeout,
                        )
                        enrich_provenance(model_details, available, loaded)
                    model_ids = [model["id"] for model in model_details]
                    log(f"Modèles récupérés avec succès: {model_ids}", logging.INFO)
                    return True, model_details

                last_error = "Aucun modèle trouvé dans la réponse de l'API"

            return False, last_error or "Aucun modèle trouvé dans la réponse de l'API"

        except requests.exceptions.Timeout:
            return False, "Timeout lors de la connexion au serveur"
        except requests.exceptions.ConnectionError:
            return False, "Impossible de se connecter au serveur"
        except Exception as e:
            return False, f"Erreur: {str(e)}"

    @staticmethod
    def _basic_model_details(model_id):
        return {
            "id": model_id,
            "identifiers": [model_id],
            "reasoning_supported": None,
            "reasoning_options": [],
            "reasoning_default": None,
        }
