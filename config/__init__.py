"""Application configuration.

    from config import bootstrap, settings
    from config.logging_config import get_logger
"""

from config.logging_config import get_logger, setup_logging
from config.paths import ensure_runtime_dirs
from config.settings import settings

__all__ = ["bootstrap", "settings", "get_logger", "setup_logging", "ensure_runtime_dirs"]

_bootstrapped = False


def bootstrap() -> None:
    """Prepare the process: logging, runtime directories, config report.

    Call once at the top of any entry point (app.py, main.py, scripts, tests).
    Idempotent, so Streamlit reruns cost nothing.
    """
    global _bootstrapped

    setup_logging()
    ensure_runtime_dirs()

    if _bootstrapped:
        return
    _bootstrapped = True

    log = get_logger(__name__)
    log.info("AI Video Assistant starting (env=%s)", settings.env)

    for note in settings.warnings():
        log.warning(note)

    missing = settings.missing_required()
    if missing:
        log.error(
            "Missing required configuration: %s. Analysis will fail until these "
            "are set in .env",
            ", ".join(missing),
        )
