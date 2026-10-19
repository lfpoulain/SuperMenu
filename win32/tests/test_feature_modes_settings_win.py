"""Feature switches in the Windows settings file: new installs and updates."""

from PySide6.QtCore import QSettings

from src.config import settings as settings_module
from src.config.settings import Settings
from supermenu_core.config import feature_modes
from supermenu_core.config.feature_modes import (
    ADVANCED_FEATURES_SETTING,
    EXPERIMENTAL_FEATURES_SETTING,
)

KEYS = (ADVANCED_FEATURES_SETTING, EXPERIMENTAL_FEATURES_SETTING)


def _home(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module.os.path, "expanduser", lambda _path: str(tmp_path))
    return tmp_path / "SuperMenu.ini"


def _stored(path):
    store = QSettings(str(path), QSettings.Format.IniFormat)
    return {key: store.value(key, type=bool) if store.contains(key) else None for key in KEYS}


def test_new_installation_starts_with_both_switches_off(tmp_path, monkeypatch):
    monkeypatch.setattr(feature_modes, "NEW_INSTALL_ENABLED", False)
    path = _home(tmp_path, monkeypatch)
    settings = Settings()
    assert not settings.get_advanced_features_enabled()
    assert not settings.get_experimental_features_enabled()
    assert _stored(path) == {key: False for key in KEYS}
    # The defaults are still written: only the switches decide what is shown.
    assert settings.get_voice_hotkey() == "Ctrl+Alt+²"


def test_update_from_an_earlier_version_keeps_every_feature(tmp_path, monkeypatch):
    monkeypatch.setattr(feature_modes, "NEW_INSTALL_ENABLED", False)
    path = _home(tmp_path, monkeypatch)
    earlier = QSettings(str(path), QSettings.Format.IniFormat)
    earlier.setValue("hotkey", "Ctrl+Alt+H")
    earlier.setValue("prompts", "{}")
    earlier.sync()
    settings = Settings()
    assert settings.get_advanced_features_enabled()
    assert settings.get_experimental_features_enabled()
    assert _stored(path) == {key: True for key in KEYS}
    assert settings.get_hotkey() == "Ctrl+Alt+H"


def test_reset_to_defaults_keeps_the_switches(tmp_path, monkeypatch):
    monkeypatch.setattr(feature_modes, "NEW_INSTALL_ENABLED", False)
    path = _home(tmp_path, monkeypatch)
    settings = Settings()
    settings.set_advanced_features_enabled(True)
    settings.sync()
    settings.reset_to_defaults()
    assert settings.get_advanced_features_enabled()
    assert not settings.get_experimental_features_enabled()
    assert _stored(path) == {ADVANCED_FEATURES_SETTING: True, EXPERIMENTAL_FEATURES_SETTING: False}
    # A later launch reads the same choice, not a new installation.
    assert Settings().get_advanced_features_enabled()
