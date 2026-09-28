"""Tests for core/review_session.py -- pure queue logic, no DB/UI."""

from core.review_session import (
    answer,
    current_id,
    drop_current,
    is_finished,
    new_session,
    reviewed_count,
)


def test_new_session_shape():
    s = new_session([1, 2, 3])
    assert s["queue"] == [1, 2, 3]
    assert s["total"] == 3
    assert current_id(s) == 1
    assert not is_finished(s)


def test_empty_session_is_finished_immediately():
    s = new_session([])
    assert is_finished(s)
    assert current_id(s) is None


def test_correct_answer_removes_card_and_counts_as_got():
    s = new_session([1, 2])
    card_id, first_try = answer(s, correct=True)
    assert card_id == 1 and first_try is True
    assert s["got"] == 1 and s["missed"] == 0
    assert s["queue"] == [2]


def test_missed_answer_goes_to_back_of_queue():
    s = new_session([1, 2])
    card_id, first_try = answer(s, correct=False)
    assert card_id == 1 and first_try is True
    assert s["missed"] == 1
    assert s["queue"] == [2, 1]


def test_retry_after_a_miss_is_not_first_try_and_does_not_double_count():
    s = new_session([1])
    answer(s, correct=False)          # miss #1: counted, goes to back -> queue [1]
    card_id, first_try = answer(s, correct=True)  # retry
    assert card_id == 1
    assert first_try is False         # caller must NOT update the DB schedule again
    assert s["got"] == 0 and s["missed"] == 1  # unchanged by the retry
    assert is_finished(s)


def test_repeated_misses_keep_the_card_in_the_queue_until_a_correct_retry():
    s = new_session([1, 2])
    answer(s, correct=False)  # 1 -> back: [2, 1]
    answer(s, correct=True)   # 2 done:    [1]
    answer(s, correct=False)  # 1 -> back: [1]  (still not first try)
    assert s["missed"] == 1 and s["got"] == 1  # only the very first try on card 1 counted
    card_id, first_try = answer(s, correct=True)
    assert card_id == 1 and first_try is False
    assert is_finished(s)


def test_reviewed_count_is_distinct_cards_not_total_answers():
    s = new_session([1, 2])
    answer(s, correct=False)  # card 1 missed once
    answer(s, correct=True)   # card 2 got it
    assert reviewed_count(s) == 2  # not 2 answers-so-far vs cards -- but here they match
    answer(s, correct=True)   # retry on card 1
    assert reviewed_count(s) == 2  # still 2 distinct cards, despite 3 total answers


def test_show_back_resets_after_each_answer():
    s = new_session([1, 2])
    s["show_back"] = True
    answer(s, correct=True)
    assert s["show_back"] is False


def test_drop_current_removes_without_scoring():
    s = new_session([1, 2, 3])
    drop_current(s)
    assert s["queue"] == [2, 3]
    assert s["total"] == 2
    assert s["got"] == 0 and s["missed"] == 0


def test_drop_current_on_empty_session_is_a_no_op():
    s = new_session([])
    drop_current(s)
    assert s["queue"] == [] and s["total"] == 0
