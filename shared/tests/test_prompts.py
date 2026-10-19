import pytest

from supermenu_core.config.prompts import (
    default_text_prompts,
    normalize_prompt_collection,
)


def _prompt(**overrides):
    value = {
        "name": "Corriger",
        "prompt": "Corrige ce texte",
        "status": "Correction en cours",
    }
    value.update(overrides)
    return value


def test_text_prompt_schema_adds_cross_platform_defaults():
    normalized = normalize_prompt_collection({"corriger": _prompt()})

    assert normalized["corriger"]["hotkey"] == ""
    assert normalized["corriger"]["insert_directly"] is False
    assert normalized["corriger"]["position"] == 999


def test_default_catalog_returns_independent_copies():
    first = default_text_prompts()
    second = default_text_prompts()

    first["corriger"]["name"] = "Modifié"

    assert second["corriger"]["name"] == "Corriger"
    assert all("hotkey" in prompt for prompt in second.values())


def test_duplicate_hotkeys_are_removed_from_persisted_settings():
    normalized = normalize_prompt_collection(
        {
            "one": _prompt(hotkey="Ctrl+Alt+1"),
            "two": _prompt(hotkey="ctrl+alt+1"),
        }
    )

    assert normalized["one"]["hotkey"] == "Ctrl+Alt+1"
    assert normalized["two"]["hotkey"] == ""


def test_duplicate_hotkeys_make_an_import_fail_atomically():
    with pytest.raises(ValueError, match="plusieurs prompts"):
        normalize_prompt_collection(
            {
                "one": _prompt(hotkey="Ctrl+Alt+1"),
                "two": _prompt(hotkey="ctrl+alt+1"),
            },
            require_non_empty=True,
        )
