from pathlib import Path

from PySide6.QtCore import QCoreApplication

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
    assert settings.get_prompts()
    assert "audio" not in settings.settings.allKeys()
    assert "screenshot" not in settings.settings.allKeys()


def test_packaged_resource_smoke_status():
    status = packaged_resource_status()
    assert status["ok"] is True
    assert Path(status["icon"]).is_file()

