#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module de journalisation pour SuperMenu.
"""
import logging
import os
import sys
from datetime import datetime

# Configuration du logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Créer un logger
logger = logging.getLogger('SuperMenu')

def log(message, level=logging.INFO):
    """
    Journalise un message avec le niveau spécifié.
    
    Args:
        message (str): Le message à journaliser
        level: Le niveau de journalisation (par défaut: INFO)
    """
    if level == logging.DEBUG:
        logger.debug(message)
    elif level == logging.INFO:
        logger.info(message)
    elif level == logging.WARNING:
        logger.warning(message)
    elif level == logging.ERROR:
        logger.error(message)
    elif level == logging.CRITICAL:
        logger.critical(message)
    else:
        logger.info(message)
