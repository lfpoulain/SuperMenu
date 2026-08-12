#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Transcription de fichiers audio terminés avec l'API OpenAI."""

import logging
import os
import re
import time

import openai
from openai import OpenAI

from src.audio.audio_config import TRANSCRIPTION_MODEL
from src.utils.logger import log


MAX_TRANSCRIPTION_FILE_BYTES = 25 * 1024 * 1024
SUPPORTED_AUDIO_EXTENSIONS = {
    ".m4a",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".wav",
    ".webm",
}
_LANGUAGE_CODE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[a-z]{2})?$")


class TranscriptionError(RuntimeError):
    """Erreur de transcription prête à être présentée à l'utilisateur."""


def parse_transcription_languages(value):
    """Normaliser une liste ou une chaîne de codes de langue."""
    if isinstance(value, str):
        raw_values = re.split(r"[\s,;]+", value)
    else:
        raw_values = value or []

    languages = []
    for raw_value in raw_values:
        code = str(raw_value or "").strip().lower()
        if not code:
            continue
        if not _LANGUAGE_CODE_PATTERN.fullmatch(code):
            raise ValueError(
                f"Code de langue invalide : {raw_value}. "
                "Utilisez par exemple fr, en ou zh-cn."
            )
        if code not in languages:
            languages.append(code)
    return languages


def parse_transcription_keywords(value):
    """Normaliser les termes littéraux attendus par GPT Transcribe."""
    if isinstance(value, str):
        raw_values = re.split(r"[,\r\n]+", value)
    else:
        raw_values = value or []

    keywords = []
    for raw_value in raw_values:
        keyword = str(raw_value or "").strip()
        if not keyword:
            continue
        if "<" in keyword or ">" in keyword:
            raise ValueError(
                "Les mots-clés de transcription ne peuvent pas contenir "
                "les caractères < ou >."
            )
        if keyword not in keywords:
            keywords.append(keyword)
    return keywords


class Transcriber:
    """Transcrire un enregistrement borné avec GPT Transcribe."""

    def __init__(
        self,
        api_key=None,
        *,
        languages=None,
        prompt="",
        keywords=None,
    ):
        self.api_key = api_key
        self.languages = parse_transcription_languages(languages)
        self.prompt = str(prompt or "").strip()
        self.keywords = parse_transcription_keywords(keywords)
        self.last_detected_languages = []

        if self.api_key:
            log("Clé API fournie au module de transcription", logging.DEBUG)
        else:
            log(
                "Aucune clé API fournie au module de transcription ; "
                "utilisation de l'environnement",
                logging.DEBUG,
            )

        # Le SDK OpenAI réessaie automatiquement deux fois les erreurs
        # transitoires. Une limite explicite évite un indicateur bloqué
        # indéfiniment si la connexion se dégrade.
        self.client = OpenAI(
            api_key=self.api_key,
            max_retries=2,
            timeout=120.0,
        )

    @staticmethod
    def _validate_audio_file(audio_file_path):
        if not audio_file_path or not os.path.isfile(audio_file_path):
            raise TranscriptionError(
                "Le fichier audio temporaire est introuvable."
            )

        file_size = os.path.getsize(audio_file_path)
        if file_size <= 0:
            raise TranscriptionError(
                "Aucun son n'a été enregistré. Vérifiez le microphone "
                "sélectionné et réessayez."
            )
        if file_size > MAX_TRANSCRIPTION_FILE_BYTES:
            raise TranscriptionError(
                "L'enregistrement dépasse la limite OpenAI de 25 Mo."
            )

        file_format = os.path.splitext(audio_file_path)[1].lower()
        if file_format not in SUPPORTED_AUDIO_EXTENSIONS:
            raise TranscriptionError(
                f"Le format audio {file_format or 'inconnu'} n'est pas "
                "accepté par l'API de transcription."
            )
        return file_size, file_format

    @staticmethod
    def _extract_detected_languages(transcript):
        detected = []
        for item in getattr(transcript, "languages", None) or []:
            code = getattr(item, "code", None)
            if code is None and isinstance(item, dict):
                code = item.get("code")
            if code:
                detected.append(str(code))
        return detected

    def transcribe(self, audio_file_path):
        """Transcrire un fichier et retourner uniquement son texte final."""
        file_size, file_format = self._validate_audio_file(audio_file_path)
        log(
            "Fichier prêt pour GPT Transcribe : "
            f"{file_size} octets, format {file_format}",
            logging.DEBUG,
        )

        request = {
            "model": TRANSCRIPTION_MODEL,
        }
        if self.prompt:
            request["prompt"] = self.prompt

        extra_body = {}
        if self.languages:
            extra_body["languages"] = self.languages
        if self.keywords:
            extra_body["keywords"] = self.keywords
        if extra_body:
            request["extra_body"] = extra_body

        start_time = time.monotonic()
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    file=audio_file,
                    **request,
                )
        except openai.AuthenticationError as exc:
            raise TranscriptionError(
                "La clé API OpenAI est absente ou invalide."
            ) from exc
        except openai.RateLimitError as exc:
            raise TranscriptionError(
                "La limite d'utilisation OpenAI est atteinte. "
                "Réessayez dans quelques instants."
            ) from exc
        except openai.APITimeoutError as exc:
            raise TranscriptionError(
                "OpenAI n'a pas répondu à temps. Vérifiez la connexion "
                "puis réessayez."
            ) from exc
        except openai.APIConnectionError as exc:
            raise TranscriptionError(
                "Connexion à OpenAI impossible. Vérifiez votre accès réseau."
            ) from exc
        except openai.BadRequestError as exc:
            raise TranscriptionError(
                "OpenAI a refusé les paramètres ou le fichier audio. "
                "Vérifiez les langues, le contexte et les mots-clés."
            ) from exc
        except openai.OpenAIError as exc:
            raise TranscriptionError(
                f"Erreur OpenAI pendant la transcription : {exc}"
            ) from exc
        except OSError as exc:
            raise TranscriptionError(
                "Impossible de lire le fichier audio temporaire."
            ) from exc

        text = getattr(transcript, "text", None)
        if text is None and isinstance(transcript, str):
            text = transcript
        text = str(text or "").strip()
        if not text:
            raise TranscriptionError(
                "OpenAI n'a détecté aucune parole dans l'enregistrement."
            )

        self.last_detected_languages = self._extract_detected_languages(
            transcript
        )
        elapsed = time.monotonic() - start_time
        language_info = (
            f", langues : {', '.join(self.last_detected_languages)}"
            if self.last_detected_languages
            else ""
        )
        log(
            f"Transcription réussie en {elapsed:.2f} s : "
            f"{len(text)} caractères{language_info}"
        )
        return text
