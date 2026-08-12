import os
import tempfile
from pathlib import Path


TEST_STATE = Path(tempfile.gettempdir()) / f"supermenu-macos-tests-{os.getpid()}"
os.environ.setdefault("SUPERMENU_CONFIG_DIR", str(TEST_STATE / "config"))
os.environ.setdefault("SUPERMENU_LOG_DIR", str(TEST_STATE / "logs"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
