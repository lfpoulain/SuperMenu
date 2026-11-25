"""Apple Speech and OpenAI share the same live dictation interface."""

import sys
from pathlib import Path

from supermenu_core.audio.backends import OpenAISpeechBackend, ProcessSpeechBackend
from supermenu_core.audio.resident import ResidentSpeechBackend
from supermenu_core.config.feature_modes import effective_speech_idle_seconds
from src.utils.paths import resource_path
from src.utils.system_version import macos_major_version


def create_speech_backend(settings, options):
    if options["provider"] == "openai":
        return OpenAISpeechBackend(
            options.get("api_key", settings.get_api_key()), options
        )
    if options["provider"] != "apple":
        raise ValueError("Ce moteur vocal n’est pas disponible sur macOS.")
    if sys.platform != "darwin" or macos_major_version() < 26:
        raise ValueError(
            "La dictée locale Apple Speech nécessite macOS 26 ou une version ultérieure."
        )
    frozen = getattr(sys, "frozen", False)
    parts = (
        ("native", "SuperMenuSpeech")
        if frozen
        else ("build", "native", "SuperMenuSpeech")
    )
    helper = Path(resource_path(*parts))
    if not helper.is_file():
        if frozen:
            raise ValueError(
                "Le composant vocal Apple manque dans cette installation. Réinstallez SuperMenu."
            )
        raise ValueError(
            "Le composant vocal Apple n’est pas compilé. Lancez "
            "« bash scripts/build_speech_helper.sh » depuis le dossier macos."
        )
    if options.get("action", "start") in {"probe", "download"}:
        return ProcessSpeechBackend((str(helper), []), options)
    # The saved delay applies with the advanced features only; it is kept.
    return ResidentSpeechBackend(
        (str(helper), []), options, effective_speech_idle_seconds(settings)
    )
