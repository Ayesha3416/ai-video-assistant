"""SQLAlchemy models. Field names/shapes deliberately mirror the JSON records
in data/users.json, data/history.json, data/chat_sessions.json (see the
migration script) so Step 7b/7c can swap the JSON-backed functions in
auth/auth_manager.py, utils/history_manager.py, utils/chat_sessions.py for
DB-backed ones with minimal changes to their callers.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # "email" historically also holds the one legacy non-email username
    # account (see migration script) -- kept as the unique login key either way.
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Nullable: an account migrated from JSON before ever logging in again
    # after Step 5 (bcrypt) may still only have the old salt+SHA-256 fields
    # below. auth code checks bcrypt_hash first, falls back to the legacy
    # pair, and upgrades to bcrypt_hash on next successful login -- same
    # transparent-upgrade behavior Step 5 already established, just against
    # the DB now instead of JSON.
    bcrypt_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legacy_salt: Mapped[str | None] = mapped_column(String(64), nullable=True)
    legacy_password_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    # D-08: roles user/admin, first admin bootstrapped from ADMIN_EMAILS later.
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    history_entries: Mapped[list["HistoryEntry"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    # Keeps the existing uuid4-hex string IDs already saved in
    # chat_sessions.json / referenced by the sidebar and delete-dialog code,
    # so migrated rows don't need their IDs rewritten.
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="Untitled chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Same shape as the old JSON: a list of {role, content, time, ...} dicts.
    chat_history: Mapped[list] = mapped_column(JSON, default=list)
    # Same shape as the old JSON "result" (or null): title/transcript/summary/
    # action_items/key_decisions/open_questions/category/segments/source.
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="chat_sessions")


class HistoryEntry(Base):
    __tablename__ = "history_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(Text, default="")
    summary_snippet: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(20), default="english")
    category: Mapped[str] = mapped_column(String(50), default="Other")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="history_entries")


class QuizAttempt(Base):
    """One submitted quiz (Step 2 / issue I-02).

    Stores the questions and the picked answers, not just the score, so an
    attempt can be reviewed later and its mistakes reused (e.g. for flashcards).
    Attempts are kept even if the chat session they came from is deleted.
    """

    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # chat_sessions.id of the conversation the quiz was taken in (not a FK on purpose).
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    quiz_id: Mapped[str] = mapped_column(String(36), default="", index=True)
    video_title: Mapped[str] = mapped_column(String(255), default="")
    num_questions: Mapped[int] = mapped_column(default=0)
    score: Mapped[int] = mapped_column(default=0)
    # [{"question": str, "options": [str, ...], "correct_index": int}, ...]
    questions: Mapped[list] = mapped_column(JSON, default=list)
    # [picked_option_index | None, ...] -- same order as `questions`
    answers: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Flashcard(Base):
    """One flashcard with its spaced-repetition state (Step 3, decision D-07).

    ``stage`` = consecutive successful reviews (0 = new / just missed).
    ``due_at`` = MIDNIGHT of the day the card is next due (due when due_at <= now).
    ``card_key`` = hash of the normalised question, used to skip duplicates per user.
    """

    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # chat_sessions.id the card came from (not a FK on purpose: cards outlive chats).
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    video_title: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(20), default="video")  # video | quiz | manual
    card_key: Mapped[str] = mapped_column(String(40), index=True)
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    stage: Mapped[int] = mapped_column(default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    times_correct: Mapped[int] = mapped_column(default=0)
    times_wrong: Mapped[int] = mapped_column(default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
