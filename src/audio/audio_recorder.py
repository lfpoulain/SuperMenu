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
import subprocess
import wave
import math
from src.utils.logger import log
from src.audio.audio_config import (
    SAMPLE_RATE, CHANNELS, CHUNK_SIZE, MAX_RECORDING_TIME, OPUS_BITRATE, FFMPEG_PATH,
    FORMAT, WAV_EXTENSION, MP4_EXTENSION, PCM_EXTENSION, FFMPEG_INPUT_FORMAT,
    FFMPEG_CONTAINER_FORMAT, STREAM_STOP_DELAY
)

MAX_RECORDING_CHUNKS = max(
    1, math.ceil(MAX_RECORDING_TIME * SAMPLE_RATE / CHUNK_SIZE)
)
FFMPEG_TIMEOUT_SECONDS = 30


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
        
        # Vérifier si FFmpeg est disponible
        self.ffmpeg_available = os.path.exists(FFMPEG_PATH)
        if self.ffmpeg_available:
            log(f"FFmpeg trouvé: {FFMPEG_PATH}")
        else:
            log(f"FFmpeg non trouvé à {FFMPEG_PATH}. L'enregistrement se fera en WAV.", level=logging.WARNING)
        
        # Afficher les informations sur le périphérique audio
        if input_device_index is not None:
            try:
                device_info = self.pyaudio.get_device_info_by_index(input_device_index)
                log(f"Périphérique audio sélectionné: {device_info['name']}")
                log(f"Canaux max: {device_info['maxInputChannels']}, Taux d'échantillonnage par défaut: {device_info['defaultSampleRate']}")
            except Exception as e:
                log(f"Erreur lors de l'obtention des informations sur le périphérique: {e}", level=logging.ERROR)
    
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
        
        # Utiliser MP4/Opus si FFmpeg est disponible, sinon WAV
        file_extension = MP4_EXTENSION if self.ffmpeg_available else WAV_EXTENSION
        
        # Créer un fichier temporaire pour l'enregistrement
        temp_file = tempfile.NamedTemporaryFile(suffix=file_extension, delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        # Ajouter à la liste des fichiers temporaires
        self.temp_files.append(temp_path)
        
        format_name = "MP4/Opus" if file_extension == MP4_EXTENSION else "WAV"
        log(f"Démarrage de l'enregistrement au format {format_name}: {temp_path}")
        log(f"Paramètres d'enregistrement: {CHANNELS} canal(aux), {SAMPLE_RATE}Hz, chunks de {CHUNK_SIZE}", level=logging.DEBUG)
        
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
                stream_callback=self._callback
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
        
        self.is_recording = False
        
        # Récupérer le chemin du fichier temporaire
        output_file_path = self.temp_files[-1] if self.temp_files else None
        
        if output_file_path and self.frames:
            try:
                # Si FFmpeg est disponible, encoder en MP4/Opus, sinon en WAV
                if self.ffmpeg_available:
                    return self._encode_to_opus(output_file_path)
                else:
                    return self._save_to_wav(output_file_path)
                
            except Exception as e:
                log(f"Erreur lors de la sauvegarde du fichier audio: {e}", level=logging.ERROR)
                return None
        else:
            log("Aucune donnée audio à sauvegarder", level=logging.WARNING)
            return None

    def cancel_recording(self):
        """Arrêter le microphone et supprimer l'enregistrement sans l'encoder."""
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
            
            with wave.open(wav_file_path, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(self.pyaudio.get_sample_size(FORMAT))
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(b''.join(self.frames))
            
            # Vérifier la taille du fichier WAV
            wav_file_size = os.path.getsize(wav_file_path)
            log(f"Fichier WAV sauvegardé: {wav_file_path} ({wav_file_size} octets)")
            
            if wav_file_size == 0:
                log("Le fichier WAV est vide!", level=logging.WARNING)
                return None
            
            return wav_file_path
            
        except Exception as e:
            log(f"Erreur lors de la sauvegarde en WAV: {e}", level=logging.ERROR)
            return None
    
    def _encode_to_opus(self, output_file_path):
        """
        Encode les données audio directement au format Opus et les remuxe dans un conteneur MP4.
        
        Args:
            output_file_path (str): Chemin du fichier de sortie
            
        Returns:
            str: Chemin du fichier MP4 créé, ou None en cas d'erreur
        """
        pcm_path = None
        try:
            # Créer un fichier temporaire pour les données PCM brutes
            with tempfile.NamedTemporaryFile(suffix=PCM_EXTENSION, delete=False) as pcm_file:
                pcm_path = pcm_file.name
                # Écrire les données PCM brutes
                pcm_file.write(b''.join(self.frames))
            
            # Assurer que le chemin de sortie se termine par .mp4
            if not output_file_path.lower().endswith(MP4_EXTENSION):
                mp4_path = output_file_path.rsplit('.', 1)[0] + MP4_EXTENSION
            else:
                mp4_path = output_file_path
                
            log(f"Encodage en Opus et remuxage en MP4: {mp4_path}")
            
            # Utiliser FFmpeg pour encoder en Opus et remuxer dans un conteneur MP4
            ffmpeg_cmd = [
                FFMPEG_PATH,
                '-f', FFMPEG_INPUT_FORMAT,  # Format d'entrée: PCM signé 16-bit little-endian
                '-ar', str(SAMPLE_RATE),  # Taux d'échantillonnage
                '-ac', str(CHANNELS),  # Nombre de canaux
                '-i', pcm_path,  # Fichier d'entrée
                '-c:a', 'libopus',  # Codec Opus
                '-b:a', f'{OPUS_BITRATE}',  # Bitrate
                '-application', 'voip',  # Optimisé pour la voix
                '-frame_duration', '20',  # Durée de trame en ms
                '-compression_level', '10',  # Niveau de compression (0-10)
                '-f', FFMPEG_CONTAINER_FORMAT,  # Format conteneur MP4
                '-y',  # Écraser le fichier de sortie s'il existe
                mp4_path  # Fichier de sortie
            ]
            
            # Exécuter FFmpeg
            process = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=FFMPEG_TIMEOUT_SECONDS,
                check=False,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if os.name == "nt"
                    else 0
                ),
            )
            
            # Vérifier que le fichier MP4 a été créé
            if (
                process.returncode == 0
                and os.path.exists(mp4_path)
                and os.path.getsize(mp4_path) > 0
            ):
                mp4_size = os.path.getsize(mp4_path)
                log(f"Encodage en MP4/Opus réussi: {mp4_path} ({mp4_size} octets)")
                return mp4_path
            else:
                log("Échec de l'encodage en MP4/Opus", level=logging.ERROR)
                if process.stderr:
                    log(
                        f"Erreur FFmpeg: {process.stderr.decode('utf-8', errors='replace')}",
                        level=logging.ERROR,
                    )
                return None

        except subprocess.TimeoutExpired:
            log(
                f"FFmpeg n'a pas répondu sous {FFMPEG_TIMEOUT_SECONDS} secondes",
                level=logging.ERROR,
            )
            return None
        except Exception as e:
            log(f"Erreur lors de l'encodage en MP4/Opus: {e}", level=logging.ERROR)
            return None
        finally:
            if pcm_path and os.path.exists(pcm_path):
                try:
                    os.remove(pcm_path)
                    log(f"Fichier PCM temporaire supprimé: {pcm_path}")
                except Exception as e:
                    log(
                        f"Erreur lors de la suppression du fichier PCM temporaire: {e}",
                        level=logging.WARNING,
                    )
    
    def cleanup(self):
        """Nettoie les ressources et les fichiers temporaires."""
        # Fermer le flux s'il est ouvert
        if self.stream:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                log(f"Erreur lors de la fermeture du flux audio: {e}", level=logging.WARNING)
        
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
                    log(f"Fichier temporaire supprimé: {temp_file}", level=logging.DEBUG)
            except Exception as e:
                log(f"Erreur lors de la suppression du fichier temporaire {temp_file}: {e}", level=logging.WARNING)
        
        self.temp_files = []
