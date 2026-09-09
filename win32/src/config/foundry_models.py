"""The two local models offered by the Windows beta."""

FOUNDRY_MODELS = {
    "qwen3.5-4b": {"label": "Qwen3.5 4B — léger", "ram_gb": 16},
    "qwen3.5-9b": {"label": "Qwen3.5 9B — qualité", "ram_gb": 24},
}
DEFAULT_FOUNDRY_MODEL = "qwen3.5-4b"
MAX_INPUT_CHARS = 16000


def normalize_foundry_model(value):
    return value if value in FOUNDRY_MODELS else DEFAULT_FOUNDRY_MODEL
