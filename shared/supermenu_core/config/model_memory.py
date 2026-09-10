"""Model retention preferences shared by speech and text engines."""

MODEL_IDLE_CHOICES = (0, 60, 300, 900, 1800, -1)


def idle_choices(immediate="Après chaque utilisation"):
    return (
        (immediate, 0),
        ("1 minute d’inactivité", 60),
        ("5 minutes d’inactivité (par défaut)", 300),
        ("15 minutes d’inactivité", 900),
        ("30 minutes d’inactivité", 1800),
        ("À la fermeture de SuperMenu", -1),
    )


class TextMemorySettingsMixin:
    def get_text_idle_seconds(self):
        try:
            value = int(self.settings.value("text_idle_seconds", 300))
        except (TypeError, ValueError):
            return 300
        return value if value in MODEL_IDLE_CHOICES else 300

    def set_text_idle_seconds(self, value):
        value = int(value)
        if value not in MODEL_IDLE_CHOICES:
            raise ValueError("Délai de déchargement inconnu")
        self.settings.setValue("text_idle_seconds", value)
