"""Uninstalling with user data removal also deletes the stored API keys."""

import re
from pathlib import Path

from src.utils import paths


def _installer_script():
    return Path(paths.resource_path("setup_supermenu.iss")).read_text(
        encoding="utf-8"
    )


def test_purging_user_data_also_deletes_the_stored_api_keys():
    script = _installer_script()

    # keyring stores generic credentials: the latest under "SuperMenu", the
    # previous ones under "<username>@SuperMenu" (see src/config/settings.py).
    assert "external 'CredDeleteW@advapi32.dll stdcall'" in script
    assert "CRED_TYPE_GENERIC = 1;" in script
    for target in (
        "'SuperMenu'",
        "'openai_api_key@SuperMenu'",
        "'custom_endpoint_api_key@SuperMenu'",
    ):
        assert f"CredDelete({target}, CRED_TYPE_GENERIC, 0);" in script

    purge = re.search(
        r"if PurgeUserData then\s+begin(.*?)\n    end;", script, re.S
    ).group(1)
    assert "DeleteStoredApiKeys();" in purge


def test_uninstall_question_mentions_the_api_keys():
    assert "clés API enregistrées" in _installer_script()


def test_keyring_targets_match_the_settings_service_and_usernames():
    settings = Path(paths.resource_path("src", "config", "settings.py")).read_text(
        encoding="utf-8"
    )
    script = _installer_script()

    usernames = set(
        re.findall(r'keyring\.set_password\(\s*"SuperMenu",\s*"(\w+)"', settings)
    )
    assert usernames == {"openai_api_key", "custom_endpoint_api_key"}
    for username in usernames:
        assert f"'{username}@SuperMenu'" in script
