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
import sys
import threading
from logging.handlers import RotatingFileHandler


# Déterminer le répertoire de logs (../logs par rapport à ce fichier)
if getattr(sys, "frozen", False):
    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = os.path.expanduser("~\\AppData\\Local")
    LOG_DIR = os.path.join(local_app_data, "SuperMenu", "logs")
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # SUPERMENU_LOG_DIR lets the tests keep their deliberate errors out of
    # the journal of the application run from the sources.
    LOG_DIR = os.getenv("SUPERMENU_LOG_DIR") or os.path.join(BASE_DIR, "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "supermenu.log")


# Créer et configurer le logger principal
logger = logging.getLogger("SuperMenu")
logger.setLevel(logging.INFO)
logger.propagate = False

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

if not logger.handlers:
    # Sortie console (absente de l'EXE fenêtré, où sys.stderr vaut None)
    if sys.stderr is not None:
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


_crash_reporting_installed = False


def install_crash_reporting() -> None:
    """Écrit dans le journal les exceptions non gérées.

    L'EXE est construit sans console : sans ces crochets, une exception levée
    dans un slot Qt ou dans un thread ne laisse aucune trace.
    """
    global _crash_reporting_installed
    if _crash_reporting_installed:
        return
    _crash_reporting_installed = True

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Exception non gérée dans le thread principal",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def handle_thread_exception(args):
        if issubclass(args.exc_type, SystemExit):
            return
        logger.critical(
            "Exception non gérée dans le thread %s",
            getattr(args.thread, "name", "inconnu"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = handle_exception
    threading.excepthook = handle_thread_exception
