"""Flashcards page (Step 3): Review / Create cards / My cards.

Also exposes two small hooks used by the rest of the app:

* ``nav_label(email)``               -> sidebar label, e.g. "Flashcards (3)" when 3 are due
* ``render_quiz_mistakes_button``    -> "Add missed questions to flashcards" under a quiz score

All scheduling rules live in ``core/spaced_repetition.py`` and the sitting's
queue logic in ``core/review_session.py``; this module is just the screen.
"""

from __future__ import annotations

import streamlit as st

from core import review_session as rs
from core.flashcard_utils import cards_from_quiz_mistakes
from utils.flashcards import (
    add_cards,
    delete_card,
    get_card,
    get_card_counts,
    get_due_cards,
    get_due_count,
    get_next_due_date,
    list_cards,
    review_card,
)

SESSION_KEY = "fc_session"  # the active review sitting (a dict, see core/review_session.py)
FLASH_KEY = "fc_flash"      # one-shot message shown at the top after a rerun
SESSION_LIMIT = 20          # cards per sitting

_SOURCE_LABELS = {"video": "from a video", "quiz": "from a quiz mistake", "manual": "added manually"}


# --------------------------------------------------------------- small hooks ---
def nav_label(email: str) -> str:
    """Sidebar label; never raises (a DB hiccup must not break the sidebar)."""
    try:
        due = get_due_count(email)
    except Exception:  # noqa: BLE001
        return "Flashcards"
    return f"Flashcards ({due})" if due else "Flashcards"


def _added_message(outcome: dict) -> str:
    n = outcome["added"]
    msg = f"Added {n} new card{'s' if n != 1 else ''}"
    if outcome["skipped"]:
        msg += f" ({outcome['skipped']} already in your deck)"
    return msg + "."


