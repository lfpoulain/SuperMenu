import os
import stat
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from supermenu_core.config.prompts import default_text_prompts
from src.config.build_info import APP_VERSION
from src.config.settings import Settings
from src.utils.paths import packaged_resource_status


def test_version_is_read_from_macos_subproject():
    expected = (
        Path(__file__).resolve().parents[1] / "VERSION"
    ).read_text(encoding="utf-8").strip()
    assert APP_VERSION == expected


def test_settings_use_macos_defaults(tmp_path, monkeypatch):
    QCoreApplication.setOrganizationName("SuperMenuTests")
    QCoreApplication.setApplicationName("SuperMenuTests")
    monkeypatch.setenv("SUPERMENU_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("SUPERMENU_LOG_DIR", str(tmp_path / "logs"))
    settings = Settings()

    assert settings.get_hotkey() == "Cmd+Shift+Space"
    assert settings.get_custom_hotkey() == "Cmd+Shift+M"
    assert settings.get_prompts() == default_text_prompts()
    assert "audio" not in settings.settings.allKeys()
    assert "screenshot" not in settings.settings.allKeys()


def test_api_key_is_stored_in_the_private_macos_config(tmp_path):
    config_path = tmp_path / "settings.ini"
    settings = Settings(config_path=str(config_path))

    settings.set_api_key("sk-local-test")
    settings.sync()

    reloaded = Settings(config_path=str(config_path))
    assert reloaded.get_api_key() == "sk-local-test"
    assert "sk-local-test" in config_path.read_text(encoding="utf-8")


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Les permissions POSIX 0600 ne s’appliquent pas sous Windows.",
)
def test_private_config_stays_readable_by_its_owner_only(tmp_path):
    config_path = tmp_path / "settings.ini"

    def mode(path):
        return stat.S_IMODE(os.stat(path).st_mode)

    settings = Settings(config_path=str(config_path))
    assert mode(config_path) == 0o600

    settings.set_api_key("sk-local-test")
    settings.sync()
    assert mode(config_path) == 0o600

    # A write made by QSettings alone (atomic replacement) keeps the mode.
    settings.set_custom_endpoint_api_key("endpoint-secret")
    settings.settings.sync()
    assert mode(config_path) == 0o600
    leftovers = [
        path
        for path in tmp_path.iterdir()
        if path.is_file()
        and path.name.startswith(config_path.name)
        and path != config_path
        and not path.name.endswith(".lock")
    ]
    assert all(mode(path) == 0o600 for path in leftovers)


def test_custom_reasoning_accepts_provider_native_options(tmp_path):
    settings = Settings(config_path=str(tmp_path / "settings.ini"))

    for option in ("on", "off", "future_tier"):
        settings.set_custom_reasoning_effort(option)
        assert settings.get_custom_reasoning_effort() == option


def test_custom_endpoint_key_is_separate_from_openai_key(tmp_path):
    settings = Settings(config_path=str(tmp_path / "settings.ini"))

    settings.set_api_key("openai-secret")
    settings.set_custom_endpoint_api_key("endpoint-secret")

    assert settings.get_api_key() == "openai-secret"
    assert settings.get_custom_endpoint_api_key() == "endpoint-secret"


def test_packaged_resource_smoke_status():
    status = packaged_resource_status()
    assert status["ok"] is True
    assert Path(status["icon"]).is_file()
