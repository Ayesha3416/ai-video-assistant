"""Tests for core/spaced_repetition.py (decision D-07: 1/3/7/14-day ladder)."""

from datetime import date, timedelta

from core.spaced_repetition import (
    MASTERED_STAGE,
    interval_for_stage,
    is_mastered,
    next_review,
)

TODAY = date(2026, 9, 24)


def test_interval_ladder():
    assert interval_for_stage(1) == 1
    assert interval_for_stage(2) == 3
    assert interval_for_stage(3) == 7
    assert interval_for_stage(4) == 14


def test_interval_clamped_beyond_ladder():
    assert interval_for_stage(4) == interval_for_stage(9)


def test_new_card_first_success_is_one_day():
    stage, due = next_review(stage=0, correct=True, today=TODAY)
    assert stage == 1
    assert due == TODAY + timedelta(days=1)


def test_full_progression_through_the_ladder():
    stage, current = 0, TODAY
    expected_gaps = [1, 3, 7, 14]
    for gap in expected_gaps:
        stage, next_due = next_review(stage, True, current)
        assert next_due == current + timedelta(days=gap)
        current = next_due
    assert stage == MASTERED_STAGE


def test_mastered_card_repeats_every_14_days():
    stage, due = next_review(MASTERED_STAGE, True, TODAY)
    assert stage == MASTERED_STAGE
    assert due == TODAY + timedelta(days=14)


def test_missed_card_resets_to_stage_zero_and_comes_back_tomorrow():
    stage, due = next_review(stage=3, correct=False, today=TODAY)
    assert stage == 0
    assert due == TODAY + timedelta(days=1)


def test_missed_from_mastered_also_resets():
    stage, due = next_review(stage=MASTERED_STAGE, correct=False, today=TODAY)
    assert stage == 0
    assert due == TODAY + timedelta(days=1)


def test_is_mastered():
    assert not is_mastered(0)
    assert not is_mastered(3)
    assert is_mastered(4)
    assert is_mastered(5)


def test_negative_stage_is_treated_as_new():
    stage, due = next_review(stage=-1, correct=True, today=TODAY)
    assert stage == 1
    assert due == TODAY + timedelta(days=1)
