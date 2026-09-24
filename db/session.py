"""Engine + session setup for the app's SQLite database.

D-04: SQLite via SQLAlchemy, written so switching to Postgres later is a
config change, not a rewrite -- that's why the connection string is built
from settings/paths rather than hardcoded, and why nothing here is
SQLite-specific except the file path itself.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config.paths import DB_PATH

# check_same_thread=False: Streamlit can call into this from more than one
# script-run/thread across reruns. SQLite still serializes writes internally,
# which is exactly the safety property this migration is for (see the
# load-whole-file/modify/write-whole-file pattern in the old
# utils/*.py + auth/auth_manager.py JSON helpers this replaces).
ENGINE = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=ENGINE, expire_on_commit=False)


def init_db() -> None:
    """Create all tables if they don't exist yet. Safe to call repeatedly."""
    from db.models import Base  # local import avoids a circular import at module load

    Base.metadata.create_all(ENGINE)


@contextmanager
def get_db():
    """Usage:

        with get_db() as db:
            db.add(obj)
            db.commit()

    Always closes the session, even on error.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
