"""Read-only LM Link metadata, isolated from inference and optional for discovery.

LM Studio's REST catalog does not consistently expose deviceIdentifier. The
SDK protocol does: null means local to the server, a string means LM Link.
Protocol reference: lmstudio-ai/lmstudio-python, json_api.py / sync_api.py;
field semantics: lmstudio-ai/lmstudio-js, ModelInfoBase.ts.
"""

import json
import re
import time
import uuid
from urllib.parse import urlsplit, urlunsplit


def _auth_message(api_key):
    if api_key:
        match = re.fullmatch(r"sk-lm-([A-Za-z0-9]{8}):([A-Za-z0-9]{20})", api_key)
        if not match:
            raise ValueError("Unsupported LM Studio token format")
        identifier, passkey = match.groups()
    else:
        identifier, passkey = f"guest:{uuid.uuid4()}", str(uuid.uuid4())
    return dict(authVersion=1, clientIdentifier=identifier, clientPasskey=passkey)


def _read_catalog(base_url, namespace, method, auth, deadline):
    from websocket import create_connection

    url = urlsplit(base_url)
    if url.scheme not in {"http", "https"} or not url.hostname:
        raise ValueError("Unsupported server URL")
    ws_url = urlunsplit(
        (
            "wss" if url.scheme == "https" else "ws",
            url.netloc,
            url.path.rstrip("/") + "/" + namespace,
            "",
            "",
        )
    )

    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError("LM Studio catalog deadline exceeded")
        return value

    socket = create_connection(
        ws_url,
        timeout=remaining(),
        suppress_origin=True,
        redirect_limit=0,
    )
    try:
        socket.settimeout(remaining())
        socket.send(json.dumps(auth))
        socket.settimeout(remaining())
        if json.loads(socket.recv()).get("success") is not True:
            raise ValueError("LM Studio catalog authentication failed")
        socket.settimeout(remaining())
        socket.send(json.dumps(dict(type="rpcCall", endpoint=method, callId=1)))
        # Ignore bounded server notices without extending the total deadline.
        for _ in range(32):
            socket.settimeout(remaining())
            message = json.loads(socket.recv())
            if message.get("callId") != 1:
                continue
            if message.get("type") != "rpcResult":
                raise ValueError("LM Studio catalog RPC failed")
            result = message.get("result")
            if not isinstance(result, list):
                raise ValueError("Invalid LM Studio catalog")
            return [row for row in result if isinstance(row, dict)]
        raise ValueError("Too many LM Studio notices")
    finally:
        socket.shutdown()


def fetch_provenance(base_url, api_key=None, timeout=8):
    """Return independent availability/loaded snapshots; never break REST use."""
    available, loaded = [], []
    deadline = time.monotonic() + min(timeout, 8)
    try:
        auth = _auth_message(api_key)
        available = _read_catalog(
            base_url,
            "system",
            "listDownloadedModels",
            auth,
            deadline,
        )
        loaded = _read_catalog(base_url, "llm", "listLoaded", auth, deadline)
    except Exception:
        # No token, host, server error payload or private machine names in logs.
        # Incompatible/older servers remain usable through their REST catalog.
        pass
    try:
        from .lmstudio_transport import device_names

        names = device_names(base_url, api_key, deadline)
        for row in available + loaded:
            if "deviceIdentifier" in row and (
                row["deviceIdentifier"] is None
                or isinstance(row["deviceIdentifier"], str)
            ):
                row["deviceName"] = names.get(row["deviceIdentifier"], "")
    except Exception:
        pass
    return available, loaded


def _sources(rows):
    sources = []
    for row in rows:
        # Absence is unknown; it must not be confused with explicit null.
        if "deviceIdentifier" not in row:
            continue
        device = row["deviceIdentifier"]
        if device is None or (isinstance(device, str) and device.strip()):
            if device not in sources:
                sources.append(device)
    return sources


def enrich_provenance(details, available, loaded):
    """Match exact routing IDs/keys, never display names shared by two models."""
    for model in details:
        key = model.get("model_key", model["id"])
        loaded_matches = [
            row
            for row in loaded
            if row.get("identifier") == model["id"]
            or (model["id"] == key and row.get("modelKey") == key)
        ]
        keys = {key} | {
            row["modelKey"]
            for row in loaded_matches
            if isinstance(row.get("modelKey"), str)
        }
        model["sources"] = _sources(
            [
                row
                for row in available
                if model["id"] == key
                and isinstance(row.get("modelKey"), str)
                and row["modelKey"] in keys
            ]
            + loaded_matches
        )
        model["loaded_sources"] = _sources(loaded_matches)
        model["device_names"] = {
            row["deviceIdentifier"]: row["deviceName"]
            for row in available + loaded
            if "deviceIdentifier" in row
            and (
                row["deviceIdentifier"] is None
                or isinstance(row["deviceIdentifier"], str)
            )
            and isinstance(row.get("deviceName"), str)
            and row["deviceName"].strip()
        }
    return details
