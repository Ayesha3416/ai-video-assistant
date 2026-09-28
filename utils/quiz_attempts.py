"""Saved quiz attempts (Step 2 / issue I-02).

Before this, quiz answers and scores lived only in ``st.session_state`` and
vanished on refresh. Every submitted quiz is now stored in the
``quiz_attempts`` table (see ``db/models.py``: ``QuizAttempt``).

Same conventions as ``utils/history_manager.py``: users are looked up by email,
sessions come from ``db.session.get_db()``.

``save_attempt`` never raises -- a database hiccup must not break the quiz the
user just finished; it logs and returns ``None`` instead.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from config import get_logger
from core.quiz_scoring import percent, score_answers, summarize_attempts, trend_dataframe
from db.models import QuizAttempt, User
from db.session import get_db

log = get_logger(__name__)


def _to_dict(row: QuizAttempt) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "quiz_id": row.quiz_id,
        "video_title": row.video_title,
        "num_questions": row.num_questions,
        "score": row.score,
        "percent": percent(row.score, row.num_questions),
        "timestamp": row.created_at.strftime("%Y-%m-%d %H:%M"),
    }


def save_attempt(
    user_email: str,
    session_id: str | None,
    video_title: str,
    quiz_id: str,
    questions: list,
    answers: list,
) -> dict | None:
    """Store one submitted quiz. Returns the saved attempt as a dict, or None on failure.

    ``questions`` is the list produced by ``core.quiz_generator.generate_quiz``
    (``{"question", "options", "correct_index"}`` dicts); ``answers`` is the list
    of picked option indexes (``None`` for unanswered). Both are stored, so the
    attempt can be reviewed later (and reused for flashcards).
    """
    try:
        score = score_answers(questions, answers)
        with get_db() as db:
            user = db.query(User).filter_by(email=user_email).first()
            if not user:
                log.warning("save_attempt: no user with email %r; attempt not saved.", user_email)
                return None

            row = QuizAttempt(
                user_id=user.id,
                session_id=str(session_id)[:36] if session_id else None,
                quiz_id=str(quiz_id or "")[:36],
                video_title=(video_title or "")[:255],
                num_questions=len(questions),
                score=score,
                questions=list(questions),
                answers=list(answers),
                created_at=datetime.now(),
            )
            db.add(row)
            db.commit()
            saved = _to_dict(row)

        log.info("Saved quiz attempt: %d/%d for %s", score, len(questions), user_email)
        return saved
    except Exception:  # noqa: BLE001 - never break the quiz UI over persistence
        log.exception("Could not save quiz attempt")
        return None


def get_attempts(user_email: str, limit: int | None = 200) -> list[dict]:
    """A user's attempts, newest first. ``limit=None`` returns all of them."""
    with get_db() as db:
        user = db.query(User).filter_by(email=user_email).first()
        if not user:
            return []
        query = (
            db.query(QuizAttempt)
            .filter_by(user_id=user.id)
            .order_by(QuizAttempt.created_at.desc(), QuizAttempt.id.desc())
        )
        if limit:
            query = query.limit(limit)
        return [_to_dict(r) for r in query.all()]


def get_quiz_summary(user_email: str) -> dict:
    """attempts / average_percent / best_percent / latest_percent across ALL attempts."""
    return summarize_attempts(get_attempts(user_email, limit=None))


def get_score_trend_dataframe(user_email: str, limit: int = 100) -> pd.DataFrame:
    """Oldest-to-newest scores of the most recent ``limit`` attempts (for the chart)."""
    return trend_dataframe(get_attempts(user_email, limit=limit))
