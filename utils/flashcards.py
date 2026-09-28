"""Flashcards in the SQLite DB (Step 3). Table: ``flashcards`` (``db/models.py: Flashcard``).

Same conventions as ``utils/history_manager.py`` and ``utils/quiz_attempts.py``:
users are looked up by email, sessions come from ``db.session.get_db()``.

Every function checks ownership through the user's id, so one user can never
read, review or delete another user's cards.

Queries are intentionally simple (``filter_by`` then filter/sort in Python): a
user has at most a few thousand cards, and it keeps the logic easy to test.

``Flashcard.due_at`` holds MIDNIGHT of the due day, so "due" simply means
``due_at <= now``.
"""

from __future__ import annotations

from datetime import date, datetime, time

from config import get_logger
from core.flashcard_utils import MAX_BACK_CHARS, MAX_FRONT_CHARS, card_key
from core.spaced_repetition import MASTERED_STAGE, next_review
from db.models import Flashcard, User
from db.session import get_db

log = get_logger(__name__)


def _midnight(day: date) -> datetime:
    return datetime.combine(day, time.min)


def _to_dict(row: Flashcard) -> dict:
    return {
        "id": row.id,
        "front": row.front,
        "back": row.back,
        "video_title": row.video_title,
        "source": row.source,
        "stage": row.stage,
        "due_date": row.due_at.strftime("%Y-%m-%d"),
        "times_correct": row.times_correct,
        "times_wrong": row.times_wrong,
    }


def _find_user(db, user_email: str):
    return db.query(User).filter_by(email=user_email).first()


def _user_cards(db, user_id: int) -> list:
    return db.query(Flashcard).filter_by(user_id=user_id).all()


# ------------------------------------------------------------------ create ---
def add_cards(
    user_email: str,
    cards: list[dict],
    video_title: str = "",
    session_id: str | None = None,
    source: str = "video",
) -> dict:
    """Store new cards (due immediately). Cards whose question the user already has are skipped.

    Returns ``{"added": n, "skipped": m}``.
    """
    with get_db() as db:
        user = _find_user(db, user_email)
        if not user:
            log.warning("add_cards: no user with email %r; nothing saved.", user_email)
            return {"added": 0, "skipped": len(cards)}

        existing = {c.card_key for c in _user_cards(db, user.id)}
        due_today = _midnight(date.today())
        added = skipped = 0

        for card in cards:
            front = str(card.get("front", "")).strip()[:MAX_FRONT_CHARS]
            back = str(card.get("back", "")).strip()[:MAX_BACK_CHARS]
            if not front or not back:
                skipped += 1
                continue

            key = card_key(front)
            if key in existing:
                skipped += 1
                continue
            existing.add(key)

            db.add(
                Flashcard(
                    user_id=user.id,
                    session_id=str(session_id)[:36] if session_id else None,
                    video_title=(video_title or "")[:255],
                    source=source[:20],
                    card_key=key,
                    front=front,
                    back=back,
                    stage=0,
                    due_at=due_today,
                    times_correct=0,
                    times_wrong=0,
                    created_at=datetime.now(),
                )
            )
            added += 1

        db.commit()

    log.info("Flashcards saved for %s: %d added, %d skipped", user_email, added, skipped)
    return {"added": added, "skipped": skipped}


# -------------------------------------------------------------------- read ---
def get_card(user_email: str, card_id: int) -> dict | None:
    with get_db() as db:
        user = _find_user(db, user_email)
        if not user:
            return None
        row = db.query(Flashcard).filter_by(id=card_id, user_id=user.id).first()
        return _to_dict(row) if row else None


def get_due_cards(user_email: str, limit: int = 20) -> list[dict]:
    """Cards due now (oldest due first)."""
    with get_db() as db:
        user = _find_user(db, user_email)
        if not user:
            return []
        now = datetime.now()
        due = [c for c in _user_cards(db, user.id) if c.due_at <= now]
        due.sort(key=lambda c: (c.due_at, c.id))
        return [_to_dict(c) for c in due[:limit]]


def list_cards(user_email: str, limit: int = 30) -> list[dict]:
    """Newest cards first."""
    with get_db() as db:
        user = _find_user(db, user_email)
        if not user:
            return []
        cards = _user_cards(db, user.id)
        cards.sort(key=lambda c: (c.created_at, c.id), reverse=True)
        return [_to_dict(c) for c in cards[:limit]]


def get_card_counts(user_email: str) -> dict:
    """``total`` / ``due`` (now) / ``learning`` (not yet mastered) / ``mastered``."""
    with get_db() as db:
        user = _find_user(db, user_email)
        if not user:
            return {"total": 0, "due": 0, "learning": 0, "mastered": 0}
        cards = _user_cards(db, user.id)
        now = datetime.now()
        mastered = sum(1 for c in cards if c.stage >= MASTERED_STAGE)
        return {
            "total": len(cards),
            "due": sum(1 for c in cards if c.due_at <= now),
            "learning": len(cards) - mastered,
            "mastered": mastered,
        }


def get_due_count(user_email: str) -> int:
    return get_card_counts(user_email)["due"]


def get_next_due_date(user_email: str) -> date | None:
    """The earliest FUTURE due date, or None if nothing is scheduled ahead."""
    with get_db() as db:
        user = _find_user(db, user_email)
        if not user:
            return None
        now = datetime.now()
        future = [c.due_at for c in _user_cards(db, user.id) if c.due_at > now]
        return min(future).date() if future else None


# ------------------------------------------------------------------ update ---
def review_card(
    user_email: str, card_id: int, correct: bool, today: date | None = None
) -> dict | None:
    """Record one review and reschedule the card (see core/spaced_repetition.py)."""
    today = today or date.today()
    with get_db() as db:
        user = _find_user(db, user_email)
        if not user:
            return None
        row = db.query(Flashcard).filter_by(id=card_id, user_id=user.id).first()
        if not row:
            return None

        new_stage, due_day = next_review(row.stage, correct, today)
        row.stage = new_stage
        row.due_at = _midnight(due_day)
        if correct:
            row.times_correct = (row.times_correct or 0) + 1
        else:
            row.times_wrong = (row.times_wrong or 0) + 1
        row.last_reviewed_at = datetime.now()
        db.commit()
        return _to_dict(row)


def delete_card(user_email: str, card_id: int) -> bool:
    with get_db() as db:
        user = _find_user(db, user_email)
        if not user:
            return False
        row = db.query(Flashcard).filter_by(id=card_id, user_id=user.id).first()
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True
