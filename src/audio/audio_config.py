#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration pour les fonctionnalités audio de SuperMenu.
"""
import pyaudio
from src.utils.paths import application_base_dir, resource_path

# Obtenir le chemin de base du projet ou du répertoire d'extraction PyInstaller.
BASE_DIR = application_base_dir()

# Chemin vers l'exécutable FFmpeg
FFMPEG_PATH = resource_path("bin", "ffmpeg.exe")

# Paramètres audio
SAMPLE_RATE = 48000  # Fréquence d'échantillonnage en Hz (48kHz haute qualité)
CHANNELS = 1  # Mono
CHUNK_SIZE = 1024  # Taille des chunks pour PyAudio
FORMAT = pyaudio.paInt16  # Format d'échantillonnage pour PyAudio

# Paramètres d'encodage audio
OPUS_BITRATE = 32000  # Bitrate pour l'encodage Opus (32kbps)

# Paramètres OpenAI
TRANSCRIPTION_MODEL = "gpt-transcribe"  # Modèle recommandé pour les fichiers audio terminés
MAX_RECORDING_TIME = 60  # Temps maximum d'enregistrement en secondes

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
CLIPBOARD_PASTE_DELAY = 0.3  # Délai d'attente après le collage du texte (en secondes)
CLIPBOARD_COPY_DELAY = 0.2  # Délai d'attente après la copie du texte (en secondes)
CLIPBOARD_RESTORE_DELAY = 0.2  # Délai supplémentaire avant de restaurer le clipboard original (en secondes)
