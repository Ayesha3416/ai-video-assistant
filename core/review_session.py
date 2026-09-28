"""State machine for one flashcard review sitting (Step 3).

Pure Python, no Streamlit: the UI keeps this dict in ``st.session_state`` and
calls these functions. Keeping the rules here makes them unit-testable.

Rules:
* The sitting starts with the cards that are due.
* A card answered "Got it" on its first try is done for this sitting.
* A card answered "Missed it" goes to the back of the queue so you see it again
  before finishing -- but only the FIRST answer counts for the schedule
  (``first_try`` in the return value of ``answer``); later tries are practice.
"""

from __future__ import annotations


def new_session(card_ids: list[int]) -> dict:
    return {
        "queue": list(card_ids),
        "total": len(card_ids),
        "got": 0,
        "missed": 0,
        "practice": [],  # ids that were missed once already (retries are practice only)
        "show_back": False,
    }


def current_id(session: dict) -> int | None:
    return session["queue"][0] if session["queue"] else None


def is_finished(session: dict) -> bool:
    return not session["queue"]


def reviewed_count(session: dict) -> int:
    """Distinct cards answered at least once this sitting."""
    return session["got"] + session["missed"]


def answer(session: dict, correct: bool) -> tuple[int, bool]:
    """Apply an answer to the card at the front of the queue.

    Returns ``(card_id, first_try)``. Only when ``first_try`` is True should the
    caller update the card's schedule in the database.
    """
    card_id = session["queue"].pop(0)
    first_try = card_id not in session["practice"]

    if first_try:
        if correct:
            session["got"] += 1
        else:
            session["missed"] += 1
            session["practice"].append(card_id)

    if not correct:
        session["queue"].append(card_id)  # see it again before the sitting ends

    session["show_back"] = False
    return card_id, first_try


def drop_current(session: dict) -> None:
    """Skip the front card without answering (e.g. it was deleted meanwhile)."""
    if session["queue"]:
        session["queue"].pop(0)
        if session["total"] > 0:
            session["total"] -= 1
    session["show_back"] = False
