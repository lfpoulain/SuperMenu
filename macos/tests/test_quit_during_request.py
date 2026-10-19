"""Quitting while a background request runs must not abort the process."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


MACOS_ROOT = Path(__file__).resolve().parents[1]

_SCRIPT = textwrap.dedent(
    """
    import sys
    import threading

    sys.path.insert(0, sys.argv[1])
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    from src.ui import main_window

    release = threading.Event()
    started = threading.Event()

    def blocking_request(*_args, **_kwargs):
        started.set()
        release.wait(30)
        return {}

    if sys.argv[2] == "update":
        main_window.app_updater.check_latest_release = blocking_request
        worker = main_window.UpdateCheckWorker("stable")
    else:
        from src.api.openai_client import OpenAIClient

        OpenAIClient.fetch_available_model_details = staticmethod(
            lambda *args, **kwargs: (blocking_request(), (True, []))[1]
        )
        worker = main_window.CustomModelsWorker(
            "http://localhost:11434", None, "ollama"
        )
    worker.start()
    assert started.wait(10)
    assert worker.isRunning()
    QTimer.singleShot(0, app.quit)
    app.exec()
    # The window owning the worker is torn down while the request still runs,
    # exactly as when the user quits during the startup update check.
    del worker
    print("clean-exit")
    """
)


@pytest.mark.parametrize("kind", ["update", "models"])
def test_quitting_during_a_background_request_exits_cleanly(tmp_path, kind):
    script = tmp_path / "quit_during_request.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SUPERMENU_CONFIG_DIR"] = str(tmp_path / "config")
    env["SUPERMENU_LOG_DIR"] = str(tmp_path / "logs")

    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(script), str(MACOS_ROOT), kind],
        cwd=str(MACOS_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    assert "Destroyed while thread" not in result.stderr
    assert result.returncode == 0, result.stderr
    assert "clean-exit" in result.stdout
