from src.config import settings as settings_module
from src.config.settings import Settings
from supermenu_core.config.settings_contract import CoreSettings, contract_violations


def test_windows_settings_fulfil_the_shared_core_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module.os.path, "expanduser", lambda _path: str(tmp_path))
    settings = Settings()

    assert contract_violations(settings) == []
    assert isinstance(settings, CoreSettings)
