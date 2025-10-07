#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import threading
import os
import base64
import time
import logging
from PySide6.QtCore import QObject, Signal, QTimer, Slot
from utils.logger import log

class OpenAIClient(QObject):
    """Client for OpenAI API interactions"""
    
    # Signals publics
    request_started = Signal()
    request_finished = Signal(str)
    request_error = Signal(str)
    
    # Signaux internes pour communication inter-threads (thread-safe)
    _internal_finished = Signal(str)
    _internal_error = Signal(str)
    
    def __init__(self, settings, api_key=None, model=None, max_retries=3, retry_delay=1.0):
        super().__init__()
        self.api_key = api_key
        self.settings = settings
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Déterminer le modèle à utiliser
        self.use_custom_endpoint = settings.get_use_custom_endpoint()
        self.custom_endpoint = settings.get_custom_endpoint() if self.use_custom_endpoint else None
        
        # Si on utilise un endpoint personnalisé et qu'on a un custom_model dans les settings, l'utiliser
        if self.use_custom_endpoint:
            custom_model = settings.get_custom_model()
            self.model = model if model else (custom_model if custom_model else "llama2")
        else:
            # Sinon utiliser le modèle OpenAI
            self.model = model if model else settings.get_model()
        
        # Connecter les signaux internes aux méthodes d'émission
        self._internal_finished.connect(self._emit_finished)
        self._internal_error.connect(self._emit_error)
        
        # Configurer l'URL de l'API
        if self.use_custom_endpoint and self.custom_endpoint:
            self.api_url = self.custom_endpoint
            if not self.api_url.endswith('/'):
                self.api_url += '/'
            self.api_url += 'v1/chat/completions'
        else:
            # Utiliser OpenAI par défaut
            self.api_url = "https://api.openai.com/v1/chat/completions"
    
    def set_api_key(self, api_key):
        """Set the API key"""
        self.api_key = api_key
    
    def set_model(self, model):
        """Set the model to use"""
        self.model = model
    
    def send_request(self, prompt, content, insert_directly=False):
        """Envoie une requête à l'API OpenAI en arrière-plan"""
        # Vérifier si une clé API est requise
        if not self.use_custom_endpoint and not self.api_key:
            self.request_error.emit("Clé API non configurée. Veuillez configurer votre clé API dans les paramètres.")
            return
        
        # Émettre le signal que la requête a commencé
        self.request_started.emit()
        
        # Lancer la requête dans un thread séparé
        threading.Thread(
            target=self._process_request_thread,
            args=(prompt, content, insert_directly),
            daemon=True
        ).start()
    
    def _make_request_with_retry(self, headers, data, timeout=60):
        """Effectue une requête avec retry logic.
        
        Args:
            headers (dict): En-têtes de la requête
            data (dict): Données JSON à envoyer
            timeout (int): Timeout en secondes
            
        Returns:
            requests.Response: Réponse de l'API
            
        Raises:
            Exception: Si toutes les tentatives échouent
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    data=json.dumps(data),
                    timeout=timeout
                )
                
                # Si succès, retourner immédiatement
                if response.status_code == 200:
                    return response
                
                # Si erreur 429 (rate limit) ou 503 (service unavailable), réessayer
                if response.status_code in [429, 503, 502, 504]:
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (2 ** attempt)  # Backoff exponentiel
                        log(f"API error {response.status_code}, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})...", logging.WARNING)
                        time.sleep(wait_time)
                        continue
                
                # Pour d'autres erreurs, retourner la réponse pour traitement
                return response
                
            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    log(f"Request timeout, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})...", logging.WARNING)
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Request timed out after {self.max_retries} attempts") from e
            
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    log(f"Connection error, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})...", logging.WARNING)
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Connection failed after {self.max_retries} attempts") from e
            
            except Exception as e:
                # Pour les autres exceptions, ne pas réessayer
                raise
        
        # Si on arrive ici, toutes les tentatives ont échoué
        if last_exception:
            raise last_exception
        raise Exception("All retry attempts failed")
    
    def _process_request_thread(self, prompt, content, insert_directly=False):
        """Traite la requête dans un thread séparé"""
        try:
            # Préparer les en-têtes et les données de la requête
            headers = {
                "Content-Type": "application/json"
            }
            
            # Ajouter l'authentification seulement si on utilise OpenAI ou si une clé API est fournie
            if not self.use_custom_endpoint or (self.use_custom_endpoint and self.api_key):
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            # Vérifier si le contenu est un chemin de fichier image
            if isinstance(content, str) and os.path.isfile(content) and content.lower().endswith(('.png', '.jpg', '.jpeg')):
                # C'est une image, préparer le message avec l'image
                with open(content, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
                data = {
                    "model": self.model,  # Utiliser le modèle configuré (doit supporter les images)
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 2048
                }
                
                # Nettoyer l'image temporaire après utilisation
                self._cleanup_image(content)
            else:
                # C'est du texte, préparer le message avec le texte
                full_prompt = f"{prompt}\n\n{content}"
                
                data = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": full_prompt}],
                    "max_tokens": 2048  # Limiter la taille de la réponse
                }
            
            # Envoyer la requête avec retry logic
            response = self._make_request_with_retry(headers, data, timeout=60)
            
            # Vérifier si la requête a réussi
            if response.status_code == 200:
                # Analyser la réponse
                response_data = response.json()
                content = response_data["choices"][0]["message"]["content"]
                
                if insert_directly:
                    # Insérer directement le résultat
                    from audio.text_inserter import TextInserter
                    inserter = TextInserter()
                    inserter.insert_text(content)
                else:
                    # Envoyer le contenu à la fenêtre de réponse via signal interne thread-safe
                    self._internal_finished.emit(content)
            else:
                # Gérer l'erreur via signal interne thread-safe
                error_message = f"Erreur {response.status_code}: {response.text}"
                self._internal_error.emit(error_message)
        
        except Exception as e:
            # Gérer l'exception via signal interne thread-safe
            self._internal_error.emit(f"Erreur: {str(e)}")
    
    @Slot(str)
    def _emit_finished(self, content):
        """Émet le signal finished dans le thread Qt principal"""
        try:
            self.request_finished.emit(content)
        except Exception as e:
            log(f"Error emitting finished signal: {e}", logging.ERROR)
    
    @Slot(str)
    def _emit_error(self, error_message):
        """Émet le signal error dans le thread Qt principal"""
        try:
            self.request_error.emit(error_message)
        except Exception as e:
            log(f"Error emitting error signal: {e}", logging.ERROR)
    
    def _cleanup_image(self, image_path):
        """Nettoyer l'image temporaire après utilisation"""
        try:
            if image_path and os.path.exists(image_path) and "supermenu_screenshot_" in image_path:
                os.remove(image_path)
                print(f"Image temporaire supprimée après traitement API: {image_path}")
        except Exception as e:
            print(f"Erreur lors de la suppression de l'image après traitement API: {e}")
    
    def process_request(self, prompt, content):
        """Méthode obsolète pour la compatibilité - utiliser send_request à la place"""
        self.send_request(prompt, content)

    def send_request_sync(self, prompt, content):
        """Envoie une requête à l'API OpenAI de manière synchrone et renvoie la réponse"""
        # Vérifier si une clé API est requise
        if not self.use_custom_endpoint and not self.api_key:
            raise Exception("Clé API non configurée. Veuillez configurer votre clé API dans les paramètres.")
        
        try:
            # Préparer les en-têtes et les données de la requête
            headers = {
                "Content-Type": "application/json"
            }
            
            # Ajouter l'authentification seulement si on utilise OpenAI ou si une clé API est fournie
            if not self.use_custom_endpoint or (self.use_custom_endpoint and self.api_key):
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            # Vérifier si le contenu est un chemin de fichier image
            if isinstance(content, str) and os.path.isfile(content) and content.lower().endswith(('.png', '.jpg', '.jpeg')):
                # C'est une image, préparer le message avec l'image
                with open(content, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
                data = {
                    "model": self.model,  # Utiliser le modèle configuré (doit supporter les images)
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 2048
                }
                
                # Nettoyer l'image temporaire après utilisation
                self._cleanup_image(content)
            else:
                # C'est du texte, préparer le message avec le texte
                full_prompt = f"{prompt}\n\n{content}"
                
                data = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": full_prompt}],
                    "max_tokens": 2048  # Limiter la taille de la réponse
                }
            
            # Envoyer la requête avec retry logic
            response = self._make_request_with_retry(headers, data, timeout=60)
            
            # Vérifier si la requête a réussi
            if response.status_code == 200:
                # Analyser la réponse
                response_data = response.json()
                content = response_data["choices"][0]["message"]["content"]
                return content
            else:
                # Gérer l'erreur
                error_message = f"Erreur {response.status_code}: {response.text}"
                raise Exception(error_message)
        
        except Exception as e:
            # Propager l'exception
            raise Exception(f"Erreur lors de la requête API: {str(e)}")
