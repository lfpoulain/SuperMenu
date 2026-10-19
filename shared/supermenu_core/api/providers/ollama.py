#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Ollama native API: endpoint detection, probe, think control, payloads and replies."""

import json
from urllib.parse import urlparse

from supermenu_core.api.providers.common import (
    content_to_text,
    is_gpt_oss_model,
    normalize_response_parts,
    reasoning_value_to_text,
)
from supermenu_core.config.provider_settings import (
    CUSTOM_REASONING_EFFORTS,
    OLLAMA_GPT_OSS_THINK_EFFORTS,
)

TRUNCATION_MESSAGE = (
    "Ollama a interrompu la réponse avant la fin (limite de "
    "longueur ou de contexte du modèle atteinte). Réduisez le "
    "texte ou augmentez le contexte du modèle, puis réessayez."
)


def looks_like_ollama_endpoint(endpoint_url):
    parsed = urlparse(endpoint_url or "")
    host = (parsed.hostname or "").lower()
    port = parsed.port
    path = (parsed.path or "").lower()
    return port == 11434 or "ollama" in host or path.startswith("/api")


def request_model_details(session, base_url, headers, model, timeout):
    """Ask /api/show about a model; None when the answer is unreadable.

    Transport and JSON errors propagate: the caller counts them, like an
    unreadable answer, as a failed probe.
    """
    response = session.post(
        f"{base_url}/api/show",
        headers=headers,
        data=json.dumps({"model": model, "verbose": False}),
        timeout=timeout,
    )
    if response.status_code != 200:
        return None

    payload = response.json()
    if not isinstance(payload, dict):
        return None
    return payload


def parse_capabilities(payload):
    """Normalized capabilities of an /api/show answer, or None if absent."""
    capabilities = payload.get("capabilities", [])
    if isinstance(capabilities, list):
        return {
            str(capability).strip().lower()
            for capability in capabilities
            if str(capability).strip()
        }
    return None


def build_think_value(requested_effort, model, capabilities):
    """Construit la valeur du paramètre think pour Ollama."""
    effort = (requested_effort or "none").strip().lower()
    if is_gpt_oss_model(model):
        if effort in OLLAMA_GPT_OSS_THINK_EFFORTS:
            return effort
        # GPT-OSS cannot disable its trace; low is the documented
        # latency-minimizing fallback when the UI asks for "none".
        return "low"

    if (
        capabilities is not None
        and "thinking" not in capabilities
    ):
        return None

    if effort in {"none", "off"}:
        return False

    if effort == "on":
        return True

    # Qwen 3, DeepSeek R1/v3.1 and other Ollama thinking models use the
    # documented boolean switch. Effort strings are GPT-OSS-specific.
    return True if effort in CUSTOM_REASONING_EFFORTS else False


def build_payload(model, full_prompt, image_base64, think_value):
    """Build a non-streamed /api/chat request; images travel as base64."""
    message = {"role": "user", "content": full_prompt}
    if image_base64:
        message["images"] = [image_base64]
    data = {
        "model": model,
        "messages": [message],
        "stream": False,
    }
    if think_value is not None:
        data["think"] = think_value
    return data


def extract_response_parts(response_data):
    """Read the answer and the thinking trace of an /api/chat reply."""
    message = (
        response_data.get("message", {})
        if isinstance(response_data, dict)
        else {}
    )
    content = (
        content_to_text(message.get("content", ""))
        if isinstance(message, dict)
        else ""
    )
    thinking = (
        reasoning_value_to_text(message.get("thinking", ""))
        if isinstance(message, dict)
        else ""
    )
    return normalize_response_parts(content, thinking)
