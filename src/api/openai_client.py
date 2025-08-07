#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import threading
import os
import base64
from PySide6.QtCore import QObject, Signal

class OpenAIClient(QObject):
    """Client for OpenAI API interactions"""
    
    # Signals
    request_started = Signal()
    request_finished = Signal(str)
    request_error = Signal(str)
    
    def __init__(self, api_key=None, custom_endpoint=None, custom_model=None, use_custom_endpoint=False):
        super().__init__()
        self.api_key = api_key
        self.use_custom_endpoint = use_custom_endpoint
        
        if use_custom_endpoint and custom_endpoint:
            # Utiliser l'endpoint personnalisé (ex: Ollama)
            self.api_url = custom_endpoint
            if not self.api_url.endswith('/chat/completions'):
                if not self.api_url.endswith('/'):
                    self.api_url += '/'
                self.api_url += 'v1/chat/completions'
            self.model = custom_model if custom_model else "llama2"  # Modèle par défaut pour Ollama
        else:
            # Utiliser OpenAI par défaut
            self.api_url = "https://api.openai.com/v1/chat/completions"
            self.model = "gpt-4o-mini"  # Default model
    
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
            
            # Envoyer la requête
            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(data),
                timeout=60
            )
            
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
                    # Envoyer le contenu à la fenêtre de réponse
                    self.request_finished.emit(content)
            else:
                # Gérer l'erreur
                error_message = f"Erreur {response.status_code}: {response.text}"
                self.request_error.emit(error_message)
        
        except Exception as e:
            # Gérer l'exception
            self.request_error.emit(f"Erreur: {str(e)}")
    
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
            
            # Envoyer la requête
            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(data),
                timeout=60
            )
            
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
