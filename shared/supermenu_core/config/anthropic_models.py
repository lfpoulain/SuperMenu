"""Supported Anthropic (Claude) models and their request capabilities.

Like ``openai_models``, this module has no Qt, keyring, logging, or network
side effects.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AnthropicModelCapabilities:
    """API capabilities that affect the Messages API payload."""

    label: str
    reasoning_efforts: tuple[str, ...]
    default_reasoning_effort: str
    # Whether a request declined by a safety filter can be answered by
    # another Claude model on Anthropic's side (``fallbacks`` parameter).
    server_side_fallback: bool = False
    description: str = ""


# Every model listed here accepts adaptive thinking and the five efforts.
_EFFORTS = ("low", "medium", "high", "xhigh", "max")
# SuperMenu's own default: selected text is rewritten while the user waits,
# so every model starts at the effort the fastest ones use by default.
_DEFAULT_EFFORT = "medium"

# Listed in the order shown to the user.
ANTHROPIC_MODEL_CAPABILITIES = {
    "claude-opus-5-5": AnthropicModelCapabilities(
        label="Claude Opus 5.5",
        reasoning_efforts=_EFFORTS,
        default_reasoning_effort=_DEFAULT_EFFORT,
        server_side_fallback=True,
        description="Modèle recommandé : qualité élevée pour la rédaction.",
    ),
    "claude-sonnet-5-5": AnthropicModelCapabilities(
        label="Claude Sonnet 5.5",
        reasoning_efforts=_EFFORTS,
        default_reasoning_effort=_DEFAULT_EFFORT,
        server_side_fallback=True,
        description="Rapide et polyvalent, moins coûteux qu’Opus.",
    ),
    "claude-haiku-5-5": AnthropicModelCapabilities(
        label="Claude Haiku 5.5",
        reasoning_efforts=_EFFORTS,
        default_reasoning_effort=_DEFAULT_EFFORT,
        description="Le plus rapide et le plus économique.",
    ),
    "claude-fable-5-2": AnthropicModelCapabilities(
        label="Claude Fable 5.2",
        reasoning_efforts=_EFFORTS,
        default_reasoning_effort=_DEFAULT_EFFORT,
        server_side_fallback=True,
        description="Le plus capable, pour les demandes les plus difficiles (le plus coûteux).",
    ),
    "claude-opus-5": AnthropicModelCapabilities(
        label="Claude Opus 5",
        reasoning_efforts=_EFFORTS,
        default_reasoning_effort=_DEFAULT_EFFORT,
        server_side_fallback=True,
        description="Génération précédente d’Opus.",
    ),
    "claude-sonnet-5": AnthropicModelCapabilities(
        label="Claude Sonnet 5",
        reasoning_efforts=_EFFORTS,
        default_reasoning_effort=_DEFAULT_EFFORT,
        description="Génération précédente de Sonnet.",
    ),
    "claude-opus-4-8": AnthropicModelCapabilities(
        label="Claude Opus 4.8",
        reasoning_efforts=_EFFORTS,
        default_reasoning_effort=_DEFAULT_EFFORT,
        description="Dernier modèle de la série Opus 4.",
    ),
}
AVAILABLE_ANTHROPIC_MODELS = list(ANTHROPIC_MODEL_CAPABILITIES)
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"


def normalize_anthropic_model(model_name) -> str:
    """Return a supported Claude model, falling back to the default one."""
    normalized = model_name.strip().lower() if isinstance(model_name, str) else ""
    if normalized in ANTHROPIC_MODEL_CAPABILITIES:
        return normalized
    return DEFAULT_ANTHROPIC_MODEL


def get_anthropic_model_capabilities(model_name):
    """Return the capability record for an explicitly supported Claude model."""
    if not isinstance(model_name, str):
        return None
    return ANTHROPIC_MODEL_CAPABILITIES.get(model_name.strip().lower())


def get_anthropic_model_label(model_name) -> str:
    capabilities = get_anthropic_model_capabilities(model_name)
    return capabilities.label if capabilities else str(model_name or "")


def get_anthropic_model_description(model_name) -> str:
    capabilities = get_anthropic_model_capabilities(model_name)
    return capabilities.description if capabilities else ""


def get_anthropic_reasoning_efforts(model_name):
    capabilities = get_anthropic_model_capabilities(model_name)
    return list(capabilities.reasoning_efforts) if capabilities else []


def get_default_anthropic_reasoning_effort(model_name) -> str:
    capabilities = get_anthropic_model_capabilities(model_name)
    return capabilities.default_reasoning_effort if capabilities else _DEFAULT_EFFORT


def normalize_anthropic_reasoning_effort(model_name, effort) -> str:
    """Return an effort the model accepts.

    Claude models cannot stop reasoning through the effort: "none", "off" and
    "minimal" (other providers, a prompt set to "Sans raisonnement") become
    the lightest effort.
    """
    capabilities = get_anthropic_model_capabilities(model_name)
    efforts = capabilities.reasoning_efforts if capabilities else _EFFORTS
    normalized = effort.strip().lower() if isinstance(effort, str) else ""
    if normalized in efforts:
        return normalized
    if normalized in {"none", "off", "minimal"}:
        return efforts[0]
    return (
        capabilities.default_reasoning_effort if capabilities else _DEFAULT_EFFORT
    )


def supports_server_side_fallback(model_name) -> bool:
    capabilities = get_anthropic_model_capabilities(model_name)
    return bool(capabilities and capabilities.server_side_fallback)


class AnthropicSettingsMixin:
    """Claude model and effort, stored like the other text engines.

    The API key is a secret: each application stores it its own way
    (``get_anthropic_api_key`` / ``set_anthropic_api_key``).
    """

    def get_anthropic_model(self) -> str:
        return normalize_anthropic_model(
            self.settings.value("anthropic_model", DEFAULT_ANTHROPIC_MODEL)
        )

    def set_anthropic_model(self, model) -> None:
        self.settings.setValue("anthropic_model", normalize_anthropic_model(model))

    def get_anthropic_reasoning_effort(self, model=None) -> str:
        """Read the effort for ``model`` without ever rewriting the setting."""
        selected = normalize_anthropic_model(model or self.get_anthropic_model())
        return normalize_anthropic_reasoning_effort(
            selected,
            self.settings.value(
                "anthropic_reasoning_effort",
                get_default_anthropic_reasoning_effort(selected),
            ),
        )

    def set_anthropic_reasoning_effort(self, effort, model=None) -> None:
        selected = normalize_anthropic_model(model or self.get_anthropic_model())
        self.settings.setValue(
            "anthropic_reasoning_effort",
            normalize_anthropic_reasoning_effort(selected, effort),
        )
