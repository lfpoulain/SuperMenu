#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module pour parser et extraire le contenu thinking des réponses de modèles
"""

import re
from typing import Tuple, Optional


def extract_thinking_content(response: str) -> Tuple[Optional[str], str]:
    """
    Extrait le contenu thinking et le contenu principal d'une réponse.
    
    Supporte plusieurs formats de balises thinking:
    - <think>...</think>
    - <thinking>...</thinking>
    - <thought>...</thought>
    
    Args:
        response: La réponse complète du modèle
        
    Returns:
        Tuple contenant:
        - thinking_content: Le contenu des balises thinking (None si absent)
        - main_content: Le contenu principal sans les balises thinking
    """
    if not response:
        return None, ""
    
    # Patterns pour différents formats de balises thinking
    patterns = [
        r'<think>(.*?)</think>',
        r'<thinking>(.*?)</thinking>',
        r'<thought>(.*?)</thought>'
    ]
    
    thinking_content = None
    main_content = response
    
    # Chercher le contenu thinking avec tous les patterns
    for pattern in patterns:
        matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
        if matches:
            # Combiner tous les blocs thinking trouvés
            thinking_content = '\n\n'.join(matches)
            # Retirer toutes les balises thinking du contenu principal
            main_content = re.sub(pattern, '', main_content, flags=re.DOTALL | re.IGNORECASE)
            break
    
    # Nettoyer le contenu principal (retirer les espaces multiples et lignes vides)
    if main_content:
        main_content = re.sub(r'\n\s*\n\s*\n', '\n\n', main_content)
        main_content = main_content.strip()
    
    # Nettoyer le contenu thinking
    if thinking_content:
        thinking_content = thinking_content.strip()
    
    return thinking_content, main_content


def has_thinking_content(response: str) -> bool:
    """
    Vérifie si une réponse contient du contenu thinking.
    
    Args:
        response: La réponse à vérifier
        
    Returns:
        True si la réponse contient des balises thinking, False sinon
    """
    if not response:
        return False
    
    patterns = [
        r'<think>.*?</think>',
        r'<thinking>.*?</thinking>',
        r'<thought>.*?</thought>'
    ]
    
    for pattern in patterns:
        if re.search(pattern, response, re.DOTALL | re.IGNORECASE):
            return True
    
    return False
