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
    description: str = ""


# Effort ladders documented on each model page.
_ALL_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
# These models always reason: the API rejects "none".
_ALWAYS_REASONING = ("low", "medium", "high", "xhigh", "max")
_UP_TO_XHIGH = ("none", "low", "medium", "high", "xhigh")

# Listed in the order shown to the user: newest family first, then by tier.
OPENAI_MODEL_CAPABILITIES = {
    "gpt-6.2-astra": OpenAIModelCapabilities(
        reasoning_efforts=_ALWAYS_REASONING,
        default_reasoning_effort="medium",
        description="Le plus capable : raisonnement complexe (le plus coûteux).",
    ),
    "gpt-6.2-sol": OpenAIModelCapabilities(
        reasoning_efforts=_ALWAYS_REASONING,
        default_reasoning_effort="medium",
        description="Polyvalent : bon équilibre entre qualité et coût.",
    ),
    "gpt-6.1-terra": OpenAIModelCapabilities(
        reasoning_efforts=_ALL_EFFORTS,
        default_reasoning_effort="medium",
        description="Rapide et efficace, rédaction naturelle.",
    ),
    "gpt-6-luna": OpenAIModelCapabilities(
        reasoning_efforts=_ALL_EFFORTS,
        default_reasoning_effort="medium",
        description="Le plus économique et le plus rapide.",
    ),
    "gpt-6.1-sol": OpenAIModelCapabilities(
        reasoning_efforts=_ALWAYS_REASONING,
        default_reasoning_effort="medium",
        description="Génération précédente du modèle polyvalent.",
    ),
    "gpt-6-sol": OpenAIModelCapabilities(
        reasoning_efforts=_ALL_EFFORTS,
        default_reasoning_effort="medium",
        description="Premier modèle polyvalent de la famille GPT-6.",
    ),
    "gpt-6-astra": OpenAIModelCapabilities(
        reasoning_efforts=_ALWAYS_REASONING,
        default_reasoning_effort="medium",
        description="Premier modèle haut de gamme de la famille GPT-6.",
    ),
    "gpt-5.6-sol": OpenAIModelCapabilities(
        reasoning_efforts=_ALL_EFFORTS,
        default_reasoning_effort="medium",
        description="Haut de gamme de la famille GPT-5.6.",
    ),
    "gpt-5.6-terra": OpenAIModelCapabilities(
        reasoning_efforts=_ALL_EFFORTS,
        default_reasoning_effort="medium",
        description="Équilibre entre qualité et coût (GPT-5.6).",
    ),
    "gpt-5.6-luna": OpenAIModelCapabilities(
        reasoning_efforts=_ALL_EFFORTS,
        default_reasoning_effort="medium",
        description="Rapide et économique (GPT-5.6).",
    ),
    "gpt-5.5": OpenAIModelCapabilities(
        reasoning_efforts=_UP_TO_XHIGH,
        default_reasoning_effort="medium",
        description="Génération précédente.",
    ),
    "gpt-5.4": OpenAIModelCapabilities(
        reasoning_efforts=_UP_TO_XHIGH,
        default_reasoning_effort="none",
        description="Génération précédente, sans raisonnement par défaut.",
    ),
    "gpt-5.4-mini": OpenAIModelCapabilities(
        reasoning_efforts=_UP_TO_XHIGH,
        default_reasoning_effort="none",
        description="Petit modèle rapide, sans raisonnement par défaut.",
    ),
    "gpt-5.2": OpenAIModelCapabilities(
        reasoning_efforts=_UP_TO_XHIGH,
        default_reasoning_effort="none",
        description="Ancien modèle, sans raisonnement par défaut.",
    ),
}
AVAILABLE_MODELS = list(OPENAI_MODEL_CAPABILITIES)
DEFAULT_OPENAI_MODEL = "gpt-5.6-sol"
# Models OpenAI has shut down or is retiring: a saved choice moves to the
# model of the same tier instead of failing at the first request.
LEGACY_MODEL_MIGRATIONS = {
    "gpt-5-mini": "gpt-5.6-terra",
    "o4-mini": "gpt-5.6-terra",
    "gpt-5.4-nano": "gpt-5.6-luna",
    "gpt-5-nano": "gpt-5.6-luna",
    "gpt-4.1-mini": "gpt-5.6-luna",
    "gpt-4.1-nano": "gpt-5.6-luna",
    "gpt-4o-mini": "gpt-5.6-luna",
    "gpt-5.3": "gpt-5.6-sol",
    "gpt-5.1": "gpt-5.6-sol",
    "gpt-5": "gpt-5.6-sol",
    "gpt-4.1": "gpt-5.6-sol",
    "gpt-4o": "gpt-5.6-sol",
    "o3": "gpt-5.6-sol",
}
# Tried in order: the first effort the model supports wins.
LEGACY_REASONING_EFFORT_MIGRATIONS = {
    "minimal": ("low",),
    "max": ("xhigh",),
    # A model that always reasons gets its lightest effort, not its default.
    "none": ("low",),
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


def get_openai_model_description(model_name: str) -> str:
    """Return the one-line description shown next to a model, if any."""
    capabilities = get_openai_model_capabilities(model_name)
    return capabilities.description if capabilities else ""


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

    for migrated in LEGACY_REASONING_EFFORT_MIGRATIONS.get(normalized, ()):
        if migrated in capabilities.reasoning_efforts:
            return migrated

    return capabilities.default_reasoning_effort
