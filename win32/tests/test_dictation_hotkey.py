from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from src.config import settings as settings_module
from src.config.settings import Settings
from src.utils import hotkey_manager


def test_native_hold_releases_once_when_a_shortcut_key_is_released(
    tmp_path, monkeypatch
):
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(settings_module.os.path, "expanduser", lambda _: str(tmp_path))
    settings = Settings()
    settings.set_dictation_hotkey("Ctrl+Alt+D")
    settings.set_dictation_hotkey_mode("hold")
    down, calls = {0x11, 0x12, 0x44}, []
    monkeypatch.setattr(
        hotkey_manager,
        "_USER32",
        SimpleNamespace(GetAsyncKeyState=lambda key: 0x8000 if key in down else 0),
    )
    monkeypatch.setattr(
        hotkey_manager, "_parse_hotkey_to_win32", lambda key: (3, 0x44, "")
    )
    monkeypatch.setattr(
        hotkey_manager._REGISTRY, "register", lambda mods, key, callback: (123, "")
    )
    monkeypatch.setattr(hotkey_manager._REGISTRY, "unregister", lambda key: None)
    manager = hotkey_manager.HotkeyManager(settings, dictation_hotkey=True)
    manager.dictation_shortcut.started.connect(lambda: calls.append("start"))
    manager.dictation_shortcut.released.connect(lambda: calls.append("stop"))
    manager._on_hotkey_triggered()
    manager._on_hotkey_triggered()
    manager._check_dictation_release()
    assert calls == ["start"] and manager._release_timer.isActive()
    down.remove(0x44)
    manager._check_dictation_release()
    manager._check_dictation_release()
    assert calls == ["start", "stop"] and not manager._release_timer.isActive()
    assert manager.set_hotkey("")
    assert settings.get_dictation_hotkey() == "" and not manager.registered
    manager.close()
