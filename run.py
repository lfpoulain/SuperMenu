#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script de lancement pour SuperMenu.
Ce script permet de lancer l'application depuis le répertoire racine.
"""

import os
import sys
import json
import re
import subprocess

# Ajouter la racine du projet au chemin d'importation Python
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)


def run_packaged_smoke_test():
    """Validate bundled assets without starting the desktop event loop."""
    from src.config.openai_models import AVAILABLE_MODELS, DEFAULT_OPENAI_MODEL
    from src.config.build_info import APP_VERSION, BUILD_CHANNEL
    from src.utils.paths import packaged_resource_status

    status = packaged_resource_status()
    if status["ok"]:
        try:
            result = subprocess.run(
                [status["ffmpeg"], "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
            status["ffmpeg_exit_code"] = result.returncode
            status["ok"] = result.returncode == 0
        except Exception as exc:
            status["ok"] = False
            status["error"] = str(exc)

    expected_models = [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.4",
    ]
    status["models"] = AVAILABLE_MODELS
    status["default_model"] = DEFAULT_OPENAI_MODEL
    status["model_config_ok"] = (
        AVAILABLE_MODELS == expected_models
        and DEFAULT_OPENAI_MODEL == "gpt-5.6-sol"
    )
    status["app_version"] = APP_VERSION
    status["build_channel"] = BUILD_CHANNEL
    status["build_config_ok"] = (
        BUILD_CHANNEL in {"stable", "beta"}
        and (
            APP_VERSION == "dev"
            or re.fullmatch(
                r"\d+\.\d+\.\d+(?:-beta\.\d+)?",
                APP_VERSION,
            )
            is not None
        )
    )
    status["ok"] = (
        status["ok"]
        and status["model_config_ok"]
        and status["build_config_ok"]
    )

    print(json.dumps(status, ensure_ascii=False))
    return 0 if status["ok"] else 1


# Importer et lancer l'application
if __name__ == "__main__":
    try:
        if "--smoke-test" in sys.argv:
            sys.exit(run_packaged_smoke_test())
        from src.main import SuperMenu
        app = SuperMenu()
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
