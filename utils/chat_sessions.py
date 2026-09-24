"""Chat sessions, now backed by the SQLite DB (db/models.py) instead of
data/chat_sessions.json. Public API unchanged on purpose -- save_session(),
upsert_session(), get_sessions(), delete_session() keep the exact same
signatures/return shapes (get_sessions() still returns plain dicts with the
same keys: id, title, timestamp, chat_history, result) -- so ui/navbar.py,
ui/sidebar.py, ui/dashboard.py needed no changes for this switch.
"""
import uuid
from datetime import datetime

from db.session import get_db
from db.models import User, ChatSession

MAX_SESSIONS_PER_USER = 30


def _serializable_result(result: dict | None) -> dict | None:
    # rag_chain can't be saved to the DB (JSON column) -- keep only
    # serializable fields, same as the old JSON version did.
    if not result:
        return None
    return {
        "title": result.get("title"),
        "transcript": result.get("transcript"),
        "summary": result.get("summary"),
        "action_items": result.get("action_items"),
        "key_decisions": result.get("key_decisions"),
        "open_questions": result.get("open_questions"),
        "category": result.get("category"),
        "segments": result.get("segments"),
        "source": result.get("source"),
    }


def _session_to_dict(row: ChatSession) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "timestamp": row.created_at.strftime("%Y-%m-%d %H:%M"),
        "chat_history": row.chat_history,
        "result": row.result,
    }


def _trim_to_cap(db, user_id: int):
    all_ids = [
        row.id for row in
        db.query(ChatSession.id)
        .filter_by(user_id=user_id)
        .order_by(ChatSession.created_at.desc())
        .all()
    ]
    stale_ids = all_ids[MAX_SESSIONS_PER_USER:]
    if stale_ids:
        db.query(ChatSession).filter(ChatSession.id.in_(stale_ids)).delete(
            synchronize_session=False
        )


def save_session(user_email: str, chat_history: list, result: dict | None):
    """Save the current chat as a 'previous chat' entry. Called on New Chat / Logout."""
    if not chat_history:
        return  # nothing worth saving

    with get_db() as db:
        user = db.query(User).filter_by(email=user_email).first()
        if not user:
            return

        title = result.get("title", "Untitled chat") if result else chat_history[0]["content"][:50]

        db.add(ChatSession(
            id=str(uuid.uuid4()),
            user_id=user.id,
            title=title,
            created_at=datetime.now(),
            chat_history=chat_history,
            result=_serializable_result(result),
        ))
        db.flush()
        _trim_to_cap(db, user.id)
        db.commit()


def upsert_session(user_email: str, session_id: str, chat_history: list, result: dict | None):
    """Save or update the CURRENT conversation in place, keyed by session_id.

    Called after every message exchange so the active chat shows up in
    Recent immediately, live, instead of only appearing after the user
    clicks New Chat (which finalizes the previous conversation).
    """
    if not chat_history:
        return

    with get_db() as db:
        user = db.query(User).filter_by(email=user_email).first()
        if not user:
            return

        title = result.get("title", "Untitled chat") if result else chat_history[0]["content"][:50]

        row = db.query(ChatSession).filter_by(id=session_id, user_id=user.id).first()
        if row:
            row.title = title
            row.created_at = datetime.now()  # bumps it back to top of Recent, same as before
            row.chat_history = chat_history
            row.result = _serializable_result(result)
        else:
            db.add(ChatSession(
                id=session_id,
                user_id=user.id,
                title=title,
                created_at=datetime.now(),
                chat_history=chat_history,
                result=_serializable_result(result),
            ))

        db.flush()
        _trim_to_cap(db, user.id)
        db.commit()


def get_sessions(user_email: str) -> list:
    with get_db() as db:
        user = db.query(User).filter_by(email=user_email).first()
        if not user:
            return []
        rows = (
            db.query(ChatSession)
            .filter_by(user_id=user.id)
            .order_by(ChatSession.created_at.desc())
            .all()
        )
        return [_session_to_dict(r) for r in rows]


def delete_session(user_email: str, session_id: str):
    with get_db() as db:
        user = db.query(User).filter_by(email=user_email).first()
        if not user:
            return
        db.query(ChatSession).filter_by(id=session_id, user_id=user.id).delete()
        db.commit()
