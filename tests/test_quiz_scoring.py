"""Tests for core/quiz_scoring.py -- pure logic, no DB."""

from core.quiz_scoring import (
    TREND_COLUMNS,
    percent,
    score_answers,
    summarize_attempts,
    trend_dataframe,
)

QUESTIONS = [
    {"question": "q1", "options": ["a", "b", "c", "d"], "correct_index": 0},
    {"question": "q2", "options": ["a", "b", "c", "d"], "correct_index": 2},
    {"question": "q3", "options": ["a", "b", "c", "d"], "correct_index": 3},
]


def attempt(pct, title="Video", ts="2026-09-24 10:00", score=1, n=2):
    return {"percent": pct, "video_title": title, "timestamp": ts, "score": score, "num_questions": n}


def test_score_all_correct():
    assert score_answers(QUESTIONS, [0, 2, 3]) == 3


def test_score_some_wrong_and_skipped():
    assert score_answers(QUESTIONS, [0, 1, None]) == 1


def test_score_index_zero_is_a_real_answer_not_a_skip():
    assert score_answers(QUESTIONS[:1], [0]) == 1


def test_score_tolerates_short_and_long_answer_lists():
    assert score_answers(QUESTIONS, [0]) == 1
    assert score_answers(QUESTIONS, [0, 2, 3, 1, 1, 1]) == 3
    assert score_answers(QUESTIONS, []) == 0
    assert score_answers([], [0, 1]) == 0


def test_percent():
    assert percent(8, 10) == 80.0
    assert percent(1, 3) == 33.3
    assert percent(0, 5) == 0.0
    assert percent(5, 0) == 0.0
    assert percent(3, -1) == 0.0


def test_summary_empty():
    s = summarize_attempts([])
    assert s == {"attempts": 0, "average_percent": 0.0, "best_percent": 0.0, "latest_percent": 0.0}


def test_summary_uses_newest_first_for_latest():
    newest_first = [attempt(90.0), attempt(50.0), attempt(70.0)]
    s = summarize_attempts(newest_first)
    assert s["attempts"] == 3
    assert s["latest_percent"] == 90.0
    assert s["best_percent"] == 90.0
    assert s["average_percent"] == 70.0


def test_trend_is_chronological_and_numbered():
    newest_first = [
        attempt(90.0, "C", "2026-09-24 12:00"),
        attempt(50.0, "B", "2026-09-23 12:00"),
        attempt(70.0, "A", "2026-09-22 12:00"),
    ]
    df = trend_dataframe(newest_first)
    assert list(df.columns) == TREND_COLUMNS
    assert list(df["attempt"]) == [1, 2, 3]
    assert list(df["percent"]) == [70.0, 50.0, 90.0]
    assert list(df["video"]) == ["A", "B", "C"]


def test_trend_empty_has_expected_columns():
    df = trend_dataframe([])
    assert df.empty
    assert list(df.columns) == TREND_COLUMNS


def test_trend_blank_title_gets_placeholder():
    df = trend_dataframe([attempt(10.0, title="")])
    assert df.loc[0, "video"] == "Untitled video"
