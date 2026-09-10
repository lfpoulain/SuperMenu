"""Private JSON-lines subprocess. Only this process loads Microsoft's native SDK.

The desktop process sends text through pipes, never command-line arguments or
an HTTP server. Model downloads are explicit commands, separate from inference.
"""

import json
import os
from pathlib import Path
import re
import shutil
import sys

from src.config.foundry_models import FOUNDRY_MODELS, MAX_INPUT_CHARS


class LocalError(Exception):
    """An actionable message safe to show without exposing SDK request bodies."""


def cache_root():
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SuperMenu" / "Foundry"


def platform_error():
    if sys.platform != "win32" or sys.getwindowsversion().build < 26100:
        return "Cette bêta Foundry Local nécessite Windows 11 24H2 ou plus récent."
    return ""


def clean_response(text):
    # Some catalog templates expose Qwen reasoning in content instead of a
    # separate field. Never insert it in the user's document.
    text = str(text or "")
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    elif "<think>" in text:
        raise LocalError(
            "Le modèle n'a pas terminé sa réponse. Essayez un texte plus court."
        )
    text = re.sub(r"<\|(?:im_end|im_start|endoftext)\|>", "", text).strip()
    if not text:
        raise LocalError("Le modèle local a renvoyé une réponse vide. Réessayez.")
    return text


def configure_text_model(root, model_id):
    """Configure only SuperMenu's private cache before the native model loads.

    SDK 1.2.4 does not expose Jinja template variables or load context options.
    Use Qwen's own non-thinking template branch and cap ORT's KV allocation.
    The weights and the user's other Foundry/Ollama caches are never modified.
    """
    root = Path(root).resolve()
    for manifest in (root / "cache" / "models").rglob("inference_model.json"):
        if not manifest.resolve().is_relative_to(root):
            continue
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("Name") != model_id:
            continue
        folder = manifest.parent
        template_path = folder / "chat_template.jinja"
        config_path = folder / "genai_config.json"
        if not all(
            p.resolve().is_relative_to(root) for p in (template_path, config_path)
        ):
            break
        template = template_path.read_text(encoding="utf-8")
        prefix = "{%- set enable_thinking = false %}\n"
        if "enable_thinking" not in template:
            raise LocalError(
                "Cette variante Qwen ne permet pas encore le mode texte direct de SuperMenu."
            )
        original = template
        # ORT GenAI 0.14.1's Jinja subset lacks the `is false` test.
        template = template.replace("enable_thinking is false", "not enable_thinking")
        if not template.startswith(prefix):
            template = prefix + template
        if template != original:
            atomic_text(template_path, template)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        search = config.setdefault("search", {})
        if search.get("max_length", 262144) > 32768:
            search["max_length"] = 32768
            atomic_text(config_path, json.dumps(config, ensure_ascii=False, indent=2))
        return
    raise LocalError(
        "Les fichiers du modèle sont incomplets. Relancez le téléchargement dans les réglages."
    )


