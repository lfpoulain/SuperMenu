#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Helpers shared by the local-model client and its settings UI."""

import re

_REASONING_OPTION_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


def normalize_reasoning_option(value, default=None):
    """Return a safe provider option without imposing a static model list."""
    normalized = str(value or "").strip().lower()
    if _REASONING_OPTION_RE.fullmatch(normalized):
        return normalized
    return default


def normalize_reasoning_options(values):
    """Normalize and deduplicate advertised options while preserving order."""
    if not isinstance(values, (list, tuple, set)):
        return []

    normalized = []
    for value in values:
        option = normalize_reasoning_option(value)
        if option and option not in normalized:
            normalized.append(option)
    return normalized


def choose_reasoning_option(options, preferred=None, default=None):
    """Choose the closest native option when switching between model types."""
    allowed = normalize_reasoning_options(options)
    if not allowed:
        return None

    preferred = normalize_reasoning_option(preferred)
    default = normalize_reasoning_option(default)

    if preferred in allowed:
        return preferred

    if preferred in {"none", "off"}:
        for disabled in ("off", "none"):
            if disabled in allowed:
                return disabled

    if preferred in {"on", "low", "medium", "high", "xhigh", "max"}:
        if "on" in allowed:
            return "on"

    if default in allowed:
        return default

    if preferred in {"none", "off"} and "low" in allowed:
        return "low"

    return allowed[0]


def parse_lmstudio_model_catalog(payload):
    """Extract model IDs and native reasoning controls from LM Studio's catalog."""
    if not isinstance(payload, dict):
        return []
    models = payload.get("models")
    if not isinstance(models, list):
        return []

    parsed = []
    for model_info in models:
        if not isinstance(model_info, dict):
            continue

        identifiers = []
        for key in ("key", "id", "name", "display_name"):
            identifier = model_info.get(key)
            if identifier and identifier not in identifiers:
                identifiers.append(identifier)
        for instance in model_info.get("loaded_instances", []) or []:
            if not isinstance(instance, dict):
                continue
            for key in ("id", "model_key"):
                identifier = instance.get(key)
                if identifier and identifier not in identifiers:
                    identifiers.append(identifier)

        if not identifiers:
            continue

        capabilities = model_info.get("capabilities")
        reasoning = (
            capabilities.get("reasoning") if isinstance(capabilities, dict) else None
        )
        if isinstance(reasoning, dict):
            options = normalize_reasoning_options(reasoning.get("allowed_options"))
            reasoning_supported = bool(options)
            reasoning_default = normalize_reasoning_option(reasoning.get("default"))
            if reasoning_default not in options:
                reasoning_default = options[0] if options else None
        else:
            options = []
            reasoning_supported = False
            reasoning_default = None

        parsed.append(
            {
                "id": identifiers[0],
                "identifiers": identifiers,
                "reasoning_supported": reasoning_supported,
                "reasoning_options": options,
                "reasoning_default": reasoning_default,
            }
        )
    return parsed
