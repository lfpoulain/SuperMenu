"""Rotating application log stored in the standard macOS Logs folder."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from src.utils.paths import user_log_dir


LOG_DIR = user_log_dir()
LOG_FILE = LOG_DIR / "supermenu.log"

logger = logging.getLogger("SuperMenu.macOS")
logger.setLevel(logging.INFO)

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
