#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Validateurs pour les entrées utilisateur dans SuperMenu.
"""
import re
import logging
from utils.logger import log


class Validators:
    """Classe contenant les validateurs pour différents types d'entrées."""
    
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
    
    @staticmethod
    def validate_hotkey(hotkey):
        """
        Valide un raccourci clavier.
        
        Args:
            hotkey (str): Raccourci à valider (ex: "Ctrl+Shift+A")
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not hotkey or not isinstance(hotkey, str):
            return False, "Le raccourci ne peut pas être vide"
        
        hotkey = hotkey.strip()
        
        # Diviser par +
        parts = [p.strip().lower() for p in hotkey.split('+')]
        
        if len(parts) == 0:
            return False, "Le raccourci est vide"
        
        # Vérifier les modificateurs valides
        valid_modifiers = {'ctrl', 'alt', 'shift', 'win', 'cmd'}
        
        # Si plusieurs touches, vérifier qu'au moins une est un modificateur
        if len(parts) > 1:
            has_modifier = any(p in valid_modifiers for p in parts[:-1])
            if not has_modifier:
                log(f"Warning: Hotkey '{hotkey}' has no standard modifiers", logging.WARNING)
        
        # Vérifier qu'il n'y a pas de touches dupliquées
        if len(parts) != len(set(parts)):
            return False, "Le raccourci contient des touches dupliquées"
        
        return True, ""
    
    @staticmethod
    def validate_prompt_text(prompt):
        """
        Valide un texte de prompt.
        
        Args:
            prompt (str): Texte du prompt à valider
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not prompt or not isinstance(prompt, str):
            return False, "Le prompt ne peut pas être vide"
        
        prompt = prompt.strip()
        
        if len(prompt) < 5:
            return False, "Le prompt est trop court (minimum 5 caractères)"
        
        if len(prompt) > 10000:
            return False, "Le prompt est trop long (maximum 10000 caractères)"
        
        return True, ""
    
    @staticmethod
    def sanitize_filename(filename):
        """
        Nettoie un nom de fichier en supprimant les caractères dangereux.
        
        Args:
            filename (str): Nom de fichier à nettoyer
            
        Returns:
            str: Nom de fichier sécurisé
        """
        if not filename:
            return "unnamed"
        
        # Supprimer les caractères dangereux
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
        
        # Limiter la longueur
        if len(safe_name) > 255:
            safe_name = safe_name[:255]
        
        # Ne pas commencer ou finir par un point ou un espace
        safe_name = safe_name.strip('. ')
        
        return safe_name if safe_name else "unnamed"
    
    @staticmethod
    def validate_microphone_index(index):
        """
        Valide un index de microphone.
        
        Args:
            index: Index à valider (peut être None, -1, ou un entier positif)
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if index is None or index == -1:
            return True, ""  # Valeur par défaut acceptable
        
        if not isinstance(index, int):
            return False, "L'index du microphone doit être un nombre entier"
        
        if index < -1 or index > 100:  # Limite arbitraire mais raisonnable
            return False, "L'index du microphone doit être entre -1 et 100"
        
        return True, ""
