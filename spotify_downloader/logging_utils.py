"""Logging configuration utilities."""
from __future__ import annotations

import logging
from logging import Logger


def configure_logging() -> Logger:
    """Configure application wide logging."""

    logger = logging.getLogger("spotify_downloader")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
