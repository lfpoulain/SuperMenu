"""Supported OpenAI models and their request capabilities.

This module deliberately has no Qt, keyring, logging, or network side effects.
It is safe to import from configuration, request building, tests, and packaged
smoke checks.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OpenAIModelCapabilities:
    """API capabilities that affect the OpenAI Chat Completions payload."""

    reasoning_efforts: tuple[str, ...]
    default_reasoning_effort: str
    max_tokens_parameter: str = "max_completion_tokens"


OPENAI_MODEL_CAPABILITIES = {
    "gpt-5.6-sol": OpenAIModelCapabilities(
        reasoning_efforts=("none", "low", "medium", "high", "xhigh", "max"),
        default_reasoning_effort="medium",
    ),
    "gpt-5.6-terra": OpenAIModelCapabilities(
        reasoning_efforts=("none", "low", "medium", "high", "xhigh", "max"),
        default_reasoning_effort="medium",
    ),
    "gpt-5.6-luna": OpenAIModelCapabilities(
        reasoning_efforts=("none", "low", "medium", "high", "xhigh", "max"),
        default_reasoning_effort="medium",
    ),
    "gpt-5.4": OpenAIModelCapabilities(
        reasoning_efforts=("none", "low", "medium", "high", "xhigh"),
        default_reasoning_effort="none",
    ),
}
AVAILABLE_MODELS = list(OPENAI_MODEL_CAPABILITIES)
DEFAULT_OPENAI_MODEL = "gpt-5.6-sol"
LEGACY_MODEL_MIGRATIONS = {
    "gpt-5.4-mini": "gpt-5.6-terra",
    "gpt-5-mini": "gpt-5.6-terra",
    "gpt-5.4-nano": "gpt-5.6-luna",
    "gpt-4.1-mini": "gpt-5.6-luna",
    "gpt-5.5": "gpt-5.6-sol",
    "gpt-5.3": "gpt-5.6-sol",
    "gpt-5.2": "gpt-5.6-sol",
    "gpt-5.1": "gpt-5.6-sol",
    "gpt-5": "gpt-5.6-sol",
}
LEGACY_REASONING_EFFORT_MIGRATIONS = {
    "minimal": "low",
    "max": "xhigh",
}


def normalize_openai_model(model_name: str) -> str:
    """Return a supported model, migrating removed persisted choices by role."""
    normalized = model_name.strip().lower() if isinstance(model_name, str) else ""
    if normalized in OPENAI_MODEL_CAPABILITIES:
        return normalized
    return LEGACY_MODEL_MIGRATIONS.get(normalized, DEFAULT_OPENAI_MODEL)


def get_openai_model_capabilities(model_name: str):
    """Return the capability record for an explicitly supported OpenAI model."""
    if not isinstance(model_name, str):
        return None
    return OPENAI_MODEL_CAPABILITIES.get(model_name.strip().lower())


def get_reasoning_efforts_for_model(model_name: str):
    """Return the documented reasoning efforts for a supported model."""
    capabilities = get_openai_model_capabilities(model_name)
    return list(capabilities.reasoning_efforts) if capabilities else []


def get_default_reasoning_effort_for_model(model_name: str) -> str:
    """Return the documented default effort for a supported OpenAI model."""
    capabilities = get_openai_model_capabilities(model_name)
    return capabilities.default_reasoning_effort if capabilities else "none"


def normalize_reasoning_effort(model_name: str, effort: str) -> str:
    """Normalize an effort while preserving compatible legacy intent."""
    capabilities = get_openai_model_capabilities(model_name)
    if not capabilities:
        return "none"

    normalized = effort.strip().lower() if isinstance(effort, str) else ""
    if normalized in capabilities.reasoning_efforts:
        return normalized

    migrated = LEGACY_REASONING_EFFORT_MIGRATIONS.get(normalized)
    if migrated in capabilities.reasoning_efforts:
        return migrated

    return capabilities.default_reasoning_effort
