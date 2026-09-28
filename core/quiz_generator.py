"""Generate a quiz from a video transcript (fix: whole-video coverage).

Before this fix, generate_quiz only ever looked at content[:6000] -- on a long
video that's just the first few minutes, so every quiz was effectively about
the intro. This version reuses the same "sample evenly-spaced chunks across
the whole transcript" approach as core/flashcard_generator.py (Step 3), so a
2-hour video gets questions from start to end.

Public signature is unchanged (generate_quiz(content, num_questions)), so no
caller needs to change.
"""

import json
import math
import re
import time

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import get_logger
from core.flashcard_utils import interleave, select_chunks
from core.llm import get_llm, invoke_with_retry

log = get_logger(__name__)

#: At most this many LLM calls per quiz (keeps latency and rate limits sane).
MAX_CHUNKS = 4
CHUNK_CHARS = 3500

QUIZ_SYSTEM_PROMPT = """You are a quiz-writing assistant. Based on the video transcript/summary excerpt \
given, write exactly {n} multiple-choice quiz questions that test understanding of this excerpt's content.

Respond with ONLY a valid JSON array (no markdown fences, no extra text) where each item has this exact shape:
{{
  "question": "...",
  "options": ["...", "...", "...", "..."],
  "correct_index": 0
}}

Rules:
- Exactly 4 options per question, only one of them correct.
- correct_index is the 0-based index of the correct option within "options".
- Questions must be answerable from the given excerpt only — do not invent facts.
- Do not repeat the same question twice.
- Output ONLY the JSON array, nothing else, no commentary before or after it."""


def _extract_json_array(raw: str) -> str:
    """Strips ``` / ```json fences in case the model adds them despite instructions."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return raw


def _normalize(question_text: str) -> str:
    """Loose key for de-duplication across chunks (case/whitespace-insensitive)."""
    return re.sub(r"\s+", " ", question_text.strip().lower())


def _ask_llm(chunk: str, n: int) -> str:
    """One LLM call for one transcript chunk. Isolated so tests can replace it."""
    llm = get_llm(temperature=0.4)
    prompt = ChatPromptTemplate.from_messages([
        ("system", QUIZ_SYSTEM_PROMPT),
        ("human", "{text}"),
    ])
    chain = prompt | llm | StrOutputParser()
    return invoke_with_retry(chain, {"text": chunk, "n": n})


def _parse_and_clean(raw: str) -> list:
    """Parse one chunk's raw LLM reply into well-formed question dicts, or raise ValueError."""
    cleaned = _extract_json_array(raw)
    try:
        questions = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse the quiz response as JSON: {e}\nRaw response: {raw[:300]}")

    if not isinstance(questions, list) or not questions:
        raise ValueError("The quiz response was not a non-empty list of questions.")

    cleaned_questions = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        options = q.get("options")
        question_text = q.get("question")
        correct_index = q.get("correct_index")
        if (
            isinstance(question_text, str)
            and isinstance(options, list)
            and len(options) >= 2
            and isinstance(correct_index, int)
            and 0 <= correct_index < len(options)
        ):
            cleaned_questions.append({
                "question": question_text,
                "options": options,
                "correct_index": correct_index,
            })

    if not cleaned_questions:
        raise ValueError("The quiz response didn't contain any well-formed questions.")
    return cleaned_questions


def generate_quiz(content: str, num_questions: int) -> list:
    """content: transcript (preferred) or summary text to base the quiz on.
    Returns a list of dicts: {"question": str, "options": [str, str, str, str], "correct_index": int}.
    Raises ValueError if no usable question could be generated at all.
    """
    chunks = select_chunks(content, max_chunks=MAX_CHUNKS, size=CHUNK_CHARS)
    if not chunks:
        raise ValueError("There is no transcript or summary to make a quiz from.")

    per_chunk = max(1, math.ceil(num_questions / len(chunks)))
    per_chunk_questions = []
    failures = 0

    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(0.8)  # light pacing between chunk calls to avoid tripping Groq's rate limit
        try:
            per_chunk_questions.append(_parse_and_clean(_ask_llm(chunk, per_chunk)))
        except ValueError as exc:
            failures += 1
            log.warning("Quiz: skipping chunk %d/%d (%s)", i + 1, len(chunks), exc)

    merged = interleave(per_chunk_questions)  # spread across the video, not all-chunk-1-then-chunk-2

    seen = set()
    deduped = []
    for q in merged:
        key = _normalize(q["question"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(q)

    questions = deduped[:num_questions]
    if not questions:
        raise ValueError(
            "Couldn't generate a quiz from this video"
            + (" (the model's replies could not be read)." if failures else ".")
        )

    log.info("Generated %d quiz question(s) from %d chunk(s)", len(questions), len(chunks))
    return questions
