"""Private Nemotron worker: PCM stays in inherited pipes and memory."""

import base64
import json
import os
import sys
import threading

from supermenu_core.audio.settings import NEMOTRON_MODEL, MAX_DICTATION_SECONDS
from src.api.foundry_worker import FoundryRuntime, LocalError, pipe_stream


def select_speech_model(runtime, device, emit):
    runtime.prepare_hardware(
        device,
        lambda p: emit(
            {
                "event": "progress",
                "phase": p.get("phase", "hardware"),
                "message": p["stage"],
            }
        ),
    )
    if runtime.hardware_warning and device != "cpu":
        raise LocalError(runtime.hardware_warning)
    model = runtime.manager.catalog.get_model(NEMOTRON_MODEL)
    if model is None:
        raise LocalError(
            "Nemotron 3.5 n’est pas disponible dans le catalogue pour ce PC."
        )
    variants = model.variants
    if device == "cpu":
        variants = [v for v in variants if str(v.info.runtime.device_type) == "CPU"]
    if not variants:
        raise LocalError("Aucune variante compatible de Nemotron n’est disponible.")
    return min(
        variants,
        key=lambda v: (
            0
            if v.info.runtime.execution_provider == "CUDAExecutionProvider"
            else 1 if str(v.info.runtime.device_type) == "GPU" else 2
        ),
    )


def describe(model):
    return {
        "cached": model.is_cached,
        "model": NEMOTRON_MODEL,
        "device": (
            "GPU — CUDA (NVIDIA)"
            if model.info.runtime.execution_provider == "CUDAExecutionProvider"
            else str(model.info.runtime.device_type)
        ),
        "size_mb": model.info.file_size_mb,
    }


def run(source, emit, runtime=None):
    runtime = runtime or FoundryRuntime()
    request = json.loads(source.readline())
    action = request.get("action", "start")
    if action not in {"probe", "download", "start"}:
        raise LocalError("Opération vocale inconnue.")
    emit(
        {
            "event": "progress",
            "phase": "verify",
            "message": "Vérification de Nemotron et des fichiers déjà installés…",
        }
    )
    model = select_speech_model(runtime, request.get("device", "auto"), emit)
    if action == "probe":
        emit({"event": "result", "data": describe(model)})
        return
    if action == "download":
        if not model.is_cached:
            last = [-1]

            def progress(percent):
                value = round(percent)
                if value != last[0]:
                    last[0] = value
                    emit(
                        {
                            "event": "progress",
                            "phase": "download",
                            "message": "Téléchargement de Nemotron 3.5…",
                            "percent": value,
                        }
                    )

            model.download(progress)
        emit({"event": "result", "data": describe(model)})
        return
    if not model.is_cached:
        raise LocalError(
            "Téléchargez le modèle vocal Nemotron dans les réglages de dictée avant de commencer."
        )
    session = None
    reader = None
    result = {"text": "", "error": None}
    try:
        emit(
            {
                "event": "progress",
                "phase": "load",
                "message": "Nemotron est déjà sur ce PC. Chargement en mémoire · "
                + describe(model)["device"],
            }
        )
        model.load()
        session = model.get_audio_client().create_live_transcription_session()
        session.settings.language = request.get("language") or "auto"
        session.settings.sample_rate = 16000
        session.settings.channels = 1
        session.start()

        def read():
            try:
                for event in session.get_stream():
                    text = event.content[0].text if event.content else ""
                    # SDK 1.2.4 emits deltas, followed by the full final transcript.
                    result["text"] = text if event.is_final else result["text"] + text
                    emit({"event": "transcript", "text": result["text"].strip()})
            except Exception as exc:
                result["error"] = exc
                emit(
                    {
                        "event": "error",
                        "message": "Nemotron a interrompu la transcription. Réessayez.",
                    }
                )

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        emit({"event": "ready"})
        total = 0
        stopped = False
        for line in source:
            if len(line) > 100_000:
                raise LocalError("Bloc audio trop volumineux.")
            message = json.loads(line)
            if message.get("action") == "stop":
                stopped = True
                break
            pcm = base64.b64decode(message["audio"], validate=True)
            if len(pcm) % 2:
                raise LocalError("Format audio invalide.")
            total += len(pcm)
            if total > 16000 * 2 * (MAX_DICTATION_SECONDS + 2):
                raise LocalError("La dictée a atteint sa durée maximale.")
            session.append(pcm)
        session.stop()
        reader.join(15)
        if reader.is_alive() or result["error"]:
            raise LocalError("Nemotron n’a pas pu finaliser la dictée. Réessayez.")
        if stopped:
            emit({"event": "complete", "text": result["text"].strip()})
    finally:
        if session:
            session.stop()
        model.unload()


def main():
    source = pipe_stream("stdin", -10, "r")
    sink = pipe_stream("stdout", -11, "w")
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
    lock = threading.Lock()

    def emit(event):
        with lock:
            sink.write(json.dumps(event, ensure_ascii=False) + "\n")
            sink.flush()

    try:
        run(source, emit)
        return 0
    except LocalError as exc:
        emit({"event": "error", "message": str(exc)})
    except Exception:
        emit(
            {
                "event": "error",
                "message": "Foundry n’a pas pu terminer la dictée. Vérifiez la disponibilité du modèle, la mémoire et les pilotes GPU.",
            }
        )
    return 1
