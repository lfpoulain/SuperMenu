"""Apple Speech and OpenAI share the same live dictation interface."""

import platform
import sys
from pathlib import Path

from supermenu_core.audio.backends import OpenAISpeechBackend, ProcessSpeechBackend
from supermenu_core.audio.resident import ResidentSpeechBackend
from src.utils.paths import resource_path


def create_speech_backend(settings, options):
    if options["provider"] == "openai":
        return OpenAISpeechBackend(
            options.get("api_key", settings.get_api_key()), options
        )
    if options["provider"] != "apple":
        raise ValueError("Ce moteur vocal n’est pas disponible sur macOS.")
    version = platform.mac_ver()[0].split(".")[0]
    if sys.platform != "darwin" or not version.isdigit() or int(version) < 26:
        raise ValueError(
            "La dictée locale Apple Speech nécessite macOS 26 ou une version ultérieure."
        )
    parts = (
        ("native", "SuperMenuSpeech")
        if getattr(sys, "frozen", False)
        else ("build", "native", "SuperMenuSpeech")
    )
    helper = Path(resource_path(*parts))
    if not helper.is_file():
        raise ValueError("Le composant vocal Apple manque. Réinstallez la bêta macOS.")
    if options.get("action", "start") in {"probe", "download"}:
        return ProcessSpeechBackend((str(helper), []), options)
    return ResidentSpeechBackend(
        (str(helper), []), options, settings.get_speech_idle_seconds()
    )
