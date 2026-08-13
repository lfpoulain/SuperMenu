#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module pour l'enregistrement audio dans SuperMenu.
"""

import os
import time
import tempfile
import threading
import logging
import pyaudio
import wave
import math
from src.utils.logger import log
from src.audio.audio_config import (
    SAMPLE_RATE,
    CHANNELS,
    CHUNK_SIZE,
    MAX_RECORDING_TIME,
    FORMAT,
    WAV_EXTENSION,
    STREAM_STOP_DELAY,
)

MAX_RECORDING_CHUNKS = max(1, math.ceil(MAX_RECORDING_TIME * SAMPLE_RATE / CHUNK_SIZE))


class AudioRecorder:
    """Classe pour gérer l'enregistrement audio."""

    def __init__(self, input_device_index=None):
        """
        Initialise l'enregistreur audio.

        Args:
            input_device_index (int, optional): Index du périphérique d'entrée à utiliser
        """
        self.input_device_index = input_device_index
        self.pyaudio = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.stop_event = threading.Event()
        self.temp_files = []  # Pour suivre les fichiers temporaires créés

        # Afficher les informations sur le périphérique audio
        if input_device_index is not None:
            try:
                device_info = self.pyaudio.get_device_info_by_index(input_device_index)
                log(f"Périphérique audio sélectionné: {device_info['name']}")
                log(
                    f"Canaux max: {device_info['maxInputChannels']}, Taux d'échantillonnage par défaut: {device_info['defaultSampleRate']}"
                )
            except Exception as e:
                log(
                    f"Erreur lors de l'obtention des informations sur le périphérique: {e}",
                    level=logging.ERROR,
                )

    @staticmethod
    def list_microphones():
        """
        Liste tous les microphones MME (Microsoft Multimedia Extensions) disponibles.

        Returns:
            list: Liste de tuples (index, nom) pour chaque microphone MME
        """
        p = None
        mics = []

        try:
            p = pyaudio.PyAudio()
            log("Recherche des microphones MME disponibles...")
            mme_api_index = p.get_host_api_info_by_type(pyaudio.paMME)["index"]

            for i in range(p.get_device_count()):
                device_info = p.get_device_info_by_index(i)
                try:
                    if (
                        device_info["maxInputChannels"] > 0
                        and device_info.get("hostApi", -1) == mme_api_index
                    ):
                        mics.append((i, device_info["name"]))
                        log(
                            f"Microphone MME trouvé: {device_info['name']} (index: {i})",
                            level=logging.DEBUG,
                        )
                except Exception as e:
                    log(
                        f"Erreur lors de l'accès au périphérique {i}: {e}",
                        level=logging.WARNING,
                    )
        except Exception as e:
            log(f"Impossible d'énumérer les microphones: {e}", level=logging.ERROR)
        finally:
            if p is not None:
                try:
                    p.terminate()
                except Exception:
                    pass

        if not mics:
            log("Aucun microphone MME trouvé!", level=logging.WARNING)
        else:
            log(f"{len(mics)} microphone(s) MME trouvé(s)")
        return mics

    def start_recording(self):
        """
        Démarre l'enregistrement audio.

        Returns:
            str: Chemin du fichier temporaire qui contiendra l'audio
        """
        if self.is_recording:
            log("L'enregistrement est déjà en cours", level=logging.WARNING)
            return None

        # Créer un fichier temporaire pour l'enregistrement
        temp_file = tempfile.NamedTemporaryFile(suffix=WAV_EXTENSION, delete=False)
        temp_path = temp_file.name
        temp_file.close()

        # Ajouter à la liste des fichiers temporaires
        self.temp_files.append(temp_path)

        log(f"Démarrage de l'enregistrement au format WAV: {temp_path}")
        log(
            f"Paramètres d'enregistrement: {CHANNELS} canal(aux), {SAMPLE_RATE}Hz, chunks de {CHUNK_SIZE}",
            level=logging.DEBUG,
        )

        # Réinitialiser les frames et l'événement d'arrêt
        self.frames = []
        self.stop_event.clear()

        # Ouvrir le flux audio
        try:
            self.stream = self.pyaudio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=CHUNK_SIZE,
                stream_callback=self._callback,
            )

            self.is_recording = True
            log("Flux audio ouvert avec succès", level=logging.DEBUG)

            # Démarrer le flux
            self.stream.start_stream()

            return temp_path

        except Exception as e:
            log(f"Erreur lors de l'ouverture du flux audio: {e}", level=logging.ERROR)
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                self.temp_files.remove(temp_path)
            except (OSError, ValueError):
                pass
            return None

    def _callback(self, in_data, frame_count, time_info, status):
        """
        Callback pour le flux audio.

        Args:
            in_data: Les données audio capturées
            frame_count: Nombre de frames
            time_info: Informations temporelles
            status: Statut du flux

        Returns:
            tuple: (données, drapeau de continuation)
        """
        if status:
            log(f"Statut du flux audio: {status}", level=logging.WARNING)

        if self.stop_event.is_set() or len(self.frames) >= MAX_RECORDING_CHUNKS:
            self.stop_event.set()
            return (None, pyaudio.paComplete)
        self.frames.append(in_data)
        return (None, pyaudio.paContinue)

    def stop_recording(self):
        """
        Arrête l'enregistrement et sauvegarde le fichier audio.

        Returns:
            str: Chemin du fichier audio enregistré, ou None en cas d'erreur
        """
        if not self.is_recording:
            log("Aucun enregistrement en cours", level=logging.WARNING)
            return None

        # Signaler l'arrêt au callback
        self.stop_event.set()

        # Attendre que le flux se termine
        time.sleep(STREAM_STOP_DELAY)

        # Fermer le flux
        try:
            if self.stream:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
                log("Flux audio fermé", level=logging.DEBUG)
        except Exception as e:
            log(f"Erreur lors de la fermeture du flux audio: {e}", level=logging.ERROR)
        finally:
            self.stream = None

        self.is_recording = False

        # Récupérer le chemin du fichier temporaire
        output_file_path = self.temp_files[-1] if self.temp_files else None

        if output_file_path and self.frames:
            try:
                return self._save_to_wav(output_file_path)
            except Exception as e:
                log(
                    f"Erreur lors de la sauvegarde du fichier audio: {e}",
                    level=logging.ERROR,
                )
                return None
        else:
            log("Aucune donnée audio à sauvegarder", level=logging.WARNING)
            return None

    def cancel_recording(self):
        """Arrêter le microphone et supprimer l'enregistrement temporaire."""
        self.stop_event.set()

        try:
            if self.stream:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
        except Exception as e:
            log(
                f"Erreur lors de l'annulation du flux audio: {e}",
                level=logging.WARNING,
            )
        finally:
            self.stream = None
            self.is_recording = False
            self.frames = []

        for temp_file in list(self.temp_files):
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except OSError as e:
                log(
                    f"Impossible de supprimer l'enregistrement annulé: {e}",
                    level=logging.WARNING,
                )
        self.temp_files = []

    def _save_to_wav(self, wav_file_path):
        """
        Sauvegarde les données audio au format WAV.

        Args:
            wav_file_path (str): Chemin du fichier WAV à créer

        Returns:
            str: Chemin du fichier WAV créé, ou None en cas d'erreur
        """
        try:
            log(f"Sauvegarde de l'audio au format WAV: {wav_file_path}")

            with wave.open(wav_file_path, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(self.pyaudio.get_sample_size(FORMAT))
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(b"".join(self.frames))

            # Vérifier la taille du fichier WAV
            wav_file_size = os.path.getsize(wav_file_path)
            log(f"Fichier WAV sauvegardé: {wav_file_path} ({wav_file_size} octets)")

            if wav_file_size <= 44:
                log("Le fichier WAV est vide!", level=logging.WARNING)
                return None

            return wav_file_path

        except Exception as e:
            log(f"Erreur lors de la sauvegarde en WAV: {e}", level=logging.ERROR)
            return None

    def cleanup(self):
        """Nettoie les ressources et les fichiers temporaires."""
        # Fermer le flux s'il est ouvert
        if self.stream:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                log(
                    f"Erreur lors de la fermeture du flux audio: {e}",
                    level=logging.WARNING,
                )
            finally:
                self.stream = None
        self.is_recording = False
        self.frames = []

        # Terminer PyAudio
        try:
            self.pyaudio.terminate()
        except Exception as e:
            log(f"Erreur lors de la terminaison de PyAudio: {e}", level=logging.WARNING)

        # Supprimer les fichiers temporaires
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    log(
                        f"Fichier temporaire supprimé: {temp_file}", level=logging.DEBUG
                    )
            except Exception as e:
                log(
                    f"Erreur lors de la suppression du fichier temporaire {temp_file}: {e}",
                    level=logging.WARNING,
                )

        self.temp_files = []
