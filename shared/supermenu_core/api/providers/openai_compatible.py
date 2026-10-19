#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""OpenAI chat completions, also spoken by generic custom endpoints."""

from supermenu_core.api.providers.common import (
    chat_completion_parts,
    content_to_text,
    extract_reasoning_text,
    normalize_response_parts,
)
from supermenu_core.config.openai_models import (
    get_openai_model_capabilities,
    normalize_reasoning_effort,
)

# Generic OpenAI-compatible servers reject prompt + max_tokens above their
# context window, so their cap stays conservative.
DEFAULT_MAX_TOKENS = 2048
# OpenAI's max_completion_tokens also counts reasoning tokens: 2048 was spent
# by the reasoning alone at the default effort, leaving an empty or cut answer.
OPENAI_MAX_COMPLETION_TOKENS = 16384

OPENAI_TRUNCATION_MESSAGE = (
    "La réponse a été interrompue avant la fin (limite de longueur "
    "atteinte). Réduisez le texte ou le niveau de raisonnement, "
    "puis réessayez."
)


def custom_truncation_message():
    """Explain a cutoff by a generic server in terms of SuperMenu's own cap."""
    # The cap is SuperMenu's own (see DEFAULT_MAX_TOKENS), and servers
    # that expose a reasoning trace count it in the same budget.
    return (
        "Le serveur a interrompu la réponse avant la fin : SuperMenu "
        f"limite la réponse à {DEFAULT_MAX_TOKENS} tokens sur ce type "
        "de serveur, raisonnement du modèle compris (ou le contexte du "
        "modèle est plein). Réduisez le texte ou utilisez un modèle "
        "sans raisonnement, puis réessayez."
    )


def _chat_messages_payload(model, prompt, full_prompt, image_data_url):
    if image_data_url:
        return {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_url},
                        },
                    ],
                }
            ],
        }
    return {
        "model": model,
        "messages": [{"role": "user", "content": full_prompt}],
    }


def build_openai_payload(model, prompt, full_prompt, image_data_url, read_effort):
    """Build a request for OpenAI itself.

    ``read_effort`` is only called once the model is known to be supported:
    an unsupported model never reads (nor normalizes) the effort setting.
    """
    data = _chat_messages_payload(model, prompt, full_prompt, image_data_url)
    capabilities = get_openai_model_capabilities(model)
    if capabilities is None:
        raise ValueError(f"Modèle OpenAI non supporté: {model}")

    data[capabilities.max_tokens_parameter] = (
        OPENAI_MAX_COMPLETION_TOKENS
        if capabilities.max_tokens_parameter == "max_completion_tokens"
        else DEFAULT_MAX_TOKENS
    )
    effort = normalize_reasoning_effort(
        model,
        read_effort(),
    )
    data["reasoning_effort"] = effort
    return data


def build_custom_payload(model, prompt, full_prompt, image_data_url):
    """Build a request for a generic OpenAI-compatible endpoint."""
    data = _chat_messages_payload(model, prompt, full_prompt, image_data_url)
    data["max_tokens"] = DEFAULT_MAX_TOKENS
    return data


def extract_response_parts(response_data):
    """Read output_text, output items or the first chat-completions choice."""
    if isinstance(response_data, dict) and response_data.get("output_text"):
        return normalize_response_parts(
            content_to_text(response_data.get("output_text")),
            extract_reasoning_text(response_data),
        )

    if isinstance(response_data, dict) and isinstance(
        response_data.get("output"), list
    ):
        parts = []
        for output_item in response_data.get("output", []):
            if not isinstance(output_item, dict):
                continue
            for content_item in output_item.get("content", []) or []:
                if isinstance(content_item, dict):
                    text = content_item.get("text") or content_item.get("content")
                    if isinstance(text, str):
                        parts.append(text)
        return normalize_response_parts(
            "\n".join(parts),
            extract_reasoning_text(response_data),
        )

    return chat_completion_parts(response_data)
