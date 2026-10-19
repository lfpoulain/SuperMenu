"""Feature switches in the macOS settings file: new installs and updates."""

from PySide6.QtCore import QSettings

from src.config.settings import Settings
from supermenu_core.config import feature_modes
from supermenu_core.config.feature_modes import (
    ADVANCED_FEATURES_SETTING,
    EXPERIMENTAL_FEATURES_SETTING,
)

KEYS = (ADVANCED_FEATURES_SETTING, EXPERIMENTAL_FEATURES_SETTING)


def _stored(path):
    store = QSettings(str(path), QSettings.Format.IniFormat)
    return {key: store.value(key, type=bool) if store.contains(key) else None for key in KEYS}


def test_new_installation_starts_with_both_switches_off(tmp_path, monkeypatch):
    # Never the per-process test configuration, which earlier tests filled.
    monkeypatch.setattr(feature_modes, "NEW_INSTALL_ENABLED", False)
    path = tmp_path / "settings.ini"
    settings = Settings(config_path=str(path))
    assert not settings.get_advanced_features_enabled()
    assert not settings.get_experimental_features_enabled()
    assert _stored(path) == {key: False for key in KEYS}


def test_update_from_an_earlier_version_keeps_every_feature(tmp_path, monkeypatch):
    monkeypatch.setattr(feature_modes, "NEW_INSTALL_ENABLED", False)
    path = tmp_path / "settings.ini"
    earlier = QSettings(str(path), QSettings.Format.IniFormat)
    earlier.setValue("hotkey", "Cmd+Shift+K")
    earlier.setValue("theme", "light")
    earlier.sync()
    settings = Settings(config_path=str(path))
    assert settings.get_advanced_features_enabled()
    assert settings.get_experimental_features_enabled()
    assert _stored(path) == {key: True for key in KEYS}
    assert settings.get_hotkey() == "Cmd+Shift+K"


def test_reset_to_defaults_keeps_the_switches(tmp_path, monkeypatch):
    monkeypatch.setattr(feature_modes, "NEW_INSTALL_ENABLED", False)
    path = tmp_path / "settings.ini"
    settings = Settings(config_path=str(path))
    settings.set_experimental_features_enabled(True)
    settings.set_hotkey("Cmd+Shift+K")
    settings.sync()
    settings.reset_to_defaults()
    assert settings.get_hotkey() == "Cmd+Shift+Space"
    assert not settings.get_advanced_features_enabled()
    assert settings.get_experimental_features_enabled()
    assert _stored(path) == {ADVANCED_FEATURES_SETTING: False, EXPERIMENTAL_FEATURES_SETTING: True}
    assert Settings(config_path=str(path)).get_experimental_features_enabled()
