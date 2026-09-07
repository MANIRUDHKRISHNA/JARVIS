"""Central logging configuration for JARVIS."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock


BASE_DIR = Path(__file__).resolve().parents[2]

LOG_DIR = BASE_DIR / "data" / "logs"
LOG_FILE = LOG_DIR / "jarvis.log"

_LOGGER_NAME = "jarvis"

_config_lock = Lock()
_configured = False


def _configure_logger() -> logging.Logger:
    """Configure the central JARVIS logger."""
    global _configured

    logger = logging.getLogger(_LOGGER_NAME)

    with _config_lock:
        if _configured:
            return logger

        LOG_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.setLevel(logging.INFO)
        logger.propagate = False

        formatter = logging.Formatter(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(threadName)s | "
            "%(name)s | "
            "%(message)s"
        )

        if not logger.handlers:
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )

            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)

            console_handler = logging.StreamHandler()

            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)

            logger.addHandler(file_handler)
            logger.addHandler(console_handler)

        _configured = True

    return logger


def get_logger(
    name: str | None = None,
) -> logging.Logger:
    """Return a configured JARVIS logger."""
    root_logger = _configure_logger()

    if not name:
        return root_logger

    return root_logger.getChild(name)


def configure_logging() -> logging.Logger:
    """Explicitly configure logging."""
    return _configure_logger()


# Backward compatibility for existing Stage 15 tools.
logger = get_logger()


__all__ = [
    "LOG_DIR",
    "LOG_FILE",
    "logger",
    "configure_logging",
    "get_logger",
]
