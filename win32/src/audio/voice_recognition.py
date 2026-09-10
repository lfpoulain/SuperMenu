"""Windows adapter for the shared live dictation controller."""

from types import SimpleNamespace

from supermenu_core.audio.microphone import microphones
from supermenu_core.audio.session import DictationSession
from supermenu_core.audio.settings import languages, speech_options
from supermenu_core.ui.dictation_dialog import RecordingDialog  # noqa: F401
from src.audio.speech_backend import create_speech_backend


class VoiceRecognition(DictationSession):
    def __init__(
        self,
        api_key=None,
        microphone_index=None,
        callback=None,
        target=None,
        *,
        settings=None,
        transcription_languages=None,
        transcription_prompt="",
        transcription_keywords=None,
        callback_success_message=""
    ):
        if settings is not None:
            options = speech_options(settings)
        else:
            settings = SimpleNamespace(get_api_key=lambda: api_key or "")
            options = {
                "provider": "openai",
                "microphone": "",
                "language": "",
                "languages": languages(transcription_languages),
                "prompt": transcription_prompt,
                "keywords": (
                    transcription_keywords.split(",")
                    if isinstance(transcription_keywords, str)
                    else transcription_keywords or []
                ),
            }
        super().__init__(
            lambda opts: create_speech_backend(settings, opts), options, callback
        )
        self.target = target

    @staticmethod
    def list_microphones():
        return microphones()
