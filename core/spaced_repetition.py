"""Spaced-repetition scheduling (Step 3, locked decision D-07).

Plain Python -- the LLM never does date math. A Leitner-style ladder:

    stage = number of consecutive successful reviews (0 = new, or just missed)

    review result   new stage        next review
    -------------   -----------      -----------
    Got it (0->1)   1                +1 day
    Got it (1->2)   2                +3 days
    Got it (2->3)   3                +7 days
    Got it (3->4)   4  (mastered)    +14 days
    Got it (4->4)   4                +14 days   (keeps repeating every 14 days)
    Missed it       0                +1 day     (back to the start)

To move to SM-2 later, only ``next_review`` needs to change -- everything else
(DB, UI, tests) talks to it through that one function.
"""

from __future__ import annotations

from datetime import date, timedelta

#: Days until the next review after reaching stage 1, 2, 3, 4+.
INTERVALS_DAYS = (1, 3, 7, 14)

#: A card at this stage has been recalled correctly 4 times in a row.
MASTERED_STAGE = len(INTERVALS_DAYS)

#: A missed card comes back after this many days.
MISSED_RETRY_DAYS = 1


def interval_for_stage(stage: int) -> int:
    """Days to wait once a card has reached ``stage`` (clamped to the ladder)."""
    stage = max(1, min(stage, len(INTERVALS_DAYS)))
    return INTERVALS_DAYS[stage - 1]


def next_review(stage: int, correct: bool, today: date) -> tuple[int, date]:
    """Return ``(new_stage, next_due_date)`` after one review."""
    if not correct:
        return 0, today + timedelta(days=MISSED_RETRY_DAYS)

    new_stage = min(max(stage, 0) + 1, MASTERED_STAGE)
    return new_stage, today + timedelta(days=interval_for_stage(new_stage))


def is_mastered(stage: int) -> bool:
    return stage >= MASTERED_STAGE
