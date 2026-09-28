"""Generate flashcards from a video transcript (Step 3).

Same building blocks as ``core/quiz_generator.py`` (Groq via ``core.llm``, JSON
reply, tolerant parsing) with one important difference: the quiz reads only the
first ~6000 characters of a transcript, so on a long video it only covers the
opening. Here the transcript is sampled in evenly spaced chunks across the WHOLE
video and the cards are interleaved, so they cover it end to end.
"""

from __future__ import annotations

import math
import time

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config import get_logger
from core.flashcard_utils import dedupe_cards, interleave, parse_cards, select_chunks
from core.llm import get_llm, invoke_with_retry

log = get_logger(__name__)

#: At most this many LLM calls per generation (keeps latency and rate limits sane).
MAX_CHUNKS = 4
CHUNK_CHARS = 3500

FLASHCARD_SYSTEM_PROMPT = """You are an expert study-flashcard writer. From the video transcript
excerpt given, write exactly {n} flashcards that help a student remember its key ideas.

Respond with ONLY a valid JSON array (no markdown fences, no extra text) where each item has this exact shape:
{{
  "front": "a clear question or prompt with ONE specific answer",
  "back": "the concise answer, 1-2 sentences"
}}

Rules:
- Each card tests exactly one idea; do not combine several facts in one card.
- The front must make sense on its own, without the video (no "in this video", no "the speaker").
- Prefer "why", "how" and "what is" questions over yes/no questions.
- Use only facts stated in the excerpt; do not invent anything.
- Do not repeat the same question twice.
- If the excerpt has nothing worth remembering, return an empty array [].
- Output ONLY the JSON array, nothing else."""


def _ask_llm(chunk: str, n: int) -> str:
    """One LLM call for one transcript chunk. Isolated so tests can replace it."""
    llm = get_llm(temperature=0.4)
    prompt = ChatPromptTemplate.from_messages(
        [("system", FLASHCARD_SYSTEM_PROMPT), ("human", "{text}")]
    )
    chain = prompt | llm | StrOutputParser()
    return invoke_with_retry(chain, {"text": chunk, "n": n})


def generate_flashcards(content: str, num_cards: int = 10) -> list[dict]:
    """Return up to ``num_cards`` cards as ``[{"front": str, "back": str}, ...]``.

    Raises ``ValueError`` if there is no content or no usable card could be made.
    """
    chunks = select_chunks(content, max_chunks=MAX_CHUNKS, size=CHUNK_CHARS)
    if not chunks:
        raise ValueError("There is no transcript or summary to make flashcards from.")

    per_chunk = math.ceil(num_cards / len(chunks))
    per_chunk_cards: list[list[dict]] = []
    failures = 0

    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(0.8)  # light pacing between calls, same as the other generators
        try:
            per_chunk_cards.append(parse_cards(_ask_llm(chunk, per_chunk)))
        except ValueError as exc:
            failures += 1
            log.warning("Flashcards: skipping chunk %d/%d (%s)", i + 1, len(chunks), exc)

    cards = dedupe_cards(interleave(per_chunk_cards))[:num_cards]
    if not cards:
        raise ValueError(
            "Couldn't generate any flashcards from this video"
            + (" (the model's replies could not be read)." if failures else ".")
        )

    log.info("Generated %d flashcards from %d chunk(s)", len(cards), len(chunks))
    return cards
