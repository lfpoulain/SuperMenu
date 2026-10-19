"""Voice settings are independent of text-provider settings."""

import re
import sys

from supermenu_core.config.model_memory import MODEL_IDLE_CHOICES

NEMOTRON_MODEL = "nemotron-3.5-asr-streaming-0.6b"
OPENAI_SPEECH_MODEL = "gpt-live-transcribe"
MAX_DICTATION_SECONDS = 300


def languages(value):
    values = re.split(r"[\s,;]+", value) if isinstance(value, str) else value or []
    result = []
    for value in values:
        code = str(value).strip().lower()
        if not code:
            continue
        if not re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2})?", code):
            raise ValueError("Utilisez des codes de langue comme fr, en ou fr-ca.")
        if code not in result:
            result.append(code)
    return result


def local_language(value, provider):
    codes = languages(value)
    if provider == "apple":
        if len(codes) != 1:
            raise ValueError("Apple Speech nécessite une langue, par exemple fr ou en.")
        return codes[0]
    if len(codes) > 1:
        raise ValueError(
            "Pour Nemotron, choisissez une langue ou laissez vide pour la détection automatique."
        )
    return codes[0] if codes else "auto"


class SpeechSettingsMixin:
    def get_dictation_hotkey(self):
        return str(self.settings.value("dictation_hotkey", "") or "")

    def set_dictation_hotkey(self, value):
        self.settings.setValue("dictation_hotkey", str(value or "").strip())

    def get_dictation_hotkey_mode(self):
        value = self.settings.value("dictation_hotkey_mode", "press")
        return value if value in {"press", "hold"} else "press"

    def set_dictation_hotkey_mode(self, value):
        if value not in {"press", "hold"}:
            raise ValueError("Mode de raccourci inconnu")
        self.settings.setValue("dictation_hotkey_mode", value)

    def get_dictation_auto_insert(self):
        return self.settings.value("dictation_auto_insert", False, type=bool)

    def set_dictation_auto_insert(self, value):
        self.settings.setValue("dictation_auto_insert", bool(value))

    def get_dictation_correct_before_insert(self):
        return self.settings.value("dictation_correct_before_insert", False, type=bool)

    def set_dictation_correct_before_insert(self, value):
        self.settings.setValue("dictation_correct_before_insert", bool(value))

    def get_speech_idle_seconds(self):
        try:
            value = int(self.settings.value("speech_idle_seconds", 300))
        except (TypeError, ValueError):
            return 300
        return value if value in MODEL_IDLE_CHOICES else 300

    def set_speech_idle_seconds(self, value):
        value = int(value)
        if value not in MODEL_IDLE_CHOICES:
            raise ValueError("Délai de déchargement inconnu")
        self.settings.setValue("speech_idle_seconds", value)

    def get_speech_provider(self):
        value = str(self.settings.value("speech_provider", "openai"))
        return value if value in {"openai", "apple", "foundry"} else "openai"

    def set_speech_provider(self, value):
        if value not in {"openai", "apple", "foundry"}:
            raise ValueError("Moteur vocal inconnu")
        self.settings.setValue("speech_provider", value)

    def get_speech_device(self):
        return (
            "cpu" if self.settings.value("speech_device", "auto") == "cpu" else "auto"
        )

    def set_speech_device(self, value):
        self.settings.setValue("speech_device", "cpu" if value == "cpu" else "auto")

    def get_speech_microphone(self):
        return str(self.settings.value("speech_microphone", "") or "")

    def set_speech_microphone(self, value):
        self.settings.setValue("speech_microphone", str(value or ""))

    def get_transcription_languages(self):
        return str(self.settings.value("transcription_languages", "fr") or "")

    def set_transcription_languages(self, value):
        self.settings.setValue("transcription_languages", str(value).strip())

    def get_transcription_prompt(self):
        return str(self.settings.value("transcription_prompt", "") or "")

    def set_transcription_prompt(self, value):
        self.settings.setValue("transcription_prompt", str(value).strip())

    def get_transcription_keywords(self):
        return str(self.settings.value("transcription_keywords", "") or "")

    def set_transcription_keywords(self, value):
        self.settings.setValue("transcription_keywords", str(value).strip())


def speech_options(settings):
    provider = settings.get_speech_provider()
    if provider == "apple" and sys.platform != "darwin":
        raise ValueError("Apple Speech est disponible uniquement sur Mac.")
    if provider == "foundry" and sys.platform != "win32":
        raise ValueError("Foundry Local vocal est disponible uniquement sur Windows.")
    expected = settings.get_transcription_languages()
    return {
        "provider": provider,
        "language": local_language(expected, provider) if provider != "openai" else "",
        "languages": languages(expected),
        "device": settings.get_speech_device(),
        "microphone": settings.get_speech_microphone(),
        "prompt": settings.get_transcription_prompt(),
        "keywords": [
            s.strip()
            for s in re.split(r"[,\n]", settings.get_transcription_keywords())
            if s.strip()
        ],
    }
