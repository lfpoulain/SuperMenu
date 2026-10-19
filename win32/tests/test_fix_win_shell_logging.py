import logging
import sys
import threading
from types import SimpleNamespace

import pytest

import run
from src import main
from src.utils import logger as logger_module


class _Records(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def records():
    handler = _Records()
    logger_module.logger.addHandler(handler)
    yield handler.records
    logger_module.logger.removeHandler(handler)


def test_unhandled_exceptions_reach_the_log_file(records, monkeypatch):
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    monkeypatch.setattr(logger_module, "_crash_reporting_installed", False)
    logger_module.install_crash_reporting()

    try:
        raise ValueError("slot Qt")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    def fail():
        raise RuntimeError("thread")

    worker = threading.Thread(target=fail, name="worker-test")
    worker.start()
    worker.join()

    critical = [r for r in records if r.levelno == logging.CRITICAL]
    assert [r.exc_info[0] for r in critical] == [ValueError, RuntimeError]
    assert "worker-test" in critical[1].getMessage()


def test_hotkey_handler_errors_are_logged_with_traceback(records):
    def broken():
        raise RuntimeError("menu")

    app = main.SuperMenu.__new__(main.SuperMenu)
    app.context_menu_manager = SimpleNamespace(
        show_menu=broken, show_voice_menu=broken, show_custom_mode=broken,
        run_prompt_hotkey=lambda prompt_id: broken(),
    )
    app.show_context_menu()
    app.show_voice_menu()
    app.show_custom_mode()
    app.run_prompt_hotkey("p1")

    errors = [r for r in records if r.levelno == logging.ERROR]
    assert len(errors) == 4
    assert all(r.exc_info and r.exc_info[0] is RuntimeError for r in errors)


@pytest.mark.parametrize("argv,expected_boxes", [(["SuperMenu.exe"], 1), (["SuperMenu.exe", "--smoke-test"], 0)])
def test_fatal_startup_error_is_logged_and_shown_only_in_the_gui(
    records, monkeypatch, argv, expected_boxes
):
    boxes = []
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", argv)
    import ctypes

    monkeypatch.setattr(
        ctypes, "windll",
        SimpleNamespace(user32=SimpleNamespace(MessageBoxW=lambda *args: boxes.append(args))),
    )
    try:
        raise OSError("DLL Qt manquante")
    except OSError:
        run.report_startup_failure("Erreur lors du lancement de l'application: DLL Qt manquante")

    assert records[-1].levelno == logging.CRITICAL
    assert records[-1].exc_info[0] is OSError
    assert len(boxes) == expected_boxes
    if boxes:
        assert "DLL Qt manquante" in boxes[0][1]
