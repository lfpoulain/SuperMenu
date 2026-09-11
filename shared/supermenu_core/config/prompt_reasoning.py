"""Request-scoped reasoning preference, independent of response visibility."""

REASONING_CHOICES = (
    ("Réglage du moteur", "default"),
    ("Sans raisonnement", "off"),
    ("Avec raisonnement", "on"),
)


def normalize_reasoning_mode(value):
    if not isinstance(value, str) or value not in {"default", "off", "on"}:
        raise ValueError("Mode de raisonnement du prompt inconnu.")
    return value


def resolve_reasoning_effort(current, mode="default"):
    mode = normalize_reasoning_mode(mode)
    if mode == "default":
        return current
    if mode == "off":
        return "none"
    return current if current and current not in {"none", "off"} else "medium"
