from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from src import main
from src.config import settings as settings_module
from src.config.settings import Settings
from src.utils import hotkey_manager as hotkeys

_VK_OEM_3 = 0xC0  # touche sous Échap en QWERTY US
_VK_OEM_5 = 0xDC  # touche sous Échap en QWERTZ allemand
_VK_OEM_7 = 0xDE  # touche "²" en AZERTY


_CHARACTERS = {_VK_OEM_3: ord("`"), _VK_OEM_5: 0x80000000 | ord("^")}  # ^ : touche morte


def _keyboard(monkeypatch, square, below_escape):
    calls = []

    def map_virtual_key(code, map_type):
        calls.append((code, map_type))
        if map_type == hotkeys._MAPVK_VK_TO_CHAR:
            return _CHARACTERS.get(code, 0)
        return below_escape

    mapping = {"²": square, "c": 0x43}
    monkeypatch.setattr(
        hotkeys,
        "_USER32",
        SimpleNamespace(VkKeyScanW=mapping.__getitem__, MapVirtualKeyW=map_virtual_key),
    )
    return calls


def test_azerty_square_key_is_unchanged(monkeypatch):
    calls = _keyboard(monkeypatch, square=_VK_OEM_7, below_escape=_VK_OEM_3)
    assert hotkeys._parse_hotkey_to_win32("Ctrl+²") == (2, _VK_OEM_7, "")
    assert hotkeys._parse_hotkey_to_win32("Ctrl+Alt+²") == (3, _VK_OEM_7, "")
    assert calls == []


def test_default_hotkey_uses_the_key_below_escape_on_qwerty(monkeypatch):
    _keyboard(monkeypatch, square=-1, below_escape=_VK_OEM_3)
    assert hotkeys._parse_hotkey_to_win32("Ctrl+²") == (2, _VK_OEM_3, "")
    assert hotkeys._parse_hotkey_to_win32("Ctrl+Alt+²") == (3, _VK_OEM_3, "")


def test_square_typed_with_altgr_does_not_turn_ctrl_into_ctrl_alt(monkeypatch):
    # QWERTZ allemand : "²" = AltGr+2, soit Ctrl+Alt+2 pour Windows.
    _keyboard(monkeypatch, square=0x0632, below_escape=_VK_OEM_5)
    assert hotkeys._parse_hotkey_to_win32("Ctrl+²") == (2, _VK_OEM_5, "")
    # Un Ctrl+Alt+² enregistré sur ce clavier garde la combinaison tapée.
    assert hotkeys._parse_hotkey_to_win32("Ctrl+Alt+²") == (3, 0x32, "")


@pytest.mark.parametrize(
    "square,below_escape,expected",
    [
        (-1, _VK_OEM_3, "touche '²' absente de ce clavier, touche sous Échap utilisée à la place (Ctrl+`)"),
        (0x0632, _VK_OEM_5, "touche '²' accessible seulement avec AltGr, touche sous Échap utilisée à la place (Ctrl+^)"),
        (-1, 0xDF, "touche sous Échap utilisée à la place (Ctrl+VK 0xDF)"),
    ],
)
def test_fallback_key_is_named_in_a_warning(monkeypatch, square, below_escape, expected):
    # Le libellé reste "Ctrl+²" : le journal doit dire quelle touche est réservée.
    _keyboard(monkeypatch, square=square, below_escape=below_escape)
    logged = []
    monkeypatch.setattr(hotkeys, "log", lambda message, level=None: logged.append((level, message)))

    assert hotkeys._parse_hotkey_to_win32("Ctrl+²") == (2, below_escape, "")
    assert logged == [(hotkeys.logging.WARNING, logged[0][1])]
    assert logged[0][1].startswith("Raccourci 'Ctrl+²' : ")
    assert logged[0][1].endswith(expected)


def test_square_without_a_usable_physical_key_is_still_reported(monkeypatch):
    _keyboard(monkeypatch, square=-1, below_escape=0xF3)  # Hankaku/Zenkaku
    assert hotkeys._parse_hotkey_to_win32("Ctrl+²") == (
        None,
        None,
        "Touche non supportée: ²",
    )


@pytest.fixture
def settings(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(settings_module.os.path, "expanduser", lambda _: str(tmp_path))
    return Settings()


def test_startup_registration_failure_is_exposed(settings, monkeypatch):
    errors = []
    monkeypatch.setattr(
        hotkeys._REGISTRY,
        "register",
        lambda mods, key, callback: (None, "Ce raccourci est déjà utilisé (win32 error 1409)"),
    )
    monkeypatch.setattr(hotkeys._REGISTRY, "unregister", lambda key: None)
    monkeypatch.setattr(hotkeys, "_parse_hotkey_to_win32", lambda key: (2, 0x43, ""))

    manager = hotkeys.HotkeyManager(settings)
    manager.registration_failed.connect(errors.append)
    try:
        assert not manager.registered
        assert manager.last_error.endswith("1409)")
        assert manager.feature_name == "Menu principal"
        assert not manager.register_hotkey()
        assert errors == [manager.last_error]
    finally:
        manager.close()


def test_startup_notification_lists_inactive_hotkeys():
    active = SimpleNamespace(registered=True, last_error="", feature_name="Menu vocal", hotkey="Ctrl+Alt+V")
    empty_dictation = SimpleNamespace(registered=False, last_error="", feature_name="Dictée", hotkey="")
    broken = SimpleNamespace(
        registered=False,
        last_error="Touche non supportée: ²",
        feature_name="Menu principal",
        hotkey="Ctrl+²",
    )

    failures = main._inactive_hotkeys((active, empty_dictation, broken, None))
    assert failures == [("Menu principal", "Ctrl+²", "Touche non supportée: ²")]
    assert main._hotkey_failure_message([]) is None

    title, text = main._hotkey_failure_message(failures)
    assert title == "Raccourci inactif"
    assert text.splitlines()[0] == "Menu principal (Ctrl+²) : Touche non supportée: ²"
    assert "Réglages > Raccourcis" in text

    title, text = main._hotkey_failure_message(failures * 2, prompt_error_count=2)
    assert title == "Raccourcis inactifs"
    assert "2 raccourcis de prompt" in text


def test_report_hotkey_failures_uses_the_tray_balloon(monkeypatch):
    shown = []
    tray = SimpleNamespace(isVisible=lambda: True, showMessage=lambda *args: shown.append(args))
    broken = SimpleNamespace(
        registered=False, last_error="win32 error 1409", feature_name="Menu principal", hotkey="Ctrl+²"
    )
    app = main.SuperMenu.__new__(main.SuperMenu)
    app.hotkey_manager = broken
    app.custom_hotkey_manager = app.voice_hotkey_manager = None
    app.screenshot_hotkey_manager = app.dictation_hotkey_manager = None
    app.prompt_hotkey_manager = SimpleNamespace(errors={})
    app.main_window = SimpleNamespace(tray_icon=tray)

    app._report_hotkey_failures()

    assert len(shown) == 1
    title, text, _icon, _duration = shown[0]
    assert title == "SuperMenu — Raccourci inactif"
    assert text.startswith("Menu principal (Ctrl+²) : win32 error 1409")
