"""Settings interface the shared core relies on.

Both applications hand their own ``Settings`` object to shared code: provider
clients, prompt and voice editors, dictation, transfers and restores. This
module states what that code may call, so a method renamed or dropped on one
platform fails a test instead of a user action. The shared mixins (speech,
voice prompts, text prompts, model targets) supply part of it; each platform
implements the rest. Optional platform features, such as ``get_foundry_model``
on Windows, are probed with ``hasattr`` and stay out of the contract. The
feature switch getters are probed too, so that test doubles without them keep
every feature on, but both applications must provide them.
"""

import inspect
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SettingsStore(Protocol):
    """Subset of ``QSettings`` used by the shared mixins and restores."""

    def value(self, key, defaultValue=None, type=None) -> Any: ...

    def setValue(self, key, value) -> None: ...

    def contains(self, key) -> bool: ...

    def remove(self, key) -> None: ...

    def sync(self) -> None: ...


@runtime_checkable
class CoreSettings(Protocol):
    settings: SettingsStore
    default_prompts: dict
    default_voice_prompts: dict

    def sync(self) -> None: ...

    # Text provider
    def get_ai_provider(self) -> str: ...

    def get_api_key(self) -> Any: ...

    def set_api_key(self, api_key) -> None: ...

    def get_model(self) -> str: ...

    def get_openai_reasoning_effort(self, model=None) -> str: ...

    def get_custom_reasoning_effort(self) -> str: ...

    def get_reasoning_effort(self) -> str: ...

    def get_use_custom_endpoint(self) -> bool: ...

    def get_custom_endpoint(self) -> str: ...

    def get_custom_endpoint_type(self) -> str: ...

    def get_custom_endpoint_api_key(self) -> str: ...

    def get_custom_model(self) -> str: ...

    def get_custom_model_target(self) -> dict: ...

    def get_model_device_names(self, endpoint) -> dict: ...

    def set_model_device_name(self, endpoint, device, name) -> None: ...

    # Application
    def get_advanced_features_enabled(self) -> bool: ...

    def set_advanced_features_enabled(self, enabled) -> None: ...

    def get_experimental_features_enabled(self) -> bool: ...

    def set_experimental_features_enabled(self, enabled) -> None: ...

    def get_text_idle_seconds(self) -> int: ...

    def get_theme(self) -> str: ...

    def get_update_channel(self) -> str: ...

    def set_update_channel(self, channel) -> None: ...

    def set_last_update_check_date(self, date_value) -> None: ...

    # Text prompts
    def get_prompts(self) -> dict: ...

    def get_prompt(self, prompt_id) -> Any: ...

    def set_prompts(self, prompts) -> None: ...

    def update_prompt(
        self,
        prompt_id,
        name,
        prompt,
        status,
        insert_directly=False,
        position=None,
        hotkey="",
        reasoning_mode=None,
        model_target=None,
    ) -> None: ...

    def add_prompt(
        self,
        prompt_id,
        name,
        prompt,
        status,
        insert_directly=False,
        position=999,
        hotkey="",
        reasoning_mode=None,
        model_target=None,
    ) -> str: ...

    def delete_prompt(self, prompt_id) -> Any: ...

    # Voice prompts
    def get_voice_prompts(self) -> dict: ...

    def get_voice_prompt(self, prompt_id) -> Any: ...

    def set_voice_prompts(self, prompts) -> None: ...

    def update_voice_prompt(
        self,
        prompt_id,
        name,
        prompt,
        status,
        insert_directly=False,
        position=None,
        include_selected_text=False,
        prompt_order="prompt_transcription_selected",
        reasoning_mode=None,
        model_target=None,
    ) -> None: ...

    def add_voice_prompt(
        self,
        prompt_id,
        name,
        prompt,
        status,
        insert_directly=False,
        position=999,
        include_selected_text=False,
        prompt_order="prompt_transcription_selected",
        reasoning_mode=None,
        model_target=None,
    ) -> str: ...

    def delete_voice_prompt(self, prompt_id) -> Any: ...

    # Speech recognition
    def get_speech_provider(self) -> str: ...

    def set_speech_provider(self, value) -> None: ...

    def get_speech_device(self) -> str: ...

    def set_speech_device(self, value) -> None: ...

    def get_speech_microphone(self) -> str: ...

    def set_speech_microphone(self, value) -> None: ...

    def get_speech_idle_seconds(self) -> int: ...

    def set_speech_idle_seconds(self, value) -> None: ...

    def get_transcription_languages(self) -> Any: ...

    def set_transcription_languages(self, value) -> None: ...

    def get_transcription_prompt(self) -> str: ...

    def set_transcription_prompt(self, value) -> None: ...

    def get_transcription_keywords(self) -> Any: ...

    def set_transcription_keywords(self, value) -> None: ...

    # Dictation
    def get_dictation_hotkey(self) -> str: ...

    def set_dictation_hotkey(self, value) -> None: ...

    def get_dictation_hotkey_mode(self) -> str: ...

    def set_dictation_hotkey_mode(self, value) -> None: ...

    def get_dictation_auto_insert(self) -> bool: ...

    def set_dictation_auto_insert(self, value) -> None: ...

    def get_dictation_correct_before_insert(self) -> bool: ...

    def set_dictation_correct_before_insert(self, value) -> None: ...


