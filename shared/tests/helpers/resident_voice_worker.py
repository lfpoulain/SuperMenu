"""Deterministic private worker exercising the actual Qt pipe lifecycle."""

import json
import sys


def emit(kind, sid, **fields):
    print(json.dumps({"event": kind, "session_id": sid, **fields}), flush=True)


def emit_sessionless(kind, **fields):
    # Mirrors worker-level failures (SDK, model load) reported without a session.
    print(json.dumps({"event": kind, **fields}), flush=True)


previous = None
for line in sys.stdin:
    request = json.loads(line)
    if request.get("action") in {"cancel", "stop"}:
        continue
    sid = request["session_id"]
    mode = request.get("mode", "")
    if mode == "sessionless_error":
        emit("progress", sid, phase="load", message="Chargement…")
        emit_sessionless("error", message=request.get("text", ""))
        sys.exit(1)
    if mode == "silent":
        continue
    if mode == "hardware":
        emit("progress", sid, phase="verify", message="Vérification…")
        emit("progress", sid, phase="hardware", message="Activation du GPU…")
        emit("progress", sid, phase="load", message="Chargement…")
    emit("ready", sid)
    if mode == "late_progress":
        emit("progress", sid, phase="hardware", message="Tardif")
    if previous:
        emit("transcript", previous, text="STALE")
        emit("complete", previous, text="STALE")
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("action") == "stop":
            emit("complete", sid, text=request.get("text", ""))
            break
        if message.get("action") == "cancel":
            if mode == "drain_error":
                emit("error", sid, message="Fermeture impossible.")
                sys.exit(1)
            if mode == "drain_sessionless_error":
                emit_sessionless("error", message="Fermeture impossible.")
                sys.exit(1)
            if mode == "drain_exit":
                sys.exit(1)
            if mode == "drain_silent":
                continue
            emit("cancelled", sid)
            break
        emit("transcript", sid, text=request.get("text", ""))
    previous = sid
