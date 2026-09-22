"""Step 1 smoke tests: the config package works and changes nothing else.

    pytest tests/test_config.py -v
"""

import importlib
import logging

import pytest

from config import bootstrap
from config import paths
from config.logging_config import get_logger, setup_logging
from config.settings import Settings, settings


# ---------------------------------------------------------------- paths


def test_root_dir_is_project_root():
    """ROOT_DIR must point at the folder containing app.py, not config/."""
    assert (paths.ROOT_DIR / "app.py").exists()
    assert (paths.ROOT_DIR / "core").is_dir()


def test_paths_are_absolute():
    """The whole point of this module: cwd must not matter."""
    for name in dir(paths):
        value = getattr(paths, name)
        if isinstance(value, type(paths.ROOT_DIR)):
            assert value.is_absolute(), f"{name} is relative"


def test_downloads_dir_keeps_legacy_spelling():
    """Step 1 must not orphan files already on disk. Renamed in Step 6."""
    assert paths.DOWNLOADS_DIR.name == "downloades"


def test_ensure_runtime_dirs_is_idempotent():
    paths.ensure_runtime_dirs()
    paths.ensure_runtime_dirs()
    for directory in paths.RUNTIME_DIRS:
        assert directory.is_dir()


# ------------------------------------------------------------- settings


def test_settings_never_raises_without_env(monkeypatch):
    """The app must start with no keys configured -- it just can't analyse."""
    for key in ("GROQ_API_KEY", "SARVAM_API_KEY", "SECRET_KEY", "WHISPER_MODEL"):
        monkeypatch.delenv(key, raising=False)
    blank = Settings()
    assert blank.groq_api_key == ""
    assert "GROQ_API_KEY" in blank.missing_required()


def test_settings_strips_whitespace(monkeypatch):
    """The existing .env uses `GROQ_API_KEY = abc`, which leaves a leading space."""
    monkeypatch.setenv("GROQ_API_KEY", "  abc123  ")
    assert Settings().groq_api_key == "abc123"


def test_defaults_match_previous_hardcoded_values():
    """Behaviour parity: these were literals in core/ before Step 1."""
    assert settings.whisper_model or True  # env may override; just must exist
    fresh = Settings()
    assert fresh.groq_model == "openai/gpt-oss-120b"
    assert fresh.embedding_model == "all-MiniLM-L6-v2"
    assert fresh.chunk_minutes == 10
    assert fresh.retriever_k == 6
    assert fresh.sarvam_model == "saaras:v2.5"


@pytest.mark.parametrize(
    "raw,expected",
    [("true", True), ("1", True), ("YES", True), ("off", False), ("", False)],
)
def test_bool_parsing(monkeypatch, raw, expected):
    monkeypatch.setenv("DEBUG", raw)
    assert Settings().debug is expected


def test_int_parsing_survives_garbage(monkeypatch):
    monkeypatch.setenv("CHUNK_MINUTES", "not-a-number")
    assert Settings().chunk_minutes == 10


def test_admin_emails_parsed_and_lowercased(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "A@x.com, b@y.com ,")
    assert Settings().admin_emails == ["a@x.com", "b@y.com"]


def test_settings_is_immutable():
    with pytest.raises(Exception):
        settings.groq_api_key = "tampered"


# -------------------------------------------------------------- logging


def test_setup_logging_does_not_duplicate_handlers():
    """Streamlit reruns the script constantly; handlers must not accumulate."""
    setup_logging()
    count = len(logging.getLogger().handlers)
    for _ in range(5):
        setup_logging()
    assert len(logging.getLogger().handlers) == count


def test_get_logger_returns_named_logger():
    assert get_logger("a.b.c").name == "a.b.c"


def test_noisy_libraries_are_quieted():
    setup_logging()
    assert logging.getLogger("chromadb").level >= logging.WARNING


# ------------------------------------------------------------ bootstrap


def test_bootstrap_is_idempotent():
    for _ in range(3):
        bootstrap()
    for directory in paths.RUNTIME_DIRS:
        assert directory.is_dir()


# -------------------------------------------- no behaviour change yet


@pytest.mark.parametrize(
    "module",
    [
        "auth.auth_manager",
        "utils.history_manager",
        "utils.chat_sessions",
        "utils.audio_processor",
        "core.extractor",
        "core.summarizer",
        "core.quiz_generator",
        "core.notes_generator",
        "core.vector_store",
    ],
)
def test_existing_modules_still_import(module):
    """Step 1 touched only app.py and main.py. Everything else must be untouched
    and still importable."""
    importlib.import_module(module)