def atomic_text(path, text):
    temporary = path.with_suffix(path.suffix + ".supermenu-tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


class FoundryRuntime:
    def __init__(self, root=None):
        self.root = Path(root) if root else cache_root()
        self.manager = None
        self.loaded_model = None
        self.hardware_prepared = False
        self.hardware_warning = ""

    def prepare_hardware(self, device, progress, *, retry=False):
        self.initialize()
        if device == "cpu" or (self.hardware_prepared and not retry):
            return
        self.hardware_prepared = False
        self.hardware_warning = ""
        # SDK 1.2.4 does not register EPs when the catalog is opened. Without
        # this step it exposes CPU variants even on an NVIDIA-equipped PC.
        try:
            available = {
                ep.name: ep.is_registered for ep in self.manager.discover_eps()
            }
            provider = next(
                (
                    name
                    for name in ("CUDAExecutionProvider", "WebGpuExecutionProvider")
                    if name in available
                ),
                None,
            )
            if provider and not available[provider]:
                label = (
                    "CUDA (NVIDIA)" if provider == "CUDAExecutionProvider" else "GPU"
                )
                progress(
                    {
                        "phase": "hardware",
                        "stage": f"Activation de {label}… Les composants installés sont réutilisés ; téléchargement uniquement si nécessaire."
                    }
                )
                # No callback: SDK 1.2.x has a native disposal race in its EP
                # progress callbacks. The UI shows an indeterminate bar.
                result = self.manager.download_and_register_eps(names=[provider])
                registered = {
                    ep.name for ep in self.manager.discover_eps() if ep.is_registered
                }
                if provider not in registered:
                    raise RuntimeError(result.status)
        except Exception:
            self.hardware_warning = (
                "L'accélération GPU n'a pas pu être préparée. Vérifiez la connexion et le pilote NVIDIA/GPU, "
                "puis cliquez sur Vérifier. Vous pouvez aussi choisir CPU explicitement."
            )
        self.hardware_prepared = True

    def initialize(self):
        if self.manager is not None:
            return
        if platform_error():
            raise LocalError(platform_error())
        from foundry_local_sdk import Configuration, FoundryLocalManager
        from foundry_local_sdk.logging_helper import LogLevel

        self.root.mkdir(parents=True, exist_ok=True)
        FoundryLocalManager.initialize(
            Configuration(
                app_name="SuperMenu",
                app_data_dir=str(self.root),
                log_level=LogLevel.ERROR,
            )
        )
        self.manager = FoundryLocalManager.instance

    def model(self, alias, device="auto"):
        if alias not in FOUNDRY_MODELS:
            raise LocalError("Choisissez Qwen3.5 4B ou Qwen3.5 9B dans les réglages.")
        self.initialize()
        model = self.manager.catalog.get_model(alias)
        if model is None:
            raise LocalError(
                "Ce Qwen n'est pas disponible pour ce PC dans le catalogue Microsoft."
            )
        variants = model.variants
        if device == "cpu":
            variants = [v for v in variants if str(v.info.runtime.device_type) == "CPU"]
        if not variants:
            raise LocalError(
                "Aucune variante de ce modèle n'est disponible pour le matériel choisi."
            )

        def priority(variant):
            runtime = variant.info.runtime
            if runtime.execution_provider == "CUDAExecutionProvider":
                return 0
            if str(runtime.device_type) == "GPU":
                return 1
            if str(runtime.device_type) == "NPU":
                return 2
            return 3

        # Do not accept the SDK's cached-CPU preference. Return an immutable
        # variant, so later catalog queries cannot retarget a loaded model.
        return min(variants, key=priority)

    @staticmethod
    def describe(model):
        variant = next(v for v in model.variants if v.id == model.id)
        info = variant.info
        return {
            "alias": model.alias,
            "variant": model.id,
            "cached": model.is_cached,
            "size_mb": info.file_size_mb,
            "device": str(info.runtime.device_type) if info.runtime else "CPU",
            "execution_provider": (
                info.runtime.execution_provider
                if info.runtime
                else "CPUExecutionProvider"
            ),
            "license": info.license or "Apache-2.0",
        }

    def execute(self, request, progress):
        operation = request.get("operation")
        device = "cpu" if request.get("device") == "cpu" else "auto"
        self.prepare_hardware(device, progress, retry=operation == "probe")
        if operation == "probe":
            return {
                "models": [
                    self.describe(self.model(a, device)) for a in FOUNDRY_MODELS
                ],
                "cache_dir": str(self.root / "cache" / "models"),
                "hardware_warning": self.hardware_warning if device == "auto" else "",
            }
        if device == "auto" and self.hardware_warning:
            raise LocalError(self.hardware_warning)
        model = self.model(request.get("model"), device)
        if operation == "download":
            info = self.describe(model)
            if not info["cached"]:
                required = ((info["size_mb"] or 8000) * 1024 * 1024) + 1024**3
                if shutil.disk_usage(self.root).free < required:
                    raise LocalError(
                        "Espace disque insuffisant pour télécharger ce modèle."
                    )
                model.download(lambda p: progress({"percent": round(p, 1)}))
            return self.describe(model)
        if operation != "generate":
            raise LocalError("Commande Foundry Local inconnue.")
        prompt, content = request.get("prompt", ""), request.get("content", "")
        if not isinstance(prompt, str) or not isinstance(content, str):
            raise LocalError("Cette bêta locale accepte uniquement du texte.")
        if content.startswith("data:image/"):
            raise LocalError(
                "La capture d'écran n'est pas encore prise en charge par cette bêta locale."
            )
        if len(prompt) + len(content) > MAX_INPUT_CHARS:
            raise LocalError(
                "Le texte dépasse la limite locale de 16 000 caractères. Réduisez la sélection."
            )
        if len((prompt + content).encode("utf-8")) > 24000:
            raise LocalError(
                "Le texte est trop long pour la mémoire de contexte locale. Réduisez la sélection."
            )
        if not model.is_cached:
            raise LocalError(
                "Téléchargez d'abord ce Qwen dans Réglages > Moteur IA > IA locale Microsoft."
            )
        if self.loaded_model is not None and self.loaded_model.id != model.id:
            self.loaded_model.unload()
            self.loaded_model = None
        if self.loaded_model is None:
            progress({"phase": "load", "stage": "Chargement du modèle installé en mémoire… Aucun téléchargement du modèle."})
            configure_text_model(self.root, model.id)
            model.load()
            self.loaded_model = model
        client = model.get_chat_client()
        client.settings.max_tokens = 2048
        client.settings.temperature = 0.2
        progress({"stage": "Traitement local du texte…"})
        result = client.complete_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Tu es un assistant de rédaction. Exécute la consigne sur le texte fourni. "
                        "Réponds directement avec le résultat demandé, sans exposer ton raisonnement."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{prompt}\n\n{content}" if content else prompt,
                },
            ]
        )
        if not result.choices or result.choices[0].finish_reason == "length":
            raise LocalError(
                "La réponse locale est trop longue et a été interrompue. Réduisez le texte."
            )
        return {"text": clean_response(result.choices[0].message.content)}


def pipe_stream(name, handle_id, mode):
    """Restore inherited pipes that PyInstaller's windowed bootloader hides."""
    stream = getattr(sys, name)
    if stream is not None:
        stream.reconfigure(encoding="utf-8")
        return stream
    import ctypes
    import msvcrt

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetStdHandle.restype = ctypes.c_void_p
    handle = kernel.GetStdHandle(handle_id)
    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY if mode == "r" else os.O_WRONLY)
    return os.fdopen(fd, mode, encoding="utf-8", buffering=1)


def main():
    source = pipe_stream("stdin", -10, "r")
    sink = pipe_stream("stdout", -11, "w")
    # SDK diagnostics must not corrupt the protocol or include private text.
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
    runtime = FoundryRuntime()

    def emit(payload):
        sink.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sink.flush()

    for line in source:
        request_id = ""
        try:
            request = json.loads(line)
            request_id = request["id"]
            result = runtime.execute(
                request, lambda p: emit({"id": request_id, "progress": p})
            )
            emit({"id": request_id, "result": result})
        except LocalError as exc:
            emit({"id": request_id, "error": str(exc)})
        except Exception:
            emit(
                {
                    "id": request_id,
                    "error": (
                        "Foundry Local n'a pas pu terminer l'opération. Vérifiez la connexion "
                        "pour un téléchargement, la mémoire disponible et les mises à jour Windows/pilotes."
                    ),
                }
            )
    return 0
