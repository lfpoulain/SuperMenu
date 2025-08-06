#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module de journalisation pour SuperMenu.

Ce module configure un logger principal qui enregistre les messages
dans la console **et** dans un fichier de log en rotation situé dans
`logs/supermenu.log`. Le fichier est automatiquement créé si
nécessaire et les logs sont conservés sur plusieurs fichiers afin de
faciliter le débogage des problèmes rencontrés par les utilisateurs.
"""

import logging
import os
from logging.handlers import RotatingFileHandler


# Déterminer le répertoire de logs (../logs par rapport à ce fichier)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "supermenu.log")


# Créer et configurer le logger principal
logger = logging.getLogger("SuperMenu")
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Sortie console
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Sortie fichier avec rotation (1 Mo par fichier, 3 sauvegardes)
file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def log(message: str, level: int = logging.INFO) -> None:
    """Journalise un message avec le niveau spécifié."""
    logger.log(level, message)
