from dataclasses import dataclass
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser

from config import get_logger, settings
from core.chat_history import clean_rewrite, format_history_for_prompt, history_pairs
from core.llm import get_llm, invoke_with_retry
from core.vector_store import build_vector_store, build_vector_store_from_segments, get_retriever

log = get_logger(__name__)


def format_docs(docs):
    """Unchanged for chunks with no timestamp metadata (hinglish / legacy
    transcript-based vector stores). Chunks built from timestamped segments
    (see vector_store.build_vector_store_from_segments) get their [MM:SS]
    label prefixed so the model can cite it in answers.
    """
    parts = []
    for doc in docs:
        label = doc.metadata.get("start_label") if doc.metadata else None
        if label:
            parts.append(f"[{label}] {doc.page_content}")
        else:
            parts.append(doc.page_content)
    return "\n\n".join(parts)


SYSTEM_PROMPT = """You are an expert video/meeting assistant. Answer the user's question
using the Overview and the Retrieved excerpts below.
- If the question is general (e.g. "what is this video about", "summarize this"),
  rely mainly on the Overview.
- If the question is specific, rely mainly on the Retrieved excerpts.
- Some excerpts are prefixed with a timestamp like [12:34] (minutes:seconds,
  or h:mm:ss for longer videos) showing where in the video that excerpt was
  said. If the user asks when/at what timestamp something was said, or citing
  the moment would help, include that timestamp in your answer in the same
  [MM:SS] format. If an excerpt has no timestamp prefix, don't invent one.
- The earlier conversation is only there to help you understand what the user
  is referring to (e.g. "it", "that", "the second point"). Facts must still come
  from the Overview and Retrieved excerpts, not from earlier replies alone.
- If the answer truly isn't covered by either, say:
  "I could not find this information in the video."
Always be concise and precise. If quoting someone, mention it clearly.
Overview:
{summary}
Retrieved excerpts:
{context}"""


REWRITE_SYSTEM_PROMPT = """You rewrite follow-up questions for a search system that looks up
passages in a video transcript.

Given the conversation so far and the user's latest question, rewrite the latest
question so it is completely self-contained: replace pronouns and vague references
("it", "that", "he", "the second one", "what about after that?") with what they
refer to, using the conversation.

Rules:
- Do NOT answer the question.
- If the latest question is already self-contained, return it unchanged.
- Keep the user's meaning and language. Do not add facts that are not in the conversation.
- Output only the rewritten question on a single line, with no quotes and no label."""


@dataclass
class RagChain:
    """Everything needed to answer one question about one video.

    Replaces the old single LCEL chain. Splitting it into parts lets
    ``ask_question`` do the extra "rewrite the follow-up into a standalone
    search query" step *before* retrieval, and retry each LLM call separately.
    """

    retriever: Any
    rewrite_chain: Any
    answer_chain: Any
    summary: str = ""


def build_rag_chain(transcript: str, summary: str = "", segments: list = None):
    """segments is optional and additive: when a non-empty list of timestamped
    segments is available (English/Whisper videos — see
    transcriber.transcribe_all_with_segments), retrieval chunks are built
    from those directly so answers can cite real video timestamps. When
    segments is None/empty (hinglish videos, or old saved sessions from
    before this feature existed), behavior is exactly what it was before:
    plain transcript-based chunking, no timestamps in answers.
    """
    if segments:
        vector_store = build_vector_store_from_segments(segments)
    else:
        vector_store = build_vector_store(transcript)

    retriever = get_retriever(vector_store, k=settings.retriever_k)

    answer_prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{question}"),
    ])
    answer_chain = answer_prompt | get_llm() | StrOutputParser()

    rewrite_prompt = ChatPromptTemplate.from_messages([
        ("system", REWRITE_SYSTEM_PROMPT),
        (
            "human",
            "Conversation so far:\n{history}\n\n"
            "Latest question: {question}\n\n"
            "Self-contained question:",
        ),
    ])
    # Temperature 0: rewriting should be deterministic, not creative.
    rewrite_chain = rewrite_prompt | get_llm(temperature=0.0) | StrOutputParser()

    return RagChain(
        retriever=retriever,
        rewrite_chain=rewrite_chain,
        answer_chain=answer_chain,
        summary=summary or "Not available.",
    )


def _to_messages(pairs):
    return [
        HumanMessage(content=text) if role == "user" else AIMessage(content=text)
        for role, text in pairs
    ]


def _search_query(rag_chain: RagChain, question: str, pairs) -> str:
    """Turn a possibly-vague follow-up into a standalone search query.

    No history -> the question is returned as-is with no extra LLM call.
    Any failure -> fall back to the raw question (old behaviour), never crash.
    """
    if not pairs:
        return question
    try:
        raw = invoke_with_retry(
            rag_chain.rewrite_chain,
            {"history": format_history_for_prompt(pairs), "question": question},
        )
    except Exception as exc:  # noqa: BLE001 - rewriting is best-effort
        log.warning("Query rewrite failed (%s); using the original question.", exc)
        return question

    query = clean_rewrite(raw, question)
    if query != question:
        log.info("Follow-up rewritten for retrieval: %r -> %r", question, query)
    return query


def ask_question(rag_chain, question: str, chat_history: list | None = None) -> str:
    """Answer ``question`` about the video.

    ``chat_history`` is the dashboard's ``st.session_state.chat_history`` (it may
    already include the current question as its last entry -- that is handled).
    Omit it for one-off, context-free lookups (e.g. the frame-finder).
    """
    log.info("Question: %s", question)

    # A chain object created before this upgrade (e.g. still sitting in an open
    # Streamlit session) is a plain LCEL runnable: answer it the old way.
    if not isinstance(rag_chain, RagChain):
        return invoke_with_retry(rag_chain, question)

    pairs = history_pairs(chat_history, current_question=question)
    query = _search_query(rag_chain, question, pairs)

    docs = rag_chain.retriever.invoke(query)
    answer = invoke_with_retry(
        rag_chain.answer_chain,
        {
            "summary": rag_chain.summary,
            "context": format_docs(docs),
            "chat_history": _to_messages(pairs),
            "question": question,
        },
    )
    log.debug("Answer: %s", answer)
    return answer
