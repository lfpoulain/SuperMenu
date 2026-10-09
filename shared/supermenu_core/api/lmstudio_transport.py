"""Bounded SDK transport for explicit local / LM Link inference.

Wire schemas: lmstudio-ai/lmstudio-js lms-external-backend-interfaces.
Never changes LM Studio's shared preferred-device setting.
"""

from contextlib import ExitStack

import json
import time
from urllib.parse import urlsplit, urlunsplit

from .lmstudio_provenance import _auth_message


class StudioSession:
    def __init__(self, base_url, namespace, auth, deadline, cancelled=None):
        from websocket import create_connection

        self.deadline = deadline
        self.cancelled = cancelled
        self.socket = None
        self.counter = 0
        url = urlsplit(base_url)
        if url.scheme not in {"http", "https"} or not url.hostname:
            raise ValueError("Adresse du serveur LM Studio invalide.")
        ws_url = urlunsplit(
            (
                "wss" if url.scheme == "https" else "ws",
                url.netloc,
                url.path.rstrip("/") + "/" + namespace,
                "",
                "",
            )
        )
        try:
            self.socket = create_connection(
                ws_url,
                timeout=min(10, self.remaining()),
                suppress_origin=True,
                redirect_limit=0,
            )
            self.send(auth)
            if self.receive().get("success") is not True:
                raise RuntimeError(
                    "LM Studio a refusé la connexion. Vérifiez le jeton du serveur."
                )
        except Exception:
            self.close()
            raise

    def remaining(self):
        if self.cancelled is not None and self.cancelled.is_set():
            raise RuntimeError("Requête annulée.")
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError(
                "Le serveur LM Studio n’a pas répondu dans le délai prévu."
            )
        return seconds

    def send(self, message):
        self.socket.settimeout(min(10, self.remaining()))
        self.socket.send(json.dumps(message))

    def receive(self):
        from websocket import WebSocketTimeoutException

        while True:
            self.socket.settimeout(min(1, self.remaining()))
            try:
                message = json.loads(self.socket.recv())
            except WebSocketTimeoutException:
                continue
            if not isinstance(message, dict):
                raise ValueError("Réponse LM Studio invalide.")
            return message

    def rpc(self, endpoint, parameter=None):
        self.counter += 1
        call_id = self.counter
        message = dict(type="rpcCall", endpoint=endpoint, callId=call_id)
        if parameter is not None:
            message["parameter"] = parameter
        self.send(message)
        while True:
            result = self.receive()
            if result.get("callId") != call_id:
                continue
            if result.get("type") == "rpcResult":
                return result.get("result")
            raise RuntimeError(
                "LM Studio ne peut pas effectuer cette opération sur le poste choisi."
            )

    def channel(self, endpoint, parameter):
        self.counter += 1
        channel_id = self.counter
        self.send(
            dict(
                type="channelCreate",
                endpoint=endpoint,
                channelId=channel_id,
                creationParameter=parameter,
            )
        )
        completed = False
        try:
            while True:
                result = self.receive()
                if result.get("channelId") != channel_id:
                    continue
                kind = result.get("type")
                if kind == "channelClose":
                    completed = True
                    return
                if kind == "channelError":
                    raise RuntimeError(
                        "Le modèle ne peut pas être utilisé sur le poste choisi. "
                        "Vérifiez que ce poste est connecté et que le modèle y est disponible."
                    )
                if kind == "channelSend" and isinstance(result.get("message"), dict):
                    yield result["message"]
        finally:
            if not completed:
                try:
                    self.socket.settimeout(1)
                    self.socket.send(
                        json.dumps(
                            dict(
                                type="channelSend",
                                channelId=channel_id,
                                message={"type": "cancel"},
                            )
                        )
                    )
                except Exception:
                    pass

    def close(self):
        if self.socket is not None:
            self.socket.shutdown()
            self.socket = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def device_names(base_url, api_key, deadline):
    with StudioSession(
        base_url, "repository", _auth_message(api_key), deadline
    ) as session:
        status = session.rpc("lmLinkStatus")
    if not isinstance(status, dict):
        return {}
    names = {None: status.get("deviceName", "")}
    for peer in status.get("peers", []):
        if isinstance(peer, dict) and isinstance(peer.get("deviceIdentifier"), str):
            names[peer["deviceIdentifier"]] = peer.get("deviceName", "")
    return {
        key: value
        for key, value in names.items()
        if isinstance(value, str) and value.strip()
    }


