"""Pure helpers for flashcards (Step 3). No LLM, DB or Streamlit imports."""

from __future__ import annotations

import hashlib
import json
import re

MAX_FRONT_CHARS = 400
MAX_BACK_CHARS = 800


# ---------------------------------------------------------------- identity ---
def card_key(front: str) -> str:
    """Stable 40-char key for de-duplication: same question text -> same key.

    Case and whitespace differences don't matter ("What is RAG?" == "  what is  rag? ").
    """
    normalized = re.sub(r"\s+", " ", (front or "").strip().lower())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def dedupe_cards(cards: list[dict]) -> list[dict]:
    """Drop cards whose front repeats an earlier one (keeps first occurrence)."""
    seen: set[str] = set()
    out = []
    for card in cards:
        key = card_key(card["front"])
        if key in seen:
            continue
        seen.add(key)
        out.append(card)
    return out


# ----------------------------------------------------------- LLM output -----
_FENCE_START = re.compile(r"^```(?:json)?", re.IGNORECASE)
_FENCE_END = re.compile(r"```$")


def parse_cards(raw: str) -> list[dict]:
    """Parse the model's reply into ``[{"front": str, "back": str}, ...]``.

    Tolerates ```json fences, and a wrapper object like ``{"flashcards": [...]}``.
    Items missing a non-empty front or back are dropped. Raises ``ValueError``
    if the reply isn't JSON or doesn't contain a list of cards at all.
    """
    text = (raw or "").strip()
    text = _FENCE_START.sub("", text).strip()
    text = _FENCE_END.sub("", text).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse the flashcards response as JSON: {exc}") from exc

    if isinstance(data, dict):
        for key in ("flashcards", "cards", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break

    if not isinstance(data, list):
        raise ValueError("The flashcards response was not a list of cards.")

    cards = []
    for item in data:
        if not isinstance(item, dict):
            continue
        front, back = item.get("front"), item.get("back")
        if not isinstance(front, str) or not isinstance(back, str):
            continue
        front, back = front.strip(), back.strip()
        if front and back:
            cards.append({"front": front[:MAX_FRONT_CHARS], "back": back[:MAX_BACK_CHARS]})
    return cards


# ------------------------------------------------- covering the whole video --
def chunk_text(text: str, size: int = 3500) -> list[str]:
    """Split ``text`` into pieces of about ``size`` chars, cutting at whitespace."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind(" ", start + int(size * 0.8), end)
            if cut > start:
                end = cut
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        start = end
    return chunks


def select_chunks(text: str, max_chunks: int = 4, size: int = 3500) -> list[str]:
    """Up to ``max_chunks`` pieces spread EVENLY across the whole text.

    Unlike "just take the first N characters", a long video is sampled from
    start to end, so cards cover the whole thing.
    """
    chunks = chunk_text(text, size)
    if len(chunks) <= max_chunks:
        return chunks
    if max_chunks <= 1:
        return chunks[:1]
    last = len(chunks) - 1
    indexes = [round(i * last / (max_chunks - 1)) for i in range(max_chunks)]
    return [chunks[i] for i in sorted(set(indexes))]


def interleave(lists: list[list]) -> list:
    """Round-robin merge: [[a1,a2],[b1,b2,b3]] -> [a1,b1,a2,b2,b3]."""
    out = []
    longest = max((len(x) for x in lists), default=0)
    for i in range(longest):
        for items in lists:
            if i < len(items):
                out.append(items[i])
    return out


# ------------------------------------------------------- from quiz answers ---
def cards_from_quiz_mistakes(questions: list, answers: list) -> list[dict]:
    """One card per question the user got wrong or skipped.

    front = the question, back = the correct option's text.
    """
    cards = []
    for i, q in enumerate(questions or []):
        if not isinstance(q, dict):
            continue
        options = q.get("options")
        correct = q.get("correct_index")
        question = q.get("question")
        if (
            not isinstance(question, str)
            or not isinstance(options, list)
            or not isinstance(correct, int)
            or not 0 <= correct < len(options)
        ):
            continue

        picked = answers[i] if answers and i < len(answers) else None
        if picked == correct:
            continue

        front = question.strip()[:MAX_FRONT_CHARS]
        back = str(options[correct]).strip()[:MAX_BACK_CHARS]
        if front and back:
            cards.append({"front": front, "back": back})
    return cards
