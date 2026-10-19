#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""LM Studio native REST API, its pre-0.4 compatible fallback and LM Link routing."""

import json
import logging

import requests

from supermenu_core.api.model_capabilities import (
    choose_reasoning_option,
    parse_lmstudio_model_catalog,
)
from supermenu_core.api.providers.common import (
    chat_completion_parts,
    content_to_text,
    is_gpt_oss_model,
    log,
    normalize_response_parts,
    reasoning_value_to_text,
)

TRUNCATION_MESSAGE = (
    "LM Studio a interrompu la réponse car la fenêtre de "
    "contexte du modèle est pleine. Rechargez le modèle avec "
    "un Context Length plus élevé, puis réessayez."
)


def request_model_catalog(session, base_url, headers, timeout):
    """Read the native /api/v1/models catalog; None when it is unreadable.

    Transport and JSON errors propagate: the caller counts them, like an
    unreadable answer, as a failed probe.
    """
    response = session.get(
        f"{base_url}/api/v1/models",
        headers=headers,
        timeout=timeout,
    )
    if response.status_code != 200:
        return None

    payload = response.json()
    if not isinstance(payload, dict):
        return None
    return payload


def find_catalog_model(payload, model):
    """Return the catalog entry known under the model's identifier, or None."""
    for model_details in parse_lmstudio_model_catalog(payload):
        if model in model_details["identifiers"]:
            return model_details
    return None


def build_reasoning_value(requested_effort, supported, options, default):
    """Translate SuperMenu's effort into the selected model's native option."""
    requested = (requested_effort or "none").strip().lower()

    if supported is False:
        return None

    if not options:
        return "off" if requested in {"none", "off"} else requested

    return choose_reasoning_option(
        options,
        preferred=requested,
        default=default,
    )


def build_payload(model, prompt, full_prompt, image_data_url, reasoning):
    """Build a native /api/v1/chat request that LM Studio does not store."""
    native_input = full_prompt
    if image_data_url:
        native_input = [
            {"type": "message", "content": prompt},
            {"type": "image", "data_url": image_data_url},
        ]
    data = {
        "model": model,
        "input": native_input,
        "stream": False,
        "store": False,
    }
    if reasoning:
        data["reasoning"] = reasoning
        log(
            f"LM Studio: raisonnement '{reasoning}' envoyé au modèle "
            f"'{model}'.",
            logging.INFO,
        )
    return data


def build_compat_data(native_data, model, requested_effort):
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
                    content_parts.append({"type": "text", "text": text_content})
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
        "model": native_data.get("model", model),
        "messages": [{"role": "user", "content": message_content}],
        # LM Studio's compatible API uses -1 for no artificial output cap.
        "max_tokens": -1,
    }
    effort = (requested_effort or "none").strip().lower()
    if effort in {"low", "medium", "high"}:
        data["reasoning"] = {"effort": effort}
    elif is_gpt_oss_model(model):
        data["reasoning"] = {"effort": "low"}
    return data


def targeted_completion_response(base_url, api_key, data, device, *, cancelled, timeout):
    """Run an LM Link completion on one device and wrap it as an HTTP 200."""
    # Resolved at call time, as before: the WebSocket transport is only
    # imported for LM Link routing, and tests patch it on its module.
    from ..lmstudio_transport import targeted_completion
    result = targeted_completion(
        base_url,
        api_key,
        data, device, cancelled=cancelled,
        include_reasoning=True, timeout=timeout,
    )
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps(result).encode("utf-8")
    return response


def extract_response_parts(response_data):
    """Read native output items, or a compatible chat-completions reply."""
    output = (
        response_data.get("output", [])
        if isinstance(response_data, dict)
        else []
    )
    if isinstance(output, list) and output:
        messages = []
        reasoning_parts = []
        for item in output:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type", "")).lower()
            item_text = content_to_text(
                item.get("content", item.get("text", ""))
            )
            if item_type == "message" and item_text:
                messages.append(item_text)
            elif item_type == "reasoning":
                reasoning_text = reasoning_value_to_text(
                    item.get("content", item.get("text", ""))
                )
                if reasoning_text:
                    reasoning_parts.append(reasoning_text)
        return normalize_response_parts(
            "\n".join(messages),
            "\n\n".join(reasoning_parts),
        )

    return chat_completion_parts(response_data)
