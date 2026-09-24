#!/usr/bin/env python3
"""One-time migration: data/*.json -> data/app.db (SQLite).

Run from the project root with the venv active:
    python3 scripts/migrate_json_to_sqlite.py

Safe to re-run: existing rows (matched by email / chat session id) are
skipped, not duplicated, so running it twice by accident does no harm.

The source .json files are NOT deleted -- they're copied into
data/json_backup_pre_sqlite/ untouched, exactly as they were before this
script ran. Nothing in this step changes how the app currently reads/writes
its data (auth/auth_manager.py, utils/history_manager.py,
utils/chat_sessions.py are untouched) -- that switch-over is Step 7b/7c.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import bootstrap, get_logger
from config.paths import USERS_JSON, HISTORY_JSON, CHAT_SESSIONS_JSON, DATA_DIR

bootstrap()

from db.session import init_db, get_db
from db.models import User, ChatSession, HistoryEntry

log = get_logger(__name__)

BACKUP_DIR = DATA_DIR / "json_backup_pre_sqlite"


def _load_json(path: Path) -> dict:
    if not path.exists():
        log.warning("%s does not exist -- treating as empty.", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_timestamp(ts: str | None) -> datetime:
    if not ts:
        return datetime.utcnow()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    log.warning("Could not parse timestamp %r, using now().", ts)
    return datetime.utcnow()


def backup_json_files() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for path in (USERS_JSON, HISTORY_JSON, CHAT_SESSIONS_JSON):
        if path.exists():
            dest = BACKUP_DIR / path.name
            shutil.copy2(path, dest)
            log.info("Backed up %s -> %s", path, dest)


def migrate_users(db) -> dict[str, User]:
    """Returns {original_json_key: User row} so other migrators can look up
    the right user_id without a second DB query per record."""
    users_data = _load_json(USERS_JSON)
    email_to_user: dict[str, User] = {}

    for key, record in users_data.items():
        existing = db.query(User).filter_by(email=key).first()
        if existing:
            log.info("User %s already migrated -- skipping.", key)
            email_to_user[key] = existing
            continue

        user = User(
            email=key,
            display_name=record.get("display_name", ""),
        )
        if "bcrypt_hash" in record:
            user.bcrypt_hash = record["bcrypt_hash"]
        else:
            # Not yet upgraded to bcrypt (see db/models.py User docstring).
            user.legacy_salt = record.get("salt")
            user.legacy_password_hash = record.get("password_hash")

        db.add(user)
        db.flush()  # populate user.id without a full commit yet
        email_to_user[key] = user
        log.info("Migrated user %s (bcrypt=%s)", key, "bcrypt_hash" in record)

    db.commit()
    return email_to_user


def migrate_history(db, email_to_user: dict[str, User]) -> None:
    history_data = _load_json(HISTORY_JSON)
    count = 0
    for email, entries in history_data.items():
        user = email_to_user.get(email)
        if not user:
            log.warning("history.json has entries for unknown user %s -- skipping.", email)
            continue
        for entry in entries:
            dup = (
                db.query(HistoryEntry)
                .filter_by(
                    user_id=user.id,
                    title=entry.get("title", ""),
                    source=entry.get("source", ""),
                )
                .first()
            )
            if dup:
                continue
            db.add(
                HistoryEntry(
                    user_id=user.id,
                    title=entry.get("title", ""),
                    source=entry.get("source", ""),
                    summary_snippet=entry.get("summary_snippet", ""),
                    language=entry.get("language", "english"),
                    category=entry.get("category", "Other"),
                    created_at=_parse_timestamp(entry.get("timestamp")),
                )
            )
            count += 1
    db.commit()
    log.info("Migrated %d history entries.", count)


def migrate_chat_sessions(db, email_to_user: dict[str, User]) -> None:
    sessions_data = _load_json(CHAT_SESSIONS_JSON)
    count = 0
    for email, sessions in sessions_data.items():
        user = email_to_user.get(email)
        if not user:
            log.warning("chat_sessions.json has entries for unknown user %s -- skipping.", email)
            continue
        for session in sessions:
            sid = session.get("id")
            if sid and db.query(ChatSession).filter_by(id=sid).first():
                continue
            row = ChatSession(
                user_id=user.id,
                title=session.get("title", "Untitled chat"),
                created_at=_parse_timestamp(session.get("timestamp")),
                chat_history=session.get("chat_history", []),
                result=session.get("result"),
            )
            if sid:
                row.id = sid
            db.add(row)
            count += 1
    db.commit()
    log.info("Migrated %d chat sessions.", count)


def main() -> int:
    print("== Migrating JSON data into SQLite ==")
    backup_json_files()
    init_db()

    with get_db() as db:
        email_to_user = migrate_users(db)
        migrate_history(db, email_to_user)
        migrate_chat_sessions(db, email_to_user)

    print(f"\nDone. Backup of original JSON files: {BACKUP_DIR}")
    print("Nothing in the running app has switched to the DB yet -- that's the next step.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
