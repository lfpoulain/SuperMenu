#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Helpers shared by the OpenAI, Ollama and LM Studio paths."""

import logging

from supermenu_core.utils.thinking import split_inline_thinking

logger = logging.getLogger("SuperMenu.core.api")


def log(message, level=logging.INFO):
    """Log without coupling the shared core to a platform logger."""
    logger.log(level, message)


def models_base_url(endpoint_url, is_ollama, lmstudio=False):
    base = (endpoint_url or "").rstrip("/")
    if is_ollama:
        if base.endswith("/api/chat"):
            return base[: -len("/api/chat")]
        if base.endswith("/api"):
            return base[: -len("/api")]
        return base

    if lmstudio:
        # Longest suffixes first: ".../api/v1" also ends with "/v1", which
        # used to leave ".../api" as the server root.
        suffixes = (
            "/api/v1/chat",
            "/api/v1/models",
            "/api/v1",
            "/v1/chat/completions",
            "/v1/models",
            "/v1",
        )
    else:
        # Generic OpenAI-compatible servers may legitimately live under
        # "/api/v1" (their catalog is then ".../api/v1/models").
        suffixes = (
            "/api/v1/chat",
            "/api/v1/models",
            "/v1/chat/completions",
            "/v1/models",
            "/v1",
        )
    for suffix in suffixes:
        if base.endswith(suffix):
            return base[: -len(suffix)]
    return base


def is_gpt_oss_model(model_name):
    return "gpt-oss" in str(model_name or "").lower()


def combine_thinking(content, thinking):
    """Combine le raisonnement et la réponse pour l'affichage."""
    parts = []
    if thinking:
        parts.append(f"<think>{thinking}</think>")
    if content:
        parts.append(content)

    if not parts:
        return content or thinking or ""

    return "\n\n".join(parts)


def strip_inline_thinking(text):
    """Supprime les blocs de raisonnement inclus dans le contenu final."""
    visible, _reasoning = split_inline_thinking(text)
    return visible


def normalize_response_parts(content, reasoning):
    """Normalize provider quirks and keep a usable answer when only one channel exists."""
    visible_content, inline_reasoning = split_inline_thinking(content)
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


def content_to_text(content):
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


def reasoning_value_to_text(value):
    """Normalise un champ de raisonnement qui peut etre str, dict ou list."""
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        for nested_key in (
            "text",
            "content",
            "summary",
            "reasoning_content",
            "value",
        ):
            nested_value = reasoning_value_to_text(value.get(nested_key))
            if nested_value:
                return nested_value
        return ""

    if isinstance(value, list):
        parts = []
        for item in value:
            item_text = reasoning_value_to_text(item)
            if item_text:
                parts.append(item_text)
        return "\n\n".join(parts)

    return ""


def extract_reasoning_text(response_data):
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
            value = reasoning_value_to_text(item.get(key))
            if value:
                return value

    return ""


def chat_completion_parts(response_data):
    """Read the first chat-completions choice used by OpenAI-compatible APIs."""
    choices = (
        response_data.get("choices", []) if isinstance(response_data, dict) else []
    )
    if not choices:
        return normalize_response_parts(
            "",
            extract_reasoning_text(response_data),
        )

    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = (
        content_to_text(message.get("content", ""))
        if isinstance(message, dict)
        else ""
    )
    reasoning = extract_reasoning_text(response_data)
    return normalize_response_parts(content, reasoning)


def response_was_truncated(response_data):
    """Detect explicit server-side token/context cutoffs."""
    if not isinstance(response_data, dict):
        return False

    reasons = [
        response_data.get("finish_reason"),
        response_data.get("stop_reason"),
        # Ollama's native /api/chat reports its cutoff here.
        response_data.get("done_reason"),
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
    incomplete = response_data.get("incomplete_details")
    if isinstance(incomplete, dict):
        reasons.append(incomplete.get("reason"))

    cutoff_markers = ("length", "max_token", "max_output", "context")
    return any(
        any(marker in str(reason).lower() for marker in cutoff_markers)
        for reason in reasons
        if reason
    )
