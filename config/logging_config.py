"""Structured logging to replace the ~30 bare `print()` calls in the codebase.

Streamlit reruns the whole script on every interaction, so `setup_logging()`
is guarded against attaching duplicate handlers -- otherwise every log line
would be printed once per rerun, multiplying forever.

Usage anywhere in the app:

    from config.logging_config import get_logger
    log = get_logger(__name__)
    log.info("Transcribing chunk %s/%s", i, total)
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from config.paths import LOG_FILE, LOGS_DIR
from config.settings import settings

_CONSOLE_FORMAT = "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s"
_FILE_FORMAT = (
    "%(asctime)s  %(levelname)-7s  %(name)s  "
    "%(filename)s:%(lineno)d  %(message)s"
)
_DATE_FORMAT = "%H:%M:%S"

#: Marker attribute so repeated setup calls are idempotent across reruns.
_CONFIGURED_FLAG = "_ai_video_assistant_configured"

#: Third-party loggers that are noisy at INFO and tell us nothing useful.
_NOISY = (
    "httpx",
    "httpcore",
    "urllib3",
    "chromadb",
    "sentence_transformers",
    "watchdog",
    "matplotlib",
)


def setup_logging() -> None:
    """Configure the root logger. Safe to call on every Streamlit rerun."""
    root = logging.getLogger()

    if getattr(root, _CONFIGURED_FLAG, False):
        return

    level = getattr(logging, settings.log_level, logging.INFO)
    root.setLevel(level)

    # Drop anything Streamlit or a library attached before us, so we don't
    # double-print.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_CONSOLE_FORMAT, _DATE_FORMAT))
    root.addHandler(console)

    if settings.log_to_file:
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=5 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(logging.Formatter(_FILE_FORMAT))
            root.addHandler(file_handler)
        except OSError as exc:
            # A read-only filesystem (some container setups) must not stop the
            # app from starting -- console logging is enough.
            root.warning("File logging disabled: %s", exc)

    for name in _NOISY:
        logging.getLogger(name).setLevel(logging.WARNING)

    setattr(root, _CONFIGURED_FLAG, True)

    root.debug("Logging configured at %s", settings.log_level)


def get_logger(name: str) -> logging.Logger:
    """Return a module logger, configuring logging on first use."""
    setup_logging()
    return logging.getLogger(name)
