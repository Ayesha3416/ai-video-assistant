"""Tests for utils/quiz_attempts.py against a throwaway in-memory SQLite DB.

Your real data/app.db is never touched: the fixture swaps ``get_db`` inside
``utils.quiz_attempts`` for one bound to an in-memory engine.

These need the QuizAttempt model, i.e. run ``python apply_step_quiz.py`` first.
"""

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

QUESTIONS = [
    {"question": "q1", "options": ["a", "b", "c", "d"], "correct_index": 0},
    {"question": "q2", "options": ["a", "b", "c", "d"], "correct_index": 2},
    {"question": "q3", "options": ["a", "b", "c", "d"], "correct_index": 3},
    {"question": "q4", "options": ["a", "b", "c", "d"], "correct_index": 1},
]


@pytest.fixture()
def qa(monkeypatch):
    from db import models
    from utils import quiz_attempts

    # StaticPool: every connection shares the one in-memory database.
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

    monkeypatch.setattr(quiz_attempts, "get_db", fake_get_db)

    with fake_get_db() as db:
        db.add(models.User(email="ayesha@example.com", display_name="Ayesha"))
        db.add(models.User(email="other@example.com", display_name="Other"))
        db.commit()

    return quiz_attempts


def _save(qa, email="ayesha@example.com", answers=(0, 2, 3, 1), title="Intro to RAG", quiz_id="q-1"):
    return qa.save_attempt(email, "session-1", title, quiz_id, QUESTIONS, list(answers))


def test_quiz_attempts_table_is_registered_on_the_models():
    from db import models

    assert "quiz_attempts" in models.Base.metadata.tables


def test_save_returns_scored_attempt(qa):
    saved = _save(qa, answers=(0, 2, 0, None))  # 2 right, 1 wrong, 1 skipped
    assert saved is not None
    assert saved["score"] == 2
    assert saved["num_questions"] == 4
    assert saved["percent"] == 50.0
    assert saved["video_title"] == "Intro to RAG"
    assert saved["session_id"] == "session-1"


def test_saved_attempt_keeps_questions_and_answers(qa):
    from db import models

    _save(qa, answers=(0, 1, None, 1))
    with qa.get_db() as db:
        row = db.query(models.QuizAttempt).one()
        assert row.questions == QUESTIONS
        assert row.answers == [0, 1, None, 1]


def test_get_attempts_newest_first(qa):
    _save(qa, answers=(0, 0, 0, 0), title="first", quiz_id="a")
    _save(qa, answers=(0, 2, 3, 1), title="second", quiz_id="b")
    attempts = qa.get_attempts("ayesha@example.com")
    assert [a["video_title"] for a in attempts] == ["second", "first"]


def test_get_attempts_respects_limit(qa):
    for n in range(5):
        _save(qa, quiz_id=f"q{n}")
    assert len(qa.get_attempts("ayesha@example.com", limit=3)) == 3
    assert len(qa.get_attempts("ayesha@example.com", limit=None)) == 5


def test_users_only_see_their_own_attempts(qa):
    _save(qa, email="ayesha@example.com")
    _save(qa, email="other@example.com")
    _save(qa, email="other@example.com")
    assert len(qa.get_attempts("ayesha@example.com")) == 1
    assert len(qa.get_attempts("other@example.com")) == 2


def test_unknown_user_is_not_saved_and_reads_empty(qa):
    assert _save(qa, email="nobody@example.com") is None
    assert qa.get_attempts("nobody@example.com") == []
    assert qa.get_quiz_summary("nobody@example.com")["attempts"] == 0


def test_save_never_raises_on_garbage(qa):
    assert qa.save_attempt("ayesha@example.com", "s", "t", "q", None, None) is None


def test_retaking_the_same_quiz_creates_a_second_attempt(qa):
    _save(qa, answers=(0, 0, 0, 0), quiz_id="same")
    _save(qa, answers=(0, 2, 3, 1), quiz_id="same")
    attempts = qa.get_attempts("ayesha@example.com")
    assert [a["percent"] for a in attempts] == [100.0, 25.0]


def test_summary_and_trend(qa):
    _save(qa, answers=(0, 0, 0, 0), title="A", quiz_id="1")  # 1/4 = 25%
    _save(qa, answers=(0, 2, 0, 0), title="B", quiz_id="2")  # 2/4 = 50%
    _save(qa, answers=(0, 2, 3, 1), title="C", quiz_id="3")  # 4/4 = 100%

    summary = qa.get_quiz_summary("ayesha@example.com")
    assert summary["attempts"] == 3
    assert summary["latest_percent"] == 100.0
    assert summary["best_percent"] == 100.0
    assert summary["average_percent"] == 58.3

    trend = qa.get_score_trend_dataframe("ayesha@example.com")
    assert list(trend["video"]) == ["A", "B", "C"]
    assert list(trend["percent"]) == [25.0, 50.0, 100.0]
    assert list(trend["attempt"]) == [1, 2, 3]
