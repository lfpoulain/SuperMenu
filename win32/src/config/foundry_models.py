"""The two local models offered by the Windows beta."""

from supermenu_core.config.model_target import register_foundry_models

FOUNDRY_MODELS = {
    "qwen3.5-4b": {"label": "Qwen3.5 4B — léger", "ram_gb": 16},
    "qwen3.5-9b": {"label": "Qwen3.5 9B — qualité", "ram_gb": 24},
}
DEFAULT_FOUNDRY_MODEL = "qwen3.5-4b"
MAX_INPUT_CHARS = 16000

# Single source of truth: the shared prompt editor and per-prompt routing read
# this catalogue without importing Windows code.
register_foundry_models(FOUNDRY_MODELS)


def normalize_foundry_model(value):
    return value if value in FOUNDRY_MODELS else DEFAULT_FOUNDRY_MODEL
