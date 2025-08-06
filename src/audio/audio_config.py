#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration pour les fonctionnalités audio de SuperMenu.
"""
import os
import sys
import pyaudio

# Obtenir le chemin de base du projet
if getattr(sys, 'frozen', False):
    # Si l'application est compilée (par exemple avec PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # En mode développement
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Chemin vers l'exécutable FFmpeg
FFMPEG_PATH = os.path.join(BASE_DIR, 'bin', 'ffmpeg.exe')

# Paramètres audio
SAMPLE_RATE = 48000  # Fréquence d'échantillonnage en Hz (48kHz haute qualité)
CHANNELS = 1  # Mono
CHUNK_SIZE = 1024  # Taille des chunks pour PyAudio
FORMAT = pyaudio.paInt16  # Format d'échantillonnage pour PyAudio

# Paramètres d'encodage audio
AUDIO_FORMAT = "opus"  # Format audio préféré pour l'envoi à l'API
OPUS_BITRATE = 32000  # Bitrate pour l'encodage Opus (32kbps)

# Paramètres FFmpeg
FFMPEG_OPUS_PARAMS = {
    "c:a": "libopus",
    "b:a": f"{OPUS_BITRATE}",
    "application": "voip",  # Options: voip, audio, lowdelay (voip est optimisé pour la parole)
    "frame_duration": 20,   # Durée de trame en ms (10, 20, 40, 60)
    "compression_level": 10 # Niveau de compression (0-10, 10 étant la plus haute qualité)
}

# Liste des formats audio optimisés par ordre de préférence
PREFERRED_FORMATS = ["opus", "wav"]  # Du plus au moins préféré

# Paramètres OpenAI
TRANSCRIPTION_MODEL = "gpt-4o-transcribe"  # Modèle à utiliser pour la transcription
MAX_RECORDING_TIME = 60  # Temps maximum d'enregistrement en secondes

# Paramètres par défaut
DEFAULT_MICROPHONE_INDEX = None  # None = utiliser le microphone par défaut du système

# Extensions de fichiers audio
WAV_EXTENSION = '.wav'
MP4_EXTENSION = '.mp4'
PCM_EXTENSION = '.pcm'

# Paramètres pour les commandes FFmpeg
FFMPEG_INPUT_FORMAT = 's16le'  # Format d'entrée: PCM signé 16-bit little-endian
FFMPEG_CONTAINER_FORMAT = 'mp4'  # Format conteneur

# Paramètres pour le traitement audio
STREAM_STOP_DELAY = 0.5  # Délai d'attente après l'arrêt du flux audio (en secondes)

# Paramètres pour les opérations de texte
CLIPBOARD_PASTE_DELAY = 0.1  # Délai d'attente avant/après le collage du texte (en secondes)
CLIPBOARD_COPY_DELAY = 0.1  # Délai d'attente pour la copie du texte (en secondes)

# Paramètres pour la reconnaissance vocale
VOICE_RECOGNITION_DIALOG_WIDTH = 300  # Largeur de la boîte de dialogue de reconnaissance vocale
VOICE_RECOGNITION_DIALOG_TITLE = "Enregistrement vocal"  # Titre de la boîte de dialogue
VOICE_RECOGNITION_DIALOG_MESSAGE = "Enregistrement en cours...\nParlez maintenant et appuyez sur le bouton ci-dessous quand vous avez terminé."  # Message affiché dans la boîte de dialogue
VOICE_RECOGNITION_STOP_BUTTON_TEXT = "Arrêter l'enregistrement"  # Texte du bouton pour arrêter l'enregistrement
