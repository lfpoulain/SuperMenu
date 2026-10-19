#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Validateurs pour les entrées utilisateur dans SuperMenu.
"""

import ipaddress
import re
from urllib.parse import urlsplit


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
            if not re.match(r"^sk-[a-zA-Z0-9\-_]+$", api_key):
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

        if not re.match(r"^https?://", url, re.IGNORECASE):
            return (
                False,
                "Format d'URL invalide. L'URL doit commencer par http:// ou https://",
            )

        # Vérifications supplémentaires de sécurité
        if "javascript:" in url.lower() or "data:" in url.lower():
            return False, "URL potentiellement dangereuse détectée"

        if re.search(r"\s", url):
            return False, "Format d'URL invalide : l'URL ne doit pas contenir d'espace"

        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            return False, "Format d'URL invalide : port ou adresse incorrects"

        hostname = parsed.hostname or ""
        if not hostname:
            return False, "Format d'URL invalide : nom du serveur manquant"
        if port == 0:
            return False, "Format d'URL invalide : port incorrect"
        if not Validators._is_valid_hostname(hostname):
            return (
                False,
                "Format d'URL invalide : nom du serveur ou adresse IP incorrects",
            )

        return True, ""

    @staticmethod
    def _is_valid_hostname(hostname):
        """Accept DNS, NetBIOS / container short names, IPv4 and IPv6 hosts.

        LAN servers are routinely reached by a dotless name ("gpu-box",
        "DESKTOP-AB12CD", "ollama") or a long private suffix
        (".internal"), which a public-domain pattern rejected.
        """
        if ":" in hostname:
            try:
                ipaddress.IPv6Address(hostname)
            except ValueError:
                return False
            return True

        if re.fullmatch(r"[\d.]+", hostname):
            try:
                ipaddress.IPv4Address(hostname)
            except ValueError:
                return False
            return True

        labels = hostname[:-1].split(".") if hostname.endswith(".") else hostname.split(".")
        if len(hostname) > 253:
            return False
        for label in labels:
            if not label or len(label) > 63:
                return False
            if label.startswith("-") or label.endswith("-"):
                return False
            if not all(char.isalnum() or char in "-_" for char in label):
                return False
        return True

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

        if len(model_name) > 256:
            return False, "Le nom du modèle est trop long"

        # Le nom part uniquement dans le JSON de la requête : les serveurs
        # locaux utilisent des identifiants variés (« @q4_k_m » de LM Studio,
        # identifiants d'instance personnalisés...). Seuls les caractères de
        # contrôle sont refusés.
        if re.search(r"[\x00-\x1f\x7f]", model_name):
            return (
                False,
                "Le nom du modèle contient des caractères de contrôle invalides",
            )

        return True, ""
