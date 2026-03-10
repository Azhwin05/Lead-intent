"""
utils/logging_setup.py
───────────────────────
Configures Python's standard logging with:
  • Rich console handler   — colourised, human-readable
  • Rotating file handler  — structured, machine-readable, auto-rotates at 10 MB
  • Consistent format across all modules

Usage:
    from utils.logging_setup import get_logger
    logger = get_logger(__name__)
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

_LOGS_DIR = Path("logs")
_LOGS_DIR.mkdir(exist_ok=True)

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False  # guard against double-configuration


def configure_logging(
    level: int = logging.INFO,
    log_file: str = "pipeline.log",
    rich_console: bool = True,
) -> None:
    """
    Configure the root logger once per process.

    Parameters
    ----------
    level:        Root log level (default INFO).
    log_file:     File name inside logs/ directory.
    rich_console: Whether to attach Rich's coloured console handler.
    """
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(level)

    # ── Rotating file handler ─────────────────────────────────
    file_path = _LOGS_DIR / log_file
    file_handler = logging.handlers.RotatingFileHandler(
        filename=file_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(file_handler)

    # ── Console handler ───────────────────────────────────────
    if rich_console:
        console = Console(stderr=True)
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=True,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
        )
        console_handler.setLevel(level)
        root.addHandler(console_handler)
    else:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
        root.addHandler(stream_handler)

    # ── Suppress noisy third-party loggers ───────────────────
    for noisy in ("httpx", "httpcore", "urllib3", "asyncio", "playwright"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.

    Ensures logging has been configured before returning.
    Idempotent — safe to call from any module.
    """
    if not _configured:
        configure_logging()
    return logging.getLogger(name)
