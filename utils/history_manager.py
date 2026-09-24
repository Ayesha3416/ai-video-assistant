"""Analysis history, now backed by the SQLite DB (db/models.py) instead of
data/history.json. Public API unchanged on purpose -- add_entry(),
get_history(), get_stats(), get_*_dataframe() keep the exact same
signatures/return shapes (get_history() still returns plain dicts with the
same keys: title, source, language, category, summary_snippet, timestamp)
-- so ui/dashboard.py needed no changes for this switch.
"""
from datetime import datetime

import pandas as pd

from db.session import get_db
from db.models import User, HistoryEntry

MAX_ENTRIES_PER_USER = 50


def _entry_to_dict(entry: HistoryEntry) -> dict:
    return {
        "title": entry.title,
        "source": entry.source,
        "language": entry.language,
        "category": entry.category,
        "summary_snippet": entry.summary_snippet,
        "timestamp": entry.created_at.strftime("%Y-%m-%d %H:%M"),
    }


def add_entry(user_email: str, title: str, source: str, summary: str, language: str = "english", category: str = "Other"):
    with get_db() as db:
        user = db.query(User).filter_by(email=user_email).first()
        if not user:
            return  # defensive: shouldn't happen for a logged-in user

        db.add(HistoryEntry(
            user_id=user.id,
            title=title,
            source=source,
            language=language,
            category=category,
            summary_snippet=summary[:150] + ("..." if len(summary) > 150 else ""),
            created_at=datetime.now(),
        ))
        db.flush()

        # Keep only the most recent MAX_ENTRIES_PER_USER, same cap as before.
        all_ids = [
            row.id for row in
            db.query(HistoryEntry.id)
            .filter_by(user_id=user.id)
            .order_by(HistoryEntry.created_at.desc())
            .all()
        ]
        stale_ids = all_ids[MAX_ENTRIES_PER_USER:]
        if stale_ids:
            db.query(HistoryEntry).filter(HistoryEntry.id.in_(stale_ids)).delete(
                synchronize_session=False
            )

        db.commit()


def get_history(user_email: str) -> list:
    with get_db() as db:
        user = db.query(User).filter_by(email=user_email).first()
        if not user:
            return []
        entries = (
            db.query(HistoryEntry)
            .filter_by(user_id=user.id)
            .order_by(HistoryEntry.created_at.desc())
            .all()
        )
        return [_entry_to_dict(e) for e in entries]


def get_stats(user_email: str) -> dict:
    history = get_history(user_email)
    return {
        "total_analyzed": len(history),
        "last_activity": history[0]["timestamp"] if history else "No activity yet",
    }


def get_activity_dataframe(user_email: str) -> pd.DataFrame:
    history = get_history(user_email)
    if not history:
        return pd.DataFrame(columns=["date", "count"])

    dates = [item["timestamp"].split(" ")[0] for item in history]
    df = pd.DataFrame({"date": dates})
    counts = df.groupby("date").size().reset_index(name="count")
    counts = counts.sort_values("date")
    return counts


def get_language_dataframe(user_email: str) -> pd.DataFrame:
    history = get_history(user_email)
    if not history:
        return pd.DataFrame(columns=["language", "count"])

    langs = [item.get("language", "english") for item in history]
    df = pd.DataFrame({"language": langs})
    counts = df.groupby("language").size().reset_index(name="count")
    return counts


def get_category_dataframe(user_email: str) -> pd.DataFrame:
    history = get_history(user_email)
    if not history:
        return pd.DataFrame(columns=["category", "count"])

    cats = [item.get("category", "Other") for item in history]
    df = pd.DataFrame({"category": cats})
    counts = df.groupby("category").size().reset_index(name="count")
    return counts
