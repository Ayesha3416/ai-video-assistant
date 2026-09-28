"""Tests for utils/flashcards.py against a throwaway in-memory SQLite DB.

Your real data/app.db is never touched. Needs the Flashcard model, i.e. run
``python apply_step_flashcards.py`` first.
"""

from contextlib import contextmanager
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def fc(monkeypatch):
    from db import models
    from utils import flashcards

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def fake_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(flashcards, "get_db", fake_get_db)

    with fake_get_db() as db:
        db.add(models.User(email="ayesha@example.com", display_name="Ayesha"))
        db.add(models.User(email="other@example.com", display_name="Other"))
        db.commit()

    return flashcards


def test_flashcards_table_registered():
    from db import models

    assert "flashcards" in models.Base.metadata.tables


def test_add_cards_are_due_immediately(fc):
    outcome = fc.add_cards("ayesha@example.com", [{"front": "Q1", "back": "A1"}], video_title="Vid")
    assert outcome == {"added": 1, "skipped": 0}
    due = fc.get_due_cards("ayesha@example.com")
    assert len(due) == 1 and due[0]["front"] == "Q1" and due[0]["stage"] == 0


def test_add_cards_skips_duplicates_within_and_across_calls(fc):
    fc.add_cards("ayesha@example.com", [{"front": "What is RAG?", "back": "A"}])
    out = fc.add_cards(
        "ayesha@example.com",
        [{"front": "what is rag?", "back": "B (dup)"}, {"front": "New one", "back": "C"}],
    )
    assert out == {"added": 1, "skipped": 1}
    assert fc.get_card_counts("ayesha@example.com")["total"] == 2


def test_add_cards_skips_empty_front_or_back(fc):
    out = fc.add_cards(
        "ayesha@example.com",
        [{"front": "", "back": "x"}, {"front": "x", "back": ""}, {"front": "ok", "back": "ok"}],
    )
    assert out == {"added": 1, "skipped": 2}


def test_add_cards_unknown_user(fc):
    out = fc.add_cards("nobody@example.com", [{"front": "Q", "back": "A"}])
    assert out == {"added": 0, "skipped": 1}


def test_users_only_see_their_own_cards(fc):
    fc.add_cards("ayesha@example.com", [{"front": "Q1", "back": "A1"}])
    fc.add_cards("other@example.com", [{"front": "Q2", "back": "A2"}, {"front": "Q3", "back": "A3"}])
    assert fc.get_card_counts("ayesha@example.com")["total"] == 1
    assert fc.get_card_counts("other@example.com")["total"] == 2
    assert len(fc.list_cards("ayesha@example.com")) == 1


def test_review_card_correct_advances_stage_and_reschedules(fc):
    fc.add_cards("ayesha@example.com", [{"front": "Q", "back": "A"}])
    card_id = fc.list_cards("ayesha@example.com")[0]["id"]
    today = date(2026, 9, 24)

    updated = fc.review_card("ayesha@example.com", card_id, correct=True, today=today)
    assert updated["stage"] == 1
    assert updated["due_date"] == (today + timedelta(days=1)).isoformat()
    assert updated["times_correct"] == 1


def test_review_card_wrong_resets_stage(fc):
    fc.add_cards("ayesha@example.com", [{"front": "Q", "back": "A"}])
    card_id = fc.list_cards("ayesha@example.com")[0]["id"]
    today = date(2026, 9, 24)

    fc.review_card("ayesha@example.com", card_id, correct=True, today=today)   # stage 1
    fc.review_card("ayesha@example.com", card_id, correct=True, today=today)   # stage 2
    updated = fc.review_card("ayesha@example.com", card_id, correct=False, today=today)  # miss
    assert updated["stage"] == 0
    assert updated["due_date"] == (today + timedelta(days=1)).isoformat()
    assert updated["times_wrong"] == 1
    assert updated["times_correct"] == 2


def test_review_card_wrong_user_or_id_returns_none(fc):
    fc.add_cards("ayesha@example.com", [{"front": "Q", "back": "A"}])
    card_id = fc.list_cards("ayesha@example.com")[0]["id"]
    assert fc.review_card("other@example.com", card_id, correct=True) is None
    assert fc.review_card("ayesha@example.com", 9999, correct=True) is None


def test_due_cards_excludes_future_scheduled_cards(fc):
    fc.add_cards("ayesha@example.com", [{"front": "Q1", "back": "A1"}, {"front": "Q2", "back": "A2"}])
    cards = fc.list_cards("ayesha@example.com")
    fc.review_card("ayesha@example.com", cards[0]["id"], correct=True, today=date.today())  # now due in 1 day

    due = fc.get_due_cards("ayesha@example.com")
    assert len(due) == 1
    assert due[0]["id"] == cards[1]["id"]  # the untouched card is still due today


def test_get_next_due_date(fc):
    fc.add_cards("ayesha@example.com", [{"front": "Q", "back": "A"}])
    card_id = fc.list_cards("ayesha@example.com")[0]["id"]
    # get_next_due_date compares against the real wall clock (datetime.now()), so
    # "today" here must be far enough in the future that due_at is unambiguously
    # ahead of now, regardless of when this test happens to run.
    today = date.today() + timedelta(days=365)
    fc.review_card("ayesha@example.com", card_id, correct=True, today=today)
    assert fc.get_next_due_date("ayesha@example.com") == today + timedelta(days=1)


def test_get_next_due_date_none_when_everything_is_due_now(fc):
    fc.add_cards("ayesha@example.com", [{"front": "Q", "back": "A"}])
    assert fc.get_next_due_date("ayesha@example.com") is None


def test_card_counts_learning_vs_mastered(fc):
    fc.add_cards("ayesha@example.com", [{"front": "Q1", "back": "A1"}, {"front": "Q2", "back": "A2"}])
    ids = [c["id"] for c in fc.list_cards("ayesha@example.com")]
    today = date(2026, 9, 24)
    for _ in range(4):
        fc.review_card("ayesha@example.com", ids[0], correct=True, today=today)
        today += timedelta(days=20)  # always due by the time we review again

    counts = fc.get_card_counts("ayesha@example.com")
    assert counts["total"] == 2
    assert counts["mastered"] == 1
    assert counts["learning"] == 1


def test_delete_card(fc):
    fc.add_cards("ayesha@example.com", [{"front": "Q", "back": "A"}])
    card_id = fc.list_cards("ayesha@example.com")[0]["id"]
    assert fc.delete_card("other@example.com", card_id) is False  # not their card
    assert fc.get_card("ayesha@example.com", card_id) is not None
    assert fc.delete_card("ayesha@example.com", card_id) is True
    assert fc.get_card("ayesha@example.com", card_id) is None


def test_source_and_session_id_are_stored(fc):
    fc.add_cards(
        "ayesha@example.com",
        [{"front": "Q", "back": "A"}],
        video_title="My video",
        session_id="sess-123",
        source="quiz",
    )
    card = fc.list_cards("ayesha@example.com")[0]
    assert card["video_title"] == "My video"
    assert card["source"] == "quiz"
