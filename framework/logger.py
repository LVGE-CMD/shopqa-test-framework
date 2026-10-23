from __future__ import annotations

import logging
import os
from pathlib import Path

from framework.config import REPORTS_DIR

_LOGGER_NAME = "shopqa"
_CONFIGURED = False


def setup_logging() -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger(_LOGGER_NAME)
    if _CONFIGURED:
        return logger

    level = os.getenv("SHOPLITE_LOG_LEVEL", "INFO").upper()
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    log_dir = REPORTS_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        Path(log_dir) / "test.log", mode="w", encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _CONFIGURED = True
    return logger


def get_logger(name: str = "shopqa") -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
