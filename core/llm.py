"""The one place that builds the Groq chat model and retries rate-limited calls.

Before this module, ``get_llm()`` was copy-pasted into five files (each with its
own hard-coded model name and temperature) and ``invoke_with_retry`` lived in
``core/extractor.py`` even though summarizer, rag_engine, quiz_generator and
notes_generator all imported it from there.

    from core.llm import get_llm, invoke_with_retry
"""

from __future__ import annotations

import re
import time

from langchain_groq import ChatGroq

from config import get_logger, settings

log = get_logger(__name__)

# "429" as a whole word, so a token count like "4290" does not trigger a retry.
_RATE_LIMIT_RE = re.compile(r"\b429\b|rate[ _-]?limit|too many requests", re.IGNORECASE)

#: Never wait longer than this for a single retry, even if the API asks for more.
_MAX_BACKOFF_SECONDS = 60.0


def get_llm(temperature: float = 0.3) -> ChatGroq:
    """Build the chat model.

    Temperatures used by the callers (kept identical to the old per-file copies):
    extractor 0.2 · summarizer / RAG / notes 0.3 · quiz 0.4.
    """
    if not settings.groq_api_key:
        # A clear message beats the opaque client error you get from an empty key.
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file and restart the app."
        )
    return ChatGroq(
        model=settings.groq_model,
        groq_api_key=settings.groq_api_key,
        temperature=temperature,
    )


def _is_rate_limited(exc: Exception) -> bool:
    if getattr(exc, "status_code", None) == 429:
        return True
    return bool(_RATE_LIMIT_RE.search(str(exc)))


def _retry_delay(exc: Exception, attempt: int, initial_delay: float) -> float:
    """Honour the API's ``retry-after`` header when present, else back off exponentially."""
    backoff = initial_delay * (2**attempt)
    try:
        headers = exc.response.headers  # type: ignore[attr-defined]
        advised = float(headers.get("retry-after"))
        return min(max(advised, backoff), _MAX_BACKOFF_SECONDS)
    except (AttributeError, TypeError, ValueError):
        return min(backoff, _MAX_BACKOFF_SECONDS)


def invoke_with_retry(chain, input_data, max_retries: int = 5, initial_delay: float = 2.0):
    """Invoke a LangChain runnable, backing off and retrying on HTTP 429.

    Any other error, and a 429 on the final attempt, is raised unchanged.
    """
    max_retries = max(1, max_retries)
    for attempt in range(max_retries):
        try:
            return chain.invoke(input_data)
        except Exception as exc:
            if _is_rate_limited(exc) and attempt < max_retries - 1:
                delay = _retry_delay(exc, attempt, initial_delay)
                log.warning(
                    "Groq rate limit (429). Backing off %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(delay)
                continue
            raise