def targeted_completion(
    base_url,
    api_key,
    data,
    device,
    *,
    cancelled=None,
    include_reasoning=False,
    timeout=300
):
    """Resolve on one device, then predict on the returned immutable instance."""
    deadline = time.monotonic() + timeout
    auth = _auth_message(api_key)
    with ExitStack() as resources:
        session = resources.enter_context(
            StudioSession(base_url, "llm", auth, deadline, cancelled)
        )
        info = None
        for packet in session.channel(
            "getOrLoad",
            {
                "identifier": data["model"],
                "deviceIdentifier": device,
                "loadTtlMs": 300000,
                "loadConfigStack": {"layers": []},
            },
        ):
            if packet.get("type") in {"alreadyLoaded", "loadSuccess"}:
                info = packet.get("info")
        if (
            not isinstance(info, dict)
            or "deviceIdentifier" not in info
            or info["deviceIdentifier"] != device
            or not info.get("instanceReference")
        ):
            raise RuntimeError(
                "LM Studio n’a pas confirmé le poste choisi. Aucun texte n’a été envoyé au modèle."
            )
        parts = []
        native_input = data.get("input", "")
        if isinstance(native_input, str):
            parts.append({"type": "text", "text": native_input})
        elif isinstance(native_input, list):
            for item in native_input:
                if item.get("type") in {"text", "message"}:
                    parts.append({"type": "text", "text": item.get("content", "")})
                elif item.get("type") == "image":
                    encoded = item["data_url"].split(";base64,", 1)[1]
                    files = resources.enter_context(
                        StudioSession(base_url, "files", auth, deadline, cancelled)
                    )
                    uploaded = files.rpc(
                        "uploadFileBase64",
                        {"name": "capture.png", "contentBase64": encoded},
                    )
                    parts.append({"type": "file", "name": "capture.png", **uploaded})
        fields = [
            {
                "key": "llm.prediction.maxPredictedTokens",
                "value": {"checked": False, "value": 1},
            }
        ]
        reasoning = data.get("reasoning")
        if reasoning in {"off", "on"}:
            fields.append(
                {
                    "key": "llm.prediction.reasoning.enableThinking",
                    "value": reasoning == "on",
                }
            )
        elif reasoning:
            # SDK enableThinking only controls on/off; never silently discard a
            # requested effort tier. This is handled via the model's base template.
            base = session.rpc(
                "getBasePredictionConfig",
                {
                    "specifier": {
                        "type": "instanceReference",
                        "instanceReference": info["instanceReference"],
                    },
                },
            )
            template = next(
                (
                    field["value"]
                    for field in base.get("fields", [])
                    if field.get("key") == "llm.prediction.promptTemplate"
                ),
                None,
            )
            if not isinstance(template, dict) or template.get("type") != "jinja":
                raise RuntimeError(
                    "Ce modèle ne permet pas de régler ce niveau de raisonnement via LM Link. Choisissez le réglage du moteur."
                )
            original = template.get("jinjaPromptTemplate", {}).get("template")
            if not isinstance(original, str) or not original:
                raise RuntimeError(
                    "Le template de raisonnement de ce modèle est indisponible."
                )
            # The SDK exposes the Jinja template, but no native effort option.
            # Supply the same standard variable expected by effort-based models.
            template = {
                **template,
                "jinjaPromptTemplate": {
                    "template": "{% set reasoning_effort = "
                    + json.dumps(reasoning)
                    + " %}"
                    + original,
                },
            }
            fields.append({"key": "llm.prediction.promptTemplate", "value": template})
        text, reasoning_text, finished = [], [], False
        stop_reason = None
        for packet in session.channel(
            "predict",
            {
                "modelSpecifier": {
                    "type": "instanceReference",
                    "instanceReference": info["instanceReference"],
                },
                "history": {"messages": [{"role": "user", "content": parts}]},
                "predictionConfigStack": {
                    "layers": [
                        {"layerName": "apiOverride", "config": {"fields": fields}}
                    ]
                },
            },
        ):
            if packet.get("type") == "fragment":
                fragment = packet.get("fragment", {})
                kind = fragment.get("reasoningType", "none")
                if kind == "none":
                    text.append(fragment.get("content", ""))
                elif kind == "reasoning":
                    reasoning_text.append(fragment.get("content", ""))
            elif packet.get("type") == "success":
                finished = True
                stop_reason = packet.get("stats", {}).get("stopReason")
        if not finished:
            raise RuntimeError(
                "La connexion au modèle a été interrompue avant la fin de la réponse."
            )
        output = [{"type": "message", "content": "".join(text)}]
        if include_reasoning and reasoning_text:
            output.insert(0, {"type": "reasoning", "content": "".join(reasoning_text)})
        if stop_reason == "userStopped":
            raise RuntimeError("La génération a été interrompue.")
        if stop_reason == "maxPredictedTokensReached":
            stop_reason = "max_tokens"
        return {"output": output, "stop_reason": stop_reason}
