import json
import os
import uuid
from datetime import datetime

from config.paths import CHAT_SESSIONS_JSON, DATA_DIR

SESSIONS_FILE = str(CHAT_SESSIONS_JSON)


def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _load() -> dict:
    _ensure_file()
    with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save_session(user_email: str, chat_history: list, result: dict | None):
    """Save the current chat as a 'previous chat' entry. Called on New Chat / Logout."""
    if not chat_history:
        return  # nothing worth saving

    data = _load()
    data.setdefault(user_email, [])

    if result:
        title = result.get("title", "Untitled chat")
    else:
        title = chat_history[0]["content"][:50]

    # rag_chain can't be saved to JSON — keep only serializable fields
    serializable_result = None
    if result:
        serializable_result = {
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

    session = {
        "id": str(uuid.uuid4()),
        "title": title,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "chat_history": chat_history,
        "result": serializable_result,
    }

    data[user_email].insert(0, session)
    data[user_email] = data[user_email][:30]
    _save(data)


def upsert_session(user_email: str, session_id: str, chat_history: list, result: dict | None):
    """Save or update the CURRENT conversation in place, keyed by session_id.

    Called after every message exchange so the active chat shows up in
    Recent immediately, live, instead of only appearing after the user
    clicks New Chat (which finalizes the previous conversation).
    """
    if not chat_history:
        return

    data = _load()
    data.setdefault(user_email, [])

    if result:
        title = result.get("title", "Untitled chat")
    else:
        title = chat_history[0]["content"][:50]

    serializable_result = None
    if result:
        serializable_result = {
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

    sessions = data[user_email]
    existing_idx = next(
        (i for i, s in enumerate(sessions) if s.get("id") == session_id), None
    )

    session = {
        "id": session_id,
        "title": title,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "chat_history": chat_history,
        "result": serializable_result,
    }

    if existing_idx is not None:
        sessions.pop(existing_idx)
    sessions.insert(0, session)

    data[user_email] = sessions[:30]
    _save(data)


def get_sessions(user_email: str) -> list:
    data = _load()
    return data.get(user_email, [])

def delete_session(user_email: str, session_id: str):
    data = _load()
    sessions = data.get(user_email, [])
    data[user_email] = [s for s in sessions if s.get("id") != session_id]
    _save(data)