#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Validateurs pour les entrées utilisateur dans SuperMenu.
"""
import re


class Validators:
    """Classe contenant les validateurs pour différents types d'entrées."""

    @staticmethod
    def normalize_prompt_id(prompt_name):
        """Convertit un nom de prompt en identifiant interne sûr.

        Args:
            prompt_name (str): Nom saisi par l'utilisateur.

        Returns:
            str: Identifiant normalisé utilisable comme clé de stockage.
        """
        if not prompt_name or not isinstance(prompt_name, str):
            return ""

        normalized = prompt_name.strip().lower()
        normalized = re.sub(r"\s+", "_", normalized)
        normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized
    
    @staticmethod
    def validate_api_key(api_key):
        """
        Valide une clé API OpenAI.
        
        Args:
            api_key (str): Clé API à valider
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not api_key or not isinstance(api_key, str):
            return False, "La clé API ne peut pas être vide"
        
        # Nettoyer la clé
        api_key = api_key.strip()
        
        if len(api_key) < 20:
            return False, "La clé API semble trop courte"
        
        # Vérifier le format basique (commence par sk- pour OpenAI)
        if api_key.startswith("sk-"):
            if len(api_key) < 48:
                return False, "La clé API OpenAI semble invalide (trop courte)"
            # Format basique : sk-[proj-]XXXX... (accepte lettres, chiffres, tirets et underscores)
            # Les nouvelles clés OpenAI peuvent contenir des underscores : sk-proj-XXXX_YYYY
            if not re.match(r'^sk-[a-zA-Z0-9\-_]+$', api_key):
                return False, "La clé API contient des caractères invalides"
        
        return True, ""
    @staticmethod
    def validate_url(url):
        """
        Valide une URL d'endpoint personnalisé.
        
        Args:
            url (str): URL à valider
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not url or not isinstance(url, str):
            return False, "L'URL ne peut pas être vide"
        
        url = url.strip()
        
        # Vérifier le format de base d'une URL
        url_pattern = re.compile(
            r'^https?://'  # http:// ou https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domaine...
            r'localhost|'  # ou localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ou adresse IP
            r'(?::\d+)?'  # port optionnel
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if not url_pattern.match(url):
            return False, "Format d'URL invalide. L'URL doit commencer par http:// ou https://"
        
        # Vérifications supplémentaires de sécurité
        if 'javascript:' in url.lower() or 'data:' in url.lower():
            return False, "URL potentiellement dangereuse détectée"
        
        return True, ""
    
    @staticmethod
    def validate_model_name(model_name):
        """
        Valide un nom de modèle.
        
        Args:
            model_name (str): Nom du modèle à valider
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not model_name or not isinstance(model_name, str):
            return False, "Le nom du modèle ne peut pas être vide"
        
        model_name = model_name.strip()
        
        if len(model_name) < 2:
            return False, "Le nom du modèle est trop court"
        
        # Autoriser lettres, chiffres, tirets, underscores, points, deux-points et slashes
        # Pattern plus permissif pour supporter différents formats de noms de modèles
        if not re.match(r'^[a-zA-Z0-9._:/-]+$', model_name):
            return False, "Le nom du modèle contient des caractères invalides (seuls les lettres, chiffres, points, tirets, underscores, deux-points et slashes sont autorisés)"
        
        return True, ""
