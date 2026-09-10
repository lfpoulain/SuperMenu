import os
import sys
from unittest.mock import Mock

import pytest

from src.ui import main_window


@pytest.mark.parametrize("frozen", [False, True])
def test_restart_owns_its_runtime_before_quitting(monkeypatch, frozen):
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(sys, "argv", ["run.py"])
    monkeypatch.delenv("PYINSTALLER_RESET_ENVIRONMENT", raising=False)
    monkeypatch.setenv("_PYI_APPLICATION_HOME_DIR", "old-extraction")
    events = []
    launch = Mock(side_effect=lambda *a, **kw: events.append("launch"))
    monkeypatch.setattr(main_window.subprocess, "Popen", launch)
    monkeypatch.setattr(main_window, "QApplication", Mock(quit=lambda: events.append("quit")))
    main_window.MainWindow.restart_application(None)
    assert events == ["launch", "quit"]
    if frozen:
        assert launch.call_args.args[0] == [sys.executable]
        assert launch.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
        assert "PYINSTALLER_RESET_ENVIRONMENT" not in os.environ
    else:
        assert launch.call_args.args[0] == [sys.executable, os.path.abspath("run.py")]


def test_failed_restart_keeps_current_app_open(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(main_window.subprocess, "Popen", Mock(side_effect=OSError("launch")))
    app = Mock()
    monkeypatch.setattr(main_window, "QApplication", app)
    with pytest.raises(OSError):
        main_window.MainWindow.restart_application(None)
    app.quit.assert_not_called()
