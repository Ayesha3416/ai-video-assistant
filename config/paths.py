"""Every filesystem path the app touches, in one place.

Before this module, paths were relative strings scattered across six files
("data", "downloades", "vector_db", os.path.join("data", "users.json") ...),
which meant the app only worked if you happened to launch it from the project
root. These are absolute and anchored to the repo, so the working directory no
longer matters.

Step 1 deliberately keeps every path pointing at exactly where it points today
-- including the "downloades" spelling. Renaming it is a Step 6 concern, and
Step 1 must not change behaviour.
"""

from pathlib import Path

# config/paths.py -> config/ -> project root
ROOT_DIR = Path(__file__).resolve().parent.parent

# ---- Data ----
DATA_DIR = ROOT_DIR / "data"
FRAMES_DIR = DATA_DIR / "frames"

# Legacy JSON stores. Step 2 migrates these into SQLite; they are kept
# afterwards as read-only migration input, never written to again.
USERS_JSON = DATA_DIR / "users.json"
HISTORY_JSON = DATA_DIR / "history.json"
CHAT_SESSIONS_JSON = DATA_DIR / "chat_sessions.json"

# ---- Database (created in Step 2) ----
DB_PATH = DATA_DIR / "app.db"

# ---- Vector indexes ----
VECTOR_DB_DIR = ROOT_DIR / "vector_db"

# ---- Scratch space ----
# NOTE: spelling is intentional -- this is the existing folder name and
# renaming it now would orphan whatever is already on disk. Step 6 renames it
# as part of the temp-file lifecycle work.
DOWNLOADS_DIR = ROOT_DIR / "downloades"

# ---- Logs ----
LOGS_DIR = ROOT_DIR / "logs"
LOG_FILE = LOGS_DIR / "app.log"

# ---- Static assets ----
THEME_DIR = ROOT_DIR / "ui" / "theme"

#: Directories that must exist before the app can do anything useful.
RUNTIME_DIRS = (
    DATA_DIR,
    FRAMES_DIR,
    VECTOR_DB_DIR,
    DOWNLOADS_DIR,
    LOGS_DIR,
)


def ensure_runtime_dirs() -> None:
    """Create every runtime directory. Safe to call repeatedly.

    Replaces the module-level ``os.makedirs(...)`` side effects that currently
    fire on import in audio_processor.py and frame_extractor.py.
    """
    for directory in RUNTIME_DIRS:
        directory.mkdir(parents=True, exist_ok=True)
