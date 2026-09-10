"""Deterministic private worker exercising the actual Qt pipe lifecycle."""

import json
import sys


def emit(kind, sid, **fields):
    print(json.dumps({"event": kind, "session_id": sid, **fields}), flush=True)


previous = None
for line in sys.stdin:
    request = json.loads(line)
    if request.get("action") in {"cancel", "stop"}:
        continue
    sid = request["session_id"]
    emit("ready", sid)
    if previous:
        emit("transcript", previous, text="STALE")
        emit("complete", previous, text="STALE")
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("action") == "stop":
            emit("complete", sid, text=request.get("text", ""))
            break
        if message.get("action") == "cancel":
            emit("cancelled", sid)
            break
        emit("transcript", sid, text=request.get("text", ""))
    previous = sid
