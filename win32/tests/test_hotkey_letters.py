from types import SimpleNamespace

import pytest
from src.utils import hotkey_manager as hotkeys


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Ctrl+Alt+C", 3),
        ("Ctrl+Alt+c", 3),
        ("Ctrl+Alt+Shift+C", 7),
        ("Ctrl+Alt+1", 7),
        ("Ctrl+Alt+é", 3),
    ],
)
def test_letter_case_is_not_a_modifier_and_layout_symbols_keep_their_modifiers(
    monkeypatch, label, expected
):
    mapping = {"c": 0x43, "C": 0x143, "1": 0x131, "é": 0x32}
    monkeypatch.setattr(
        hotkeys, "_USER32", SimpleNamespace(VkKeyScanW=mapping.__getitem__)
    )
    mods, vk, error = hotkeys._parse_hotkey_to_win32(label)
    assert not error and mods == expected
    assert vk in {0x43, 0x31, 0x32}
