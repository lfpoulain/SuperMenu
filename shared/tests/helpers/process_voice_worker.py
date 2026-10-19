"""Deterministic one-shot worker for ProcessSpeechBackend (probe/download)."""

import json
import os
import signal
import sys


def emit(kind, **fields):
    print(json.dumps({"event": kind, **fields}), flush=True)


def crash():
    sys.stdout.flush()
    if sys.platform == "win32":
        os._exit(0xC0000005 - 2**32)  # Access violation, reported as a crash.
    os.kill(os.getpid(), signal.SIGKILL)


request = json.loads(sys.stdin.readline())
mode = request.get("mode", "")
if mode == "result":
    emit("progress", phase="verify", message="Vérification…")
    emit("progress", phase="hardware", message="Activation du GPU…")
    emit("result", data={"cached": True, "device": "CPU"})
elif mode == "error":
    emit("progress", phase="verify", message="Vérification…")
    emit("error", message="Nemotron n’est pas disponible.")
elif mode == "exit":
    sys.exit(0)
elif mode == "crash":
    emit("progress", phase="download", message="Téléchargement…", percent=12)
    crash()
elif mode == "error_then_crash":
    emit("error", message="Mémoire insuffisante.")
    crash()
elif mode == "invalid":
    print("pas du json", flush=True)
elif mode == "flood":
    sys.stdout.write("x" * 2_100_000)
    sys.stdout.flush()
elif mode == "ready":
    emit("ready")
    emit("progress", phase="hardware", message="Tardif")
    for line in sys.stdin:
        if json.loads(line).get("action") == "stop":
            emit("complete", text="Bonjour")
            break
