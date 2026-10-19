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
import traceback

# Ajouter la racine du projet au chemin d'importation Python
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)


def run_packaged_smoke_test():
    """Validate bundled assets without starting the desktop event loop."""
    from PySide6.QtCore import qVersion
    from PySide6.QtMultimedia import QAudioSource  # noqa: F401
    from PySide6.QtWebSockets import QWebSocket  # noqa: F401
    from supermenu_core.config.openai_models import (
        AVAILABLE_MODELS,
        DEFAULT_OPENAI_MODEL,
    )
    from src.config.build_info import APP_VERSION, BUILD_CHANNEL
    from src.utils.paths import packaged_resource_status

    status = packaged_resource_status()
    status["qt_version"] = qVersion()
    status["live_speech_modules_ok"] = True
    expected_models = [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.4",
    ]
    status["models"] = AVAILABLE_MODELS
    status["default_model"] = DEFAULT_OPENAI_MODEL
    status["model_config_ok"] = (
        AVAILABLE_MODELS == expected_models and DEFAULT_OPENAI_MODEL == "gpt-5.6-sol"
    )
    status["app_version"] = APP_VERSION
    status["build_channel"] = BUILD_CHANNEL
    status["build_config_ok"] = BUILD_CHANNEL in {"stable", "beta"} and (
        APP_VERSION == "dev"
        or re.fullmatch(
            r"\d+\.\d+\.\d+(?:-beta\.\d+)?",
            APP_VERSION,
        )
        is not None
    )
    status["ok"] = (
        status["ok"] and status["model_config_ok"] and status["build_config_ok"]
    )

    print(json.dumps(status, ensure_ascii=False))
    return 0 if status["ok"] else 1


def run_foundry_smoke_test():
    """Exercise bundled native DLLs and windowed child pipes, without weights."""
    import subprocess
    from src.api.foundry_client import worker_command
    from src.api.foundry_worker import pipe_stream
    from src.config.foundry_models import FOUNDRY_MODELS

    try:
        sys.stdout = pipe_stream("stdout", -11, "w")
    except (OSError, ValueError, TypeError):
        pass  # No output handle when invoked by Start-Process without redirect.
    program, args = worker_command()
    child = subprocess.run(
        [program, *args], input=json.dumps({"id": "smoke", "operation": "probe", "device": "cpu"}) + "\n",
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        encoding="utf-8", timeout=120, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    for line in child.stdout.splitlines():
        try:
            response = json.loads(line)
        except ValueError:
            continue
        if not isinstance(response, dict) or response.get("id") != "smoke":
            continue
        if "progress" in response:
            continue
        if "error" in response:
            print(json.dumps({"foundry_ok": False, "error": response["error"]}))
            return 1
        models = response.get("result", {}).get("models", [])
        ok = child.returncode == 0 and {m["alias"] for m in models} == set(FOUNDRY_MODELS)
        print(json.dumps({"foundry_ok": ok, "models": models}))
        return 0 if ok else 1
    print(json.dumps({"foundry_ok": False, "child_exit": child.returncode, "output": child.stdout[-2000:]}))
    return 1


# Modes sans interface : ils ne doivent jamais ouvrir de boîte de dialogue
# (la CI et le processus parent attendent leur sortie).
_HEADLESS_FLAGS = (
    "--microphone-smoke-test",
    "--speech-worker",
    "--foundry-worker",
    "--foundry-smoke-test",
    "--smoke-test",
)


def report_startup_failure(message):
    """Garde une trace d'un échec de démarrage, même dans l'EXE fenêtré.

    Dans l'EXE (console=False), sys.stdout et sys.stderr valent None : les
    print() ne vont nulle part. Le journal et une boîte de message minimale
    évitent une application qui « ne se lance pas » sans explication.
    """
    failure = sys.exc_info()
    try:
        from src.utils.logger import logger

        # Écrit aussi sur la console quand elle existe (mode développement).
        logger.critical(message, exc_info=failure)
    except Exception:
        print(message)
        traceback.print_exception(*failure)
    if any(flag in sys.argv for flag in _HEADLESS_FLAGS):
        return
    if not (getattr(sys, "frozen", False) or sys.stdout is None):
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            f"{message}\n\nDétails dans %LOCALAPPDATA%\\SuperMenu\\logs\\supermenu.log",
            "SuperMenu",
            0x10,  # MB_ICONERROR
        )
    except Exception:
        pass


# Importer et lancer l'application
if __name__ == "__main__":
    try:
        if "--microphone-smoke-test" in sys.argv:
            from supermenu_core.audio.diagnostics import run_microphone_check
            from src.api.foundry_worker import pipe_stream
            sys.stdout = pipe_stream("stdout", -11, "w")
            rate = 24000 if "--24000" in sys.argv else 16000
            sys.exit(run_microphone_check(lambda result: print(json.dumps(result), flush=True), rate))
        if "--speech-worker" in sys.argv:
            from src.audio.foundry_speech_worker import main
            sys.exit(main())
        if "--foundry-worker" in sys.argv:
            from src.api.foundry_worker import main
            sys.exit(main())
        if "--foundry-smoke-test" in sys.argv:
            sys.exit(run_foundry_smoke_test())
        if "--smoke-test" in sys.argv:
            sys.exit(run_packaged_smoke_test())
        from src.utils.logger import install_crash_reporting

        install_crash_reporting()
        from src.main import SuperMenu

        app = SuperMenu()
        sys.exit(app.run())
    except ImportError as e:
        report_startup_failure(f"Erreur d'importation: {e}")
        print(f"Chemin d'importation Python: {sys.path}")
        sys.exit(1)
    except Exception as e:
        report_startup_failure(f"Erreur lors du lancement de l'application: {e}")
        sys.exit(1)
