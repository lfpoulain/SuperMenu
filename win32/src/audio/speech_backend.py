from supermenu_core.audio.backends import OpenAISpeechBackend, ProcessSpeechBackend
from supermenu_core.audio.resident import ResidentSpeechBackend
from src.api.foundry_client import worker_command


def create_speech_backend(settings, options):
    if options["provider"] == "openai":
        return OpenAISpeechBackend(
            options.get("api_key", settings.get_api_key()), options
        )
    if options["provider"] != "foundry":
        raise ValueError("Choisissez OpenAI ou Foundry Local sur Windows.")
    program, args = worker_command()
    args = ["--speech-worker" if arg == "--foundry-worker" else arg for arg in args]
    if options.get("action", "start") in {"probe", "download"}:
        return ProcessSpeechBackend((program, args), options)
    return ResidentSpeechBackend(
        (program, args), options, settings.get_speech_idle_seconds()
    )
