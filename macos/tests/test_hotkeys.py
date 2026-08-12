from src.utils.hotkey_manager import normalize_hotkey


def test_command_hotkey_is_normalized_for_pynput():
    normalized, error = normalize_hotkey("Cmd+Shift+Space")
    assert error == ""
    assert normalized == "<cmd>+<shift>+<space>"


def test_option_alias_and_function_key_are_supported():
    normalized, error = normalize_hotkey("Option+F12")
    assert error == ""
    assert normalized == "<alt>+<f12>"


def test_hotkey_requires_a_modifier():
    normalized, error = normalize_hotkey("K")
    assert normalized is None
    assert "modificateur" in error

