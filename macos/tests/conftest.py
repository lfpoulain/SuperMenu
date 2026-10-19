import os
import tempfile
from pathlib import Path

import pytest


TEST_STATE = Path(tempfile.gettempdir()) / f"supermenu-macos-tests-{os.getpid()}"
os.environ.setdefault("SUPERMENU_CONFIG_DIR", str(TEST_STATE / "config"))
os.environ.setdefault("SUPERMENU_LOG_DIR", str(TEST_STATE / "logs"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Imported after the environment above (this module does not load Qt).
from supermenu_core.config import feature_modes  # noqa: E402


@pytest.fixture(autouse=True)
def _feature_modes_of_updated_installs(monkeypatch):
    """Earlier tests build fresh settings files and exercise every feature.

    An update keeps both feature switches on, so these tests run as an updated
    installation. Tests of a new installation set NEW_INSTALL_ENABLED to False
    and use their own settings file, never the shared test configuration.
    """
    monkeypatch.setattr(feature_modes, "NEW_INSTALL_ENABLED", True)
