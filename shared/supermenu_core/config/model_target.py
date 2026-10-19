"""Per-prompt model choices without changing the application's saved defaults."""

import json

from .feature_modes import advanced_enabled

# Server fields describe the Text settings, never a prompt. Older versions and
# exported files stored them in each prompt; they are ignored and dropped so a
# prompt always follows the configured LM Studio / Ollama server.
SERVER_KEYS = ("endpoint", "endpoint_type")

# Foundry Local aliases offered by this platform. The Windows adapter registers
# its catalogue (src/config/foundry_models.py): the core never imports it.
_foundry_models = ()


def register_foundry_models(aliases):
    global _foundry_models
    _foundry_models = tuple(
        alias for alias in aliases if isinstance(alias, str) and alias
    )


def registered_foundry_models():
    return _foundry_models


def without_server(target):
    """Return a prompt target that follows the configured server."""
    return {
        key: value for key, value in (target or {}).items() if key not in SERVER_KEYS
    }


def normalize_model_target(value):
    if value in (None, {}):
        return {}
    if not isinstance(value, dict):
        raise ValueError("Le choix du modèle doit être un objet.")
    provider = value.get("provider", "custom")
    if not isinstance(provider, str) or provider not in {
        "custom",
        "openai",
        "foundry",
        "apple",
    }:
        raise ValueError("Moteur de texte inconnu pour ce prompt.")
    model = value.get("model", "")
    if not isinstance(model, str) or not model.strip() or len(model) > 512:
        raise ValueError("Choisissez un modèle valide pour ce prompt.")
    result = {"provider": provider, "model": model.strip()}
    if provider == "custom":
        for key in ("endpoint", "endpoint_type", "device_name"):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                result[key] = text.strip()[:2048]
        if "device" in value:
            device = value["device"]
            if device is not None and (
                not isinstance(device, str) or not device.strip()
            ):
                raise ValueError("Appareil LM Link invalide.")
            if isinstance(device, str) and len(device) > 512:
                raise ValueError("Appareil LM Link invalide.")
            if result.get("endpoint_type", "lmstudio") != "lmstudio":
                raise ValueError("Le choix du poste nécessite un serveur LM Studio.")
            result["device"] = device
    return result


class ModelTargetSettingsMixin:
    def get_model_device_names(self, endpoint):
        try:
            values = json.loads(self.settings.value("model_device_names", "{}"))
            names = values.get(endpoint.rstrip("/"), {})
            return {
                key: name
                for key, name in names.items()
                if isinstance(key, str) and isinstance(name, str)
            }
        except (AttributeError, TypeError, ValueError):
            return {}

    def set_model_device_name(self, endpoint, device, name):
        try:
            values = json.loads(self.settings.value("model_device_names", "{}"))
            if not isinstance(values, dict):
                values = {}
        except (TypeError, ValueError):
            values = {}
        names = self.get_model_device_names(endpoint)
        if name.strip():
            names[device] = name.strip()[:80]
        else:
            names.pop(device, None)
        values[endpoint.rstrip("/")] = names
        self.settings.setValue("model_device_names", json.dumps(values))

    def get_custom_model_target(self):
        try:
            result = normalize_model_target(
                json.loads(self.settings.value("custom_model_target", "{}"))
            )
            if result and result["model"] != self.get_custom_model():
                return {}
            if result.get("endpoint") and result["endpoint"].rstrip(
                "/"
            ) != self.get_custom_endpoint().rstrip("/"):
                return {}
            if (
                result.get("endpoint_type", self.get_custom_endpoint_type())
                != self.get_custom_endpoint_type()
            ):
                return {}
            return result
        except (TypeError, ValueError):
            return {}

    def set_custom_model_target(self, target):
        if target:
            target = {
                **target,
                "endpoint": self.get_custom_endpoint(),
                "endpoint_type": self.get_custom_endpoint_type(),
            }
        self.settings.setValue(
            "custom_model_target", json.dumps(normalize_model_target(target))
        )


class ModelTargetSettings:
    """Read-through settings view; overrides belong only to this request."""

    def __init__(self, settings, target):
        self.base = settings
        # Only the model and its LM Link device belong to the prompt. A server
        # stored by an older version or carried by an imported file is ignored:
        # text is never sent to a server other than the configured one.
        self.target = without_server(normalize_model_target(target))
        if self.target.get("provider") == "openai":
            from .openai_models import AVAILABLE_MODELS, LEGACY_MODEL_MIGRATIONS

            if (
                self.target["model"] not in AVAILABLE_MODELS
                and self.target["model"] not in LEGACY_MODEL_MIGRATIONS
            ):
                raise ValueError(
                    "Le modèle OpenAI choisi n’est pas proposé par cette version de SuperMenu."
                )
        # Without a registered catalogue (macOS), the platform adapter refuses
        # the Foundry engine itself with a clearer message.
        foundry_models = registered_foundry_models()
        if (
            self.target.get("provider") == "foundry"
            and foundry_models
            and self.target["model"] not in foundry_models
        ):
            raise ValueError(
                "Le modèle Foundry choisi n’est pas proposé par cette version de SuperMenu."
            )
        if "device" in self.target and self.get_custom_endpoint_type() != "lmstudio":
            raise ValueError("Le choix du poste nécessite un serveur LM Studio.")

    def __getattr__(self, name):
        return getattr(self.base, name)

    def get_ai_provider(self):
        return self.target["provider"]

    def get_use_custom_endpoint(self):
        return self.get_ai_provider() == "custom"

    def get_model(self):
        return (
            self.target["model"]
            if self.get_ai_provider() == "openai"
            else self.base.get_model()
        )

    def get_custom_model(self):
        return self.target["model"]

    def get_foundry_model(self):
        return self.target["model"]

    def get_custom_endpoint(self):
        return self.base.get_custom_endpoint()

    def get_custom_endpoint_type(self):
        return self.base.get_custom_endpoint_type()

    def get_custom_model_target(self):
        return self.target

    def get_custom_endpoint_api_key(self):
        # The request always goes to the configured server: its credential.
        return self.base.get_custom_endpoint_api_key()

    def get_openai_reasoning_effort(self, model=None):
        """Read the general effort for this model without ever rewriting it.

        The application's getter may persist a normalized value when the stored
        effort does not suit the requested model (gpt-5.4 has no "max"): a
        prompt's own model must not change the general setting.
        """
        from .openai_models import (
            get_default_reasoning_effort_for_model,
            normalize_openai_model,
            normalize_reasoning_effort,
        )

        model = normalize_openai_model(model or self.get_model())
        store = getattr(self.base, "settings", None)
        if callable(getattr(store, "value", None)):
            effort = store.value(
                "openai_reasoning_effort",
                get_default_reasoning_effort_for_model(model),
            )
        else:
            getter = getattr(self.base, "get_openai_reasoning_effort", None)
            effort = getter() if getter else self.base.get_reasoning_effort()
        return normalize_reasoning_effort(model, effort)

    def get_reasoning_effort(self):
        if self.get_use_custom_endpoint():
            return self.base.get_custom_reasoning_effort()
        return self.get_openai_reasoning_effort(self.get_model())


def settings_for_prompt(settings, prompt_id):
    # Without the advanced features every prompt uses the Text settings; the
    # stored choice is kept for when they are turned back on.
    if not advanced_enabled(settings):
        return settings
    prompt = settings.get_prompt(prompt_id) or {}
    target = prompt.get("model_target")
    return ModelTargetSettings(settings, target) if target else settings
