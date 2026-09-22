# Actionable items, decisions, questions

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_text_splitters import RecursiveCharacterTextSplitter

import time

from config import get_logger
from core.llm import get_llm, invoke_with_retry

log = get_logger(__name__)


def build_chain(system_prompt: str):
    llm = get_llm(temperature=0.2)
    return (
        RunnablePassthrough() | RunnableLambda(lambda x: {"text": x}) | ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{text}"),
        ]) | llm | StrOutputParser()
    )


def _split_transcript(transcript: str) -> list:
    splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=200)
    return splitter.split_text(transcript)


def _extract_with_map_reduce(transcript: str, map_prompt: str, reduce_prompt: str) -> str:
    """Mirrors the map-reduce pattern summarizer.summarize() already uses, so long
    (e.g. 2-hour) videos get complete extraction instead of one call over the
    entire transcript at once.

    For short/normal-length transcripts (the common case — everything fits in a
    single ~3000-char chunk), this takes exactly the same single-call path as
    before: one map call, no reduce call, identical output to the old behavior.
    Only when a transcript is long enough to split into multiple chunks does
    the extra reduce/merge step run.
    """
    chunks = _split_transcript(transcript)
    map_chain = build_chain(map_prompt)

    if len(chunks) == 1:
        return invoke_with_retry(map_chain, chunks[0])

    partials = []
    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(0.8)  # light pacing between chunk calls to avoid tripping Groq's rate limit
        partials.append(invoke_with_retry(map_chain, chunk))

    combined_input = "\n\n".join(
        f"--- Part {i + 1} ---\n{p}" for i, p in enumerate(partials)
    )

    reduce_chain = build_chain(reduce_prompt)
    return invoke_with_retry(reduce_chain, combined_input)


def extract_action_items(transcript: str) -> str:
    return _extract_with_map_reduce(
        transcript,
        map_prompt=(
            "You are an expert meeting analyst. From this portion of a meeting transcript, "
            "extract all action items. For each provide:\n"
            "- Task description\n"
            "- Owner (who is responsible)\n"
            "- Deadline (if mentioned, else write 'Not specified')\n\n"
            "Format as a numbered list. If none found in this portion, say 'No action items found.'"
        ),
        reduce_prompt=(
            "Below are action items extracted from different parts of the same meeting "
            "transcript, in order. Combine them into ONE final numbered list, removing "
            "duplicates and any 'No action items found' placeholders (unless every part had "
            "none, in which case just say 'No action items found.'). Keep the task, owner, "
            "and deadline for each."
        ),
    )


def extract_key_decisions(transcript: str) -> str:
    return _extract_with_map_reduce(
        transcript,
        map_prompt=(
            "You are an expert meeting analyst. From this portion of a meeting transcript, "
            "extract all key decisions made. Format as a numbered list. "
            "If none found in this portion, say 'No key decisions found.'"
        ),
        reduce_prompt=(
            "Below are key decisions extracted from different parts of the same meeting "
            "transcript, in order. Combine them into ONE final numbered list, removing "
            "duplicates and any 'No key decisions found' placeholders (unless every part had "
            "none, in which case just say 'No key decisions found.')."
        ),
    )


def extract_questions(transcript: str) -> str:
    return _extract_with_map_reduce(
        transcript,
        map_prompt=(
            "From this portion of a meeting transcript, extract all unresolved questions "
            "or topics needing follow-up. Format as a numbered list. "
            "If none found in this portion, say 'No open questions found.'"
        ),
        reduce_prompt=(
            "Below are open questions extracted from different parts of the same meeting "
            "transcript, in order. Combine them into ONE final numbered list, removing "
            "duplicates and any 'No open questions found' placeholders (unless every part had "
            "none, in which case just say 'No open questions found.')."
        ),
    )


VALID_CATEGORIES = [
    "Education", "Entertainment", "Sports", "Technology",
    "News", "Business", "Music", "Other",
]


def classify_category(transcript: str) -> str:
    chain = build_chain(
        "You are a classifier. Based on the video transcript, classify it into exactly "
        "ONE of these categories: Education, Entertainment, Sports, Technology, News, "
        "Business, Music, Other. Respond with ONLY the single category word — nothing else, "
        "no punctuation, no explanation."
    )
    raw = invoke_with_retry(chain, transcript[:2000]).strip()

    # Normalize: strip punctuation/whitespace, take first word, match case-insensitively
    cleaned = raw.strip(" .!\n\"'").split()[0] if raw.strip(" .!\n\"'") else ""

    for valid in VALID_CATEGORIES:
        if cleaned.lower() == valid.lower():
            return valid

    log.warning("classify_category: unrecognized model output %r -> defaulting to Other", raw)
    return "Other"