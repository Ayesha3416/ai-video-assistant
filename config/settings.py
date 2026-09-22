"""One source of truth for configuration.

Today, `os.getenv` is called at import time in five different modules, with
defaults duplicated between them, and `load_dotenv()` is called in three
places. This module loads the environment once and exposes typed values.

Nothing here raises on a missing key. The app must still start with no API
keys configured -- it just can't run an analysis. Use `validate()` to report
what's missing rather than crashing at import.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from config.paths import ROOT_DIR

# Load .env exactly once, from the project root, regardless of cwd.
load_dotenv(ROOT_DIR / ".env")


def _get(name: str, default: str = "") -> str:
    """Env lookup that tolerates the `KEY = value` spacing in the current .env.

    python-dotenv keeps whitespace around `=` in the *value*, so `GROQ_API_KEY
    = abc` currently yields `" abc"`. Stripping here avoids a very confusing
    401 from Groq.
    """
    return (os.getenv(name) or default).strip()


def _get_bool(name: str, default: bool = False) -> bool:
    raw = _get(name).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = _get(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _get_list(name: str) -> list[str]:
    raw = _get(name)
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # ---- Environment ----
    env: str = field(default_factory=lambda: _get("APP_ENV", "development"))
    debug: bool = field(default_factory=lambda: _get_bool("DEBUG", False))

    # ---- LLM / transcription providers ----
    groq_api_key: str = field(default_factory=lambda: _get("GROQ_API_KEY"))
    groq_model: str = field(
        default_factory=lambda: _get("GROQ_MODEL", "openai/gpt-oss-120b")
    )
    sarvam_api_key: str = field(default_factory=lambda: _get("SARVAM_API_KEY"))
    sarvam_model: str = field(
        default_factory=lambda: _get("SARVAM_STT_MODEL", "saaras:v2.5")
    )
    whisper_model: str = field(
        default_factory=lambda: _get("WHISPER_MODEL", "small")
    )

    # ---- Security (used from Step 3) ----
    secret_key: str = field(default_factory=lambda: _get("SECRET_KEY"))
    session_days: int = field(default_factory=lambda: _get_int("SESSION_DAYS", 14))
    bcrypt_rounds: int = field(default_factory=lambda: _get_int("BCRYPT_ROUNDS", 12))
    admin_emails: list[str] = field(default_factory=lambda: _get_list("ADMIN_EMAILS"))

    # ---- Pipeline tuning (previously hardcoded) ----
    chunk_minutes: int = field(default_factory=lambda: _get_int("CHUNK_MINUTES", 10))
    embedding_model: str = field(
        default_factory=lambda: _get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    )
    retriever_k: int = field(default_factory=lambda: _get_int("RETRIEVER_K", 6))

    # ---- Retention (used from Step 6) ----
    frame_retention_days: int = field(
        default_factory=lambda: _get_int("FRAME_RETENTION_DAYS", 30)
    )
    download_retention_hours: int = field(
        default_factory=lambda: _get_int("DOWNLOAD_RETENTION_HOURS", 6)
    )

    # ---- Logging ----
    log_level: str = field(default_factory=lambda: _get("LOG_LEVEL", "INFO").upper())
    log_to_file: bool = field(default_factory=lambda: _get_bool("LOG_TO_FILE", True))

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"production", "prod"}

    def missing_required(self) -> list[str]:
        """Names of settings the app genuinely cannot run an analysis without."""
        missing = []
        if not self.groq_api_key:
            missing.append("GROQ_API_KEY")
        return missing

    def warnings(self) -> list[str]:
        """Non-fatal configuration problems worth surfacing in the log."""
        notes = []
        if not self.sarvam_api_key:
            notes.append("SARVAM_API_KEY is not set -- Hinglish transcription will fail.")
        if not self.secret_key:
            notes.append(
                "SECRET_KEY is not set -- a random one will be generated per process, "
                "so logins will not survive a restart."
            )
        elif len(self.secret_key) < 32:
            notes.append("SECRET_KEY is shorter than 32 characters.")
        if self.is_production and self.debug:
            notes.append("DEBUG is enabled in a production environment.")
        return notes


#: Import this, not the class.
settings = Settings()
