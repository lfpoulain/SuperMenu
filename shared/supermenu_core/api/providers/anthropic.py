#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Anthropic Messages API (Claude models)."""

import json
import threading

from supermenu_core.config.anthropic_models import (
    normalize_anthropic_reasoning_effort,
    supports_server_side_fallback,
)

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2026-10-21"
# Lets Anthropic answer with another Claude model when a safety filter
# declines the request, instead of returning the refusal.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# The cap also counts the model's reasoning. Requests are not streamed, so it
# stays well below the models' 128K limit to finish within the read timeout.
MAX_TOKENS = 16000

TRUNCATION_MESSAGE = (
    "Claude a interrompu la réponse avant la fin (limite de longueur "
    "atteinte, raisonnement compris). Réduisez le texte ou le niveau de "
    "raisonnement, puis réessayez."
)

_REFUSAL_CATEGORIES = {
    "cyber": "cybersécurité",
    "bio": "biologie",
}

# Set once the API rejects the fallback option (beta retired, or not offered
# to this organization): later requests skip it instead of failing twice.
_fallbacks_rejected = threading.Event()


def fallbacks_enabled(model):
    return supports_server_side_fallback(model) and not _fallbacks_rejected.is_set()


def reset_fallbacks():
    """Offer the fallback option again (another key may accept it)."""
    _fallbacks_rejected.clear()


def build_headers(api_key):
    """Headers for api.anthropic.com; the key is never sent anywhere else."""
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": API_VERSION,
    }
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def request_headers(headers, data):
    """Add the beta header a request needs when it carries ``fallbacks``."""
    if uses_fallbacks(data):
        return {**headers, "anthropic-beta": FALLBACK_BETA}
    return headers


def _image_block(image_data_url):
    header, _separator, data = image_data_url.partition(";base64,")
    media_type = header[len("data:"):] if header.startswith("data:") else "image/png"
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def build_payload(model, prompt, full_prompt, image_data_url, effort):
    """Build a Messages request.

    ``effort`` is SuperMenu's resolved effort. "none" (a prompt set to "Sans
    raisonnement") asks for the lightest effort and no reasoning summary:
    current Claude models do not accept a request that disables thinking.
    """
    if image_data_url:
        content = [_image_block(image_data_url), {"type": "text", "text": prompt}]
    else:
        content = full_prompt
    requested = str(effort or "").strip().lower()
    data = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": content}],
        "output_config": {
            "effort": normalize_anthropic_reasoning_effort(model, requested)
        },
    }
    if requested not in {"none", "off"}:
        # The summary is what the response window can show as reasoning.
        data["thinking"] = {"type": "adaptive", "display": "summarized"}
    if fallbacks_enabled(model):
        data["fallbacks"] = "default"
    return data


def uses_fallbacks(data):
    return isinstance(data, dict) and "fallbacks" in data


def fallbacks_were_rejected(status_code, body_text):
    """Whether a 400 answer complains about the fallback option itself."""
    if status_code != 400:
        return False
    text = str(body_text or "").lower()
    return "fallback" in text or "anthropic-beta" in text


def without_fallbacks(data):
    """Remember the rejection and return the same request without the option."""
    _fallbacks_rejected.set()
    plain = dict(data)
    plain.pop("fallbacks", None)
    return plain


def extract_response_parts(response_data):
    """Return (answer, reasoning summary) from a Messages response.

    A response without any text block has no answer: its reasoning summary is
    never promoted to an answer that could be pasted.
    """
    blocks = response_data.get("content") if isinstance(response_data, dict) else None
    if not isinstance(blocks, list):
        return "", ""
    text_parts, reasoning_parts = [], []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            text_parts.append(block["text"])
        elif block.get("type") == "thinking":
            thinking = block.get("thinking")
            if isinstance(thinking, str) and thinking.strip():
                reasoning_parts.append(thinking.strip())
    text = "".join(text_parts).strip()
    if not text:
        return "", ""
    return text, "\n\n".join(reasoning_parts)


def refusal_message(response_data):
    """Explain a declined request, or return None when Claude answered."""
    if not isinstance(response_data, dict):
        return None
    if response_data.get("stop_reason") != "refusal":
        return None
    details = response_data.get("stop_details")
    category = details.get("category") if isinstance(details, dict) else None
    topic = _REFUSAL_CATEGORIES.get(category)
    reason = f" (filtre de sécurité : {topic})" if topic else ""
    return (
        f"Claude a refusé de traiter cette demande{reason}. Reformulez le "
        "texte ou choisissez un autre modèle dans Réglages > Texte."
    )


def error_message(status_code, body_text):
    """Turn an API error into a message the user can act on."""
    detail = ""
    try:
        payload = json.loads(body_text)
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            detail = error["message"].strip()
    except (TypeError, ValueError):
        pass
    detail = detail or str(body_text or "").strip()
    suffix = f" Détail : {detail}" if detail else ""
    if status_code == 401:
        return (
            "Anthropic a refusé la clé API. Vérifiez-la dans Réglages > Texte."
            + suffix
        )
    if status_code == 402:
        return "Anthropic signale un problème de facturation sur ce compte." + suffix
    if status_code == 403:
        return "Cette clé API Anthropic n’a pas accès à ce modèle ou à cette région." + suffix
    if status_code == 404:
        return "Ce modèle Claude n’est pas disponible pour cette clé API." + suffix
    if status_code == 413:
        return "Le texte envoyé à Anthropic est trop volumineux." + suffix
    if status_code == 429:
        return (
            "Limite de débit ou plafond de dépense Anthropic atteint. "
            "Réessayez dans un instant." + suffix
        )
    if status_code in {500, 529}:
        return (
            "Le service Anthropic est momentanément surchargé. Réessayez "
            "dans un instant." + suffix
        )
    return f"Erreur {status_code} renvoyée par Anthropic." + suffix
