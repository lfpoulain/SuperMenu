#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module pour la transcription audio via l'API OpenAI dans SuperMenu.
"""
import os
import logging
import time
from openai import OpenAI
from utils.logger import log
from audio.audio_config import TRANSCRIPTION_MODEL

class Transcriber:
    """Classe pour gérer la transcription audio via OpenAI."""
    
    def __init__(self, api_key=None):
        """
        Initialise le transcripteur.
        
        Args:
            api_key (str, optional): Clé API OpenAI à utiliser. Si None, la clé sera récupérée depuis l'environnement.
        """
        # Utiliser la clé fournie ou celle de l'environnement
        self.api_key = api_key
        
        if self.api_key:
            # Afficher les premiers et derniers caractères de la clé API pour le débogage
            key_start = self.api_key[:5]
            key_end = self.api_key[-5:] if len(self.api_key) > 10 else ""
            log(f"Clé API fournie: {key_start}...{key_end}")
        else:
            log("Aucune clé API fournie, utilisation de la clé d'environnement")
        
        self.client = OpenAI(api_key=self.api_key)
    
    def transcribe(self, audio_file_path):
        """
        Transcrit un fichier audio en texte.
        
        Args:
            audio_file_path (str): Chemin vers le fichier audio à transcrire
            
        Returns:
            str: Le texte transcrit
        """
        try:
            # Vérifier que le fichier d'entrée existe et a une taille non nulle
            if not os.path.exists(audio_file_path):
                log(f"Le fichier audio n'existe pas: {audio_file_path}", level=logging.ERROR)
                return None
                
            file_size = os.path.getsize(audio_file_path)
            file_format = os.path.splitext(audio_file_path)[1].lower()
            log(f"Fichier audio à transcrire: {audio_file_path} ({file_size} octets, format: {file_format})")
            
            if file_size == 0:
                log("Le fichier audio est vide!", level=logging.ERROR)
                return None
                
            # Envoyer le fichier à l'API
            log(f"Envoi du fichier à l'API OpenAI pour transcription: {audio_file_path}")
            
            start_time = time.time()
            with open(audio_file_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model=TRANSCRIPTION_MODEL,
                    file=audio_file,
                    response_format="text",
                    language="fr"  # Définir explicitement la langue française
                )
            
            api_time = time.time() - start_time
            log(f"Transcription réussie en {api_time:.2f} secondes: {len(transcript) if transcript else 0} caractères")
            return transcript
        except Exception as e:
            log(f"Erreur lors de la transcription: {e}", level=logging.ERROR)
            return None
