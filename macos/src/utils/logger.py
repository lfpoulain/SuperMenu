"""Rotating application log stored in the standard macOS Logs folder."""

from __future__ import annotations

import logging
import faulthandler
import sys
import threading
from logging.handlers import RotatingFileHandler

from src.utils.paths import user_log_dir


LOG_DIR = user_log_dir()
LOG_FILE = LOG_DIR / "supermenu.log"
CRASH_FILE = LOG_DIR / "native-crash.log"

logger = logging.getLogger("SuperMenu.macOS")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def log(message: str, level: int = logging.INFO) -> None:
    logger.log(level, message)
    for handler in logger.handlers:
        handler.flush()


_crash_reporting_installed = False
_crash_file_handle = None


def install_crash_reporting() -> None:
    """Persist Python and native crash context for packaged GUI builds."""
    global _crash_reporting_installed, _crash_file_handle
    if _crash_reporting_installed:
        return
    _crash_reporting_installed = True
    try:
        _crash_file_handle = CRASH_FILE.open("a", encoding="utf-8")
        faulthandler.enable(file=_crash_file_handle, all_threads=True)
    except (OSError, RuntimeError) as exc:
        logger.warning("Journal natif indisponible : %s", exc)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Exception non gérée dans le thread principal",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def handle_thread_exception(args):
        logger.critical(
            "Exception non gérée dans le thread %s",
            getattr(args.thread, "name", "inconnu"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = handle_exception
    threading.excepthook = handle_thread_exception
