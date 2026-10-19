from src.config.settings import Settings
from supermenu_core.config.settings_contract import CoreSettings, contract_violations


def test_macos_settings_fulfil_the_shared_core_contract(tmp_path):
    settings = Settings(str(tmp_path / "settings.ini"))

    assert contract_violations(settings) == []
    assert isinstance(settings, CoreSettings)
