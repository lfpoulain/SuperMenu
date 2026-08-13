"""Provider-level settings shared by the desktop applications."""

CUSTOM_REASONING_EFFORTS = ("none", "low", "medium", "high")
OLLAMA_GPT_OSS_THINK_EFFORTS = ("low", "medium", "high")
UPDATE_CHANNELS = ("stable", "beta")


def normalize_update_channel(value) -> str:
    """Return a supported update channel, defaulting safely to stable."""
    normalized = str(value or "").strip().lower()
    return normalized if normalized in UPDATE_CHANNELS else "stable"