def render_quiz_mistakes_button(
    email: str,
    quiz_id: str,
    questions: list,
    answers: list,
    session_id: str | None,
    video_title: str,
) -> None:
    """Under a submitted quiz's score: turn wrong/skipped questions into flashcards."""
    missed = cards_from_quiz_mistakes(questions, answers)
    if not missed:
        return

    done_key = f"fc_quiz_added_{quiz_id}"
    done = st.session_state.get(done_key)
    if done is not None:
        st.caption(f"🃏 {_added_message(done)} Review them under Flashcards in the sidebar.")
        return

    label = f"🃏 Add {len(missed)} missed question{'s' if len(missed) != 1 else ''} to flashcards"
    if st.button(label, key=f"fc_quiz_btn_{quiz_id}"):
        try:
            outcome = add_cards(
                email, missed, video_title=video_title, session_id=session_id, source="quiz"
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Couldn't save the flashcards: {exc}")
            return
        st.session_state[done_key] = outcome
        st.rerun()


# ------------------------------------------------------------------- the page ---
def render_flashcards_page(email: str) -> None:
    st.subheader("🃏 Flashcards")

    flash = st.session_state.pop(FLASH_KEY, None)
    if flash:
        st.success(flash)

    counts = get_card_counts(email)
    cards = [
        ("⏰", counts["due"], "Due now"),
        ("🃏", counts["total"], "Total cards"),
        ("📖", counts["learning"], "Learning"),
        ("🏆", counts["mastered"], "Mastered"),
    ]
    for col, (icon, value, label) in zip(st.columns(4), cards):
        with col:
            st.markdown(
                '<div class="stat-card">'
                f'<div class="stat-card-icon">{icon}</div>'
                f'<div class="stat-card-value">{value}</div>'
                f'<div class="stat-card-label">{label}</div>'
                "</div>",
                unsafe_allow_html=True,
            )
    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

    tab_review, tab_create, tab_cards = st.tabs(["Review", "Create cards", "My cards"])
    with tab_review:
        _review_tab(email)
    with tab_create:
        _create_tab(email)
    with tab_cards:
        _cards_tab(email)


# ----------------------------------------------------------------- Review tab ---
def _review_tab(email: str) -> None:
    session = st.session_state.get(SESSION_KEY)

    # --- no sitting in progress: offer to start one ---
    if session is None:
        due = get_due_cards(email, limit=SESSION_LIMIT)
        if not due:
            if get_card_counts(email)["total"] == 0:
                st.info(
                    "You don't have any flashcards yet. Use the **Create cards** tab to make "
                    "some from a video, or add the questions you missed in a quiz."
                )
            else:
                nxt = get_next_due_date(email)
                msg = "🎉 You're all caught up — nothing is due right now."
                if nxt:
                    msg += f" Next review: {nxt:%A, %d %b}."
                st.success(msg)
            return

        st.markdown(f"**{len(due)} card{'s' if len(due) != 1 else ''} due.** A sitting takes a few minutes.")
        if st.button("Start review", type="primary", key="fc_start"):
            st.session_state[SESSION_KEY] = rs.new_session([c["id"] for c in due])
            st.rerun()
        return

    # --- sitting finished ---
    if rs.is_finished(session):
        st.success(
            f"Sitting complete — {session['got']} recalled, {session['missed']} missed. "
            "Missed cards come back tomorrow; the rest return at longer and longer intervals."
        )
        if st.button("Finish", type="primary", key="fc_finish"):
            st.session_state.pop(SESSION_KEY, None)
            st.rerun()
        return

    # --- a card is up ---
    card = get_card(email, rs.current_id(session))
    if card is None:  # deleted meanwhile (or belongs to someone else): skip it
        rs.drop_current(session)
        st.rerun()
        return

    reviewed = rs.reviewed_count(session)
    st.progress(min(1.0, reviewed / max(session["total"], 1)))
    st.caption(f"{reviewed} of {session['total']} reviewed · {len(session['queue'])} left in this sitting")

    with st.container(border=True):
        st.caption(f"From: {card['video_title'] or 'your cards'}")
        st.markdown("#### " + " ".join(card["front"].split()))
        if session["show_back"]:
            st.divider()
            st.markdown(card["back"])

    cid = card["id"]
    if not session["show_back"]:
        if st.button("Show answer", type="primary", use_container_width=True, key=f"fc_show_{cid}"):
            session["show_back"] = True
            st.rerun()
    else:
        left, right = st.columns(2)
        with left:
            missed_clicked = st.button("❌ Missed it", use_container_width=True, key=f"fc_miss_{cid}")
        with right:
            got_clicked = st.button("✅ Got it", type="primary", use_container_width=True, key=f"fc_got_{cid}")
        if missed_clicked or got_clicked:
            card_id, first_try = rs.answer(session, correct=got_clicked)
            if first_try:  # retries within the same sitting are practice only
                review_card(email, card_id, got_clicked)
            st.rerun()

    if st.button("End sitting", key="fc_end"):
        st.session_state.pop(SESSION_KEY, None)
        st.rerun()


# ------------------------------------------------------------ Create cards tab ---
def _create_tab(email: str) -> None:
    result = st.session_state.get("result")
    content = (result or {}).get("transcript") or (result or {}).get("summary") or ""

    st.markdown("**From a video**")
    if not content:
        st.info(
            "Analyze a video in Chat (or open one from Recent) and come back here to "
            "generate cards from it."
        )
    else:
        st.caption(f"Current video: {result.get('title', 'Untitled video')}")
        count = st.select_slider("How many cards?", options=[5, 10, 15, 20], value=10, key="fc_gen_n")
        if st.button("✨ Generate flashcards", type="primary", key="fc_gen_btn"):
            try:
                from core.flashcard_generator import generate_flashcards

                with st.spinner("Writing flashcards from the whole video..."):
                    cards = generate_flashcards(content, count)
                    outcome = add_cards(
                        email,
                        cards,
                        video_title=result.get("title", ""),
                        session_id=st.session_state.get("current_session_id"),
                        source="video",
                    )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Couldn't generate flashcards: {exc}")
            else:
                st.session_state[FLASH_KEY] = _added_message(outcome) + " Start a sitting in the Review tab."
                st.rerun()

    st.markdown("**From a quiz**")
    st.caption(
        "In Chat, type `quiz`, submit your answers, then press "
        "**Add missed questions to flashcards** under your score."
    )

    with st.expander("Add a card manually"):
        with st.form("fc_manual_form", clear_on_submit=True):
            front = st.text_area("Question (front)", height=80)
            back = st.text_area("Answer (back)", height=80)
            submitted = st.form_submit_button("Add card")
        if submitted:
            if front.strip() and back.strip():
                outcome = add_cards(email, [{"front": front, "back": back}], source="manual")
                st.session_state[FLASH_KEY] = _added_message(outcome)
                st.rerun()
            else:
                st.warning("Please fill in both the question and the answer.")


# --------------------------------------------------------------- My cards tab ---
def _cards_tab(email: str) -> None:
    cards = list_cards(email, limit=30)
    if not cards:
        st.info("No cards yet.")
        return

    total = get_card_counts(email)["total"]
    st.caption(f"Showing your {len(cards)} newest of {total} cards.")

    for card in cards:
        label = " ".join(card["front"].split())
        label = label[:80] + ("…" if len(label) > 80 else "")
        with st.expander(label):
            st.markdown(card["back"])
            st.caption(
                f"Stage {card['stage']} of 4 · next review {card['due_date']} · "
                f"recalled {card['times_correct']}× · missed {card['times_wrong']}× · "
                f"{_SOURCE_LABELS.get(card['source'], card['source'])}"
                + (f" · {card['video_title']}" if card["video_title"] else "")
            )
            if st.button("🗑️ Delete card", key=f"fc_del_{card['id']}"):
                delete_card(email, card["id"])
                st.rerun()
