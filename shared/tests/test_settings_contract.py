import ast
from pathlib import Path

import supermenu_core
from supermenu_core.config.settings_contract import (
    CoreSettings,
    SettingsStore,
    contract_violations,
)

CORE_ROOT = Path(supermenu_core.__file__).resolve().parent
# Optional platform features, probed with hasattr() before use.
OPTIONAL_MEMBERS = {"get_foundry_model"}


def _contract_members(protocol):
    members = set(protocol.__annotations__) if hasattr(protocol, "__annotations__") else set()
    members.update(name for name in vars(protocol) if not name.startswith("_"))
    return members


def test_contract_lists_every_settings_member_used_by_the_core():
    allowed = (
        _contract_members(CoreSettings)
        | _contract_members(SettingsStore)
        | OPTIONAL_MEMBERS
    )
    used = {}
    for path in CORE_ROOT.rglob("*.py"):
        if path.name == "settings_contract.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            owner = name = None
            if isinstance(node, ast.Attribute):
                owner, name = node.value, node.attr
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"getattr", "hasattr"}
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
            ):
                owner, name = node.args[0], node.args[1].value
            owner_name = getattr(owner, "id", None) or getattr(owner, "attr", None)
            if owner_name in {"settings", "_settings"}:
                used.setdefault(name, path.relative_to(CORE_ROOT).as_posix())

    assert {name: where for name, where in used.items() if name not in allowed} == {}


class _Store:
    def value(self, key, defaultValue=None, type=None):
        return defaultValue

    def setValue(self, key, value):
        pass

    def contains(self, key):
        return False

    def remove(self, key):
        pass

    def sync(self):
        pass


def _complete_settings():
    settings = type("FakeSettings", (), {})()
    for name in _contract_members(CoreSettings):
        if name in CoreSettings.__annotations__:
            continue
        setattr(settings, name, getattr(CoreSettings, name).__get__(settings))
    settings.settings = _Store()
    settings.default_prompts = {}
    settings.default_voice_prompts = {}
    return settings


def test_a_complete_implementation_has_no_violation():
    assert contract_violations(_complete_settings()) == []


def test_missing_members_and_broken_signatures_are_reported():
    settings = _complete_settings()
    del settings.get_prompts
    settings.get_model_device_names = lambda: {}
    settings.set_update_channel = lambda channel, reason: None
    settings.update_prompt = (
        lambda prompt_id, name, prompt, status, insert_directly, position=None,
        hotkey="", reasoning_mode=None, model_target=None: None
    )
    settings.add_voice_prompt = lambda *args, **kwargs: "id"
    del settings.default_voice_prompts
    settings.settings = object()

    violations = contract_violations(settings)

    assert "get_prompts : absent" in violations
    assert "default_voice_prompts : absent" in violations
    assert any(item.startswith("get_model_device_names : n'accepte pas") for item in violations)
    assert any(item.startswith("set_update_channel : exige") for item in violations)
    assert any(item.startswith("update_prompt : rend obligatoire") for item in violations)
    assert "settings.setValue : absent" in violations
    assert not any(item.startswith("add_voice_prompt") for item in violations)
