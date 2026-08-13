#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration pour les fonctionnalités audio de SuperMenu.
"""

import pyaudio

# Paramètres audio
SAMPLE_RATE = 48000  # Fréquence d'échantillonnage en Hz (48kHz haute qualité)
CHANNELS = 1  # Mono
CHUNK_SIZE = 1024  # Taille des chunks pour PyAudio
FORMAT = pyaudio.paInt16  # Format d'échantillonnage pour PyAudio

# Paramètres OpenAI
TRANSCRIPTION_MODEL = (
    "gpt-transcribe"  # Modèle recommandé pour les fichiers audio terminés
)
MAX_RECORDING_TIME = 60  # Temps maximum d'enregistrement en secondes

# Format de fichier audio natif
WAV_EXTENSION = ".wav"

# Paramètres pour le traitement audio
STREAM_STOP_DELAY = 0.5  # Délai d'attente après l'arrêt du flux audio (en secondes)

# Paramètres pour les opérations de texte
CLIPBOARD_PASTE_DELAY = 0.3  # Délai d'attente après le collage du texte (en secondes)
CLIPBOARD_COPY_DELAY = 0.2  # Délai d'attente après la copie du texte (en secondes)
CLIPBOARD_RESTORE_DELAY = (
    0.2  # Délai supplémentaire avant de restaurer le clipboard original (en secondes)
)
