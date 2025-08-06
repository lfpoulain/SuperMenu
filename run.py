#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script de lancement pour SuperMenu.
Ce script permet de lancer l'application depuis le répertoire racine.
"""

import os
import sys

# Ajouter le répertoire src au chemin d'importation Python
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Importer et lancer l'application
if __name__ == "__main__":
    try:
        # Importer le module main depuis le répertoire src
        import main
        app = main.SuperMenu()
        sys.exit(app.run())
    except ImportError as e:
        print(f"Erreur d'importation: {e}")
        print(f"Chemin d'importation Python: {sys.path}")
        sys.exit(1)
    except Exception as e:
        print(f"Erreur lors du lancement de l'application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
