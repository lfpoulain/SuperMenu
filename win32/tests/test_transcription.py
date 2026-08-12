from types import SimpleNamespace

import pytest

from src.audio.audio_config import TRANSCRIPTION_MODEL
from src.audio.transcription import (
    Transcriber,
    parse_transcription_keywords,
    parse_transcription_languages,
)


def _transcriber_with_fake_client(create):
    transcriber = Transcriber.__new__(Transcriber)
    transcriber.languages = ["fr", "en"]
    transcriber.prompt = "Dictée technique Python."
    transcriber.keywords = ["SuperMenu", "PySide6"]
    transcriber.last_detected_languages = []
    transcriber.client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(create=create)
        )
    )
    return transcriber


def test_gpt_transcribe_uses_current_context_fields(tmp_path):
    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(b"RIFF-not-empty")
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            text="Bonjour SuperMenu",
            languages=[SimpleNamespace(code="fr")],
        )

    transcriber = _transcriber_with_fake_client(create)

    assert transcriber.transcribe(str(audio_path)) == "Bonjour SuperMenu"
    assert captured["model"] == "gpt-transcribe"
    assert captured["prompt"] == "Dictée technique Python."
    assert captured["extra_body"] == {
        "languages": ["fr", "en"],
        "keywords": ["SuperMenu", "PySide6"],
    }
    assert "language" not in captured
    assert "response_format" not in captured
    assert transcriber.last_detected_languages == ["fr"]


def test_transcription_model_is_current_recommended_alias():
    assert TRANSCRIPTION_MODEL == "gpt-transcribe"


def test_transcription_hint_parsing_is_deduplicated_and_validated():
    assert parse_transcription_languages("fr, EN; fr zh-cn") == [
        "fr",
        "en",
        "zh-cn",
    ]
    assert parse_transcription_keywords(
        "SuperMenu, PySide6\nSuperMenu"
    ) == ["SuperMenu", "PySide6"]

    with pytest.raises(ValueError, match="Code de langue invalide"):
        parse_transcription_languages("français")

    with pytest.raises(ValueError, match="ne peuvent pas contenir"):
        parse_transcription_keywords("terme <interdit>")
