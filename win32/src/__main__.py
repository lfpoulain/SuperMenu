#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Point d'entrée principal pour l'application SuperMenu.
Ce fichier permet de lancer l'application en tant que module Python.
"""

import sys
from src.utils.logger import install_crash_reporting
from src.main import SuperMenu

if __name__ == "__main__":
    install_crash_reporting()
    app = SuperMenu()
    sys.exit(app.run())
