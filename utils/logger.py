"""Logging utilities for CineGen AI."""

import logging
import os
from sys import stdout

DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging() -> None:
    """Configure application logging once."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    root_logger = logging.getLogger()

    if root_logger.handlers:
        root_logger.setLevel(log_level)
        return

    handler = logging.StreamHandler(stdout)
    handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))

    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with the shared application configuration."""
    setup_logging()
    return logging.getLogger(name)