def _members(protocol):
    names = set(getattr(protocol, "__annotations__", {}))
    names.update(
        name
        for name, value in vars(protocol).items()
        if callable(value) and not name.startswith("_")
    )
    return sorted(names)


def _signature_problem(expected, actual):
    """Return why ``actual`` cannot be called like ``expected``, if it cannot.

    Shared code passes required parameters by position, so only their order
    counts; optional ones may be passed by name, so their names must match.
    """
    try:
        actual_signature = inspect.signature(actual)
    except (TypeError, ValueError):
        return None  # Qt builtins expose no Python signature.
    expected_params = list(inspect.signature(expected).parameters.values())[1:]
    params = list(actual_signature.parameters.values())
    if params and params[0].name == "self":
        params = params[1:]
    positional = [
        param
        for param in params
        if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD)
    ]
    by_name = {param.name: param for param in params}
    any_position = any(param.kind is param.VAR_POSITIONAL for param in params)
    any_keyword = any(param.kind is param.VAR_KEYWORD for param in params)
    for index, param in enumerate(expected_params):
        if index >= len(positional) and not any_position:
            return f"n'accepte pas « {param.name} » en position {index + 1}"
        if param.default is param.empty:
            continue
        if index < len(positional) and positional[index].name != param.name:
            return (
                f"attend « {positional[index].name} » à la place de "
                f"« {param.name} »"
            )
        candidate = by_name.get(param.name)
        if candidate is None and not any_keyword:
            return f"n'accepte pas le paramètre « {param.name} »"
        if candidate is not None and candidate.default is candidate.empty:
            return f"rend obligatoire le paramètre optionnel « {param.name} »"
    for param in positional[len(expected_params):]:
        if param.default is param.empty:
            return f"exige le paramètre supplémentaire « {param.name} »"
    for param in params:
        if param.kind is param.KEYWORD_ONLY and param.default is param.empty:
            return f"exige le paramètre nommé « {param.name} »"
    return None


def contract_violations(settings, protocol=CoreSettings):
    """List the members of ``protocol`` that ``settings`` lacks or breaks."""
    violations = []
    annotations = getattr(protocol, "__annotations__", {})
    for name in _members(protocol):
        if not hasattr(settings, name):
            violations.append(f"{name} : absent")
            continue
        member = getattr(settings, name)
        if name in annotations:
            nested = annotations[name]
            if Protocol in getattr(nested, "__mro__", ()):
                violations.extend(
                    f"{name}.{problem}" for problem in contract_violations(member, nested)
                )
            continue
        if not callable(member):
            violations.append(f"{name} : n'est pas une méthode")
            continue
        problem = _signature_problem(getattr(protocol, name), member)
        if problem:
            violations.append(f"{name} : {problem}")
    return violations
