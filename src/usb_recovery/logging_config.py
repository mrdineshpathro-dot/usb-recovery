"""Structured logging with rotating files. File contents are never logged."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from usb_recovery.constants import APP_ID

_CONFIGURED = False


def default_log_dir() -> Path:
    override = os.environ.get("USB_RECOVERY_LOG_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / APP_ID
    home = Path.home() / ".local" / "state" / APP_ID
    return home


def setup_logging(
    *,
    level: str = "INFO",
    log_dir: Path | None = None,
    rotate_bytes: int = 1_048_576,
    rotate_backups: int = 5,
    console: bool = True,
) -> Path:
    """Configure the `usb_recovery` logger once. Returns the log file path."""
    global _CONFIGURED
    log_path_dir = log_dir or default_log_dir()
    log_path_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_path_dir / "usb-recovery.log"

    if _CONFIGURED:
        return log_file

    logger = logging.getLogger("usb_recovery")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=rotate_bytes,
        backupCount=rotate_backups,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        logger.addHandler(stream)

    _CONFIGURED = True
    logger.info("logging initialized file=%s level=%s", log_file, level)
    return log_file


def get_logger(name: str) -> logging.Logger:
    if not name.startswith("usb_recovery"):
        name = f"usb_recovery.{name}"
    return logging.getLogger(name)
