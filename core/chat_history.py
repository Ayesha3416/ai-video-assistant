"""Helpers for history-aware RAG.

Pure Python on purpose (no langchain / chroma / streamlit imports) so it is
fast to import and easy to unit-test.

The dashboard stores the whole conversation in ``st.session_state.chat_history``
as a list of dicts. Most entries are plain Q&A turns
(``{"role": ..., "content": ..., "time": ...}``) but that list also contains
things that must NOT be shown to the LLM as conversation:

* typed entries -- ``"type": "image" | "quiz" | "notes" | "quiz_count_prompt"``
* the user message that triggered one of those (e.g. "show me 2:30", "quiz")
* the pasted video URL / file path that started the chat
* status / error messages ("Done! I've analyzed ...", "Sorry, I couldn't ...")

``history_pairs`` filters all of that out and returns a short, clean list of
``(role, text)`` tuples.
"""

from __future__ import annotations

import re

#: Only the most recent messages matter for resolving "it" / "that" / "he".
MAX_HISTORY_MESSAGES = 8

#: Assistant answers can be long; the start is enough to resolve references.
MAX_CHARS_PER_MESSAGE = 700

#: Safety valve: a "rewritten question" longer than this is not a question.
MAX_REWRITE_CHARS = 500

_MEDIA_EXTENSIONS = (
    ".mp4", ".mp3", ".wav", ".mkv", ".mov", ".avi", ".m4a", ".webm", ".flac",
)

_URL_ONLY_RE = re.compile(r"^(https?://\S+|www\.\S+)$", re.IGNORECASE)

# Assistant messages that are status/errors, not real answers about the video.
_SKIP_ASSISTANT_PREFIXES = (
    "done! i've analyzed",
    "sorry, i couldn't",
    "something went wrong",
    "i don't have a video",
)

_REWRITE_PREFIX_RE = re.compile(
    r"^(self-contained question|rewritten question|standalone question|question)\s*:\s*",
    re.IGNORECASE,
)


def _looks_like_source(text: str) -> bool:
    """A pasted YouTube URL or local media path (mirrors the dashboard's idea)."""
    t = text.strip().strip("\"'").strip()
    if not t or "\n" in t or len(t) > 400:
        return False
    if _URL_ONLY_RE.match(t):
        return True
    return t.lower().endswith(_MEDIA_EXTENSIONS)


def _truncate(text: str, limit: int = MAX_CHARS_PER_MESSAGE) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def history_pairs(
    chat_history: list | None,
    current_question: str | None = None,
    max_messages: int = MAX_HISTORY_MESSAGES,
) -> list[tuple[str, str]]:
    """Return clean ``[("user"|"assistant", text), ...]`` from the dashboard history.

    ``current_question``: the dashboard appends the new user message to
    ``chat_history`` *before* calling the RAG engine. If the last entry is that
    same message it is dropped here so the question is not duplicated.
    """
    if not chat_history:
        return []

    entries = list(chat_history)

    # Drop the message currently being answered.
    if (
        current_question is not None
        and entries
        and isinstance(entries[-1], dict)
        and entries[-1].get("role") == "user"
        and str(entries[-1].get("content", "")).strip() == current_question.strip()
    ):
        entries = entries[:-1]

    pairs: list[tuple[str, str]] = []
    for i, msg in enumerate(entries):
        if not isinstance(msg, dict):
            continue

        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue

        # Quiz / notes / frame image / picker entries are not conversation.
        if msg.get("type"):
            continue

        content = msg.get("content")
        if not isinstance(content, str) or not content.strip():
            continue

        if role == "user":
            # The pasted video link that started this chat.
            if _looks_like_source(content):
                continue
            # A user request that was answered with a typed entry
            # ("quiz", "show me 2:30", "make notes") is not a Q&A turn.
            nxt = entries[i + 1] if i + 1 < len(entries) else None
            if isinstance(nxt, dict) and nxt.get("type"):
                continue
        else:
            lowered = content.strip().lower()
            if lowered.startswith(_SKIP_ASSISTANT_PREFIXES):
                continue

        pairs.append((role, _truncate(content)))

    pairs = pairs[-max_messages:]

    # After slicing, never start on an assistant message.
    while pairs and pairs[0][0] == "assistant":
        pairs.pop(0)

    return pairs


def format_history_for_prompt(pairs: list[tuple[str, str]]) -> str:
    """Plain-text transcript used inside the query-rewrite prompt."""
    lines = []
    for role, text in pairs:
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {text}")
    return "\n".join(lines)


def clean_rewrite(raw: str | None, original: str) -> str:
    """Sanitise the model's rewritten question; fall back to the original.

    Models sometimes wrap the answer in quotes, add a label, or write several
    lines. Take the first non-empty line, strip decoration, and give up (return
    ``original``) if nothing sensible is left.
    """
    if not raw:
        return original

    first = ""
    for line in str(raw).splitlines():
        if line.strip():
            first = line.strip()
            break
    if not first:
        return original

    first = _REWRITE_PREFIX_RE.sub("", first).strip()
    first = first.strip("\"'`").strip()

    if not first or len(first) > MAX_REWRITE_CHARS:
        return original
    return first
