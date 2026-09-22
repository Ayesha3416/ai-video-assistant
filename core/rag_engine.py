from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

from config import get_logger, settings
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
- If the answer truly isn't covered by either, say:
  "I could not find this information in the video."
Always be concise and precise. If quoting someone, mention it clearly.
Overview:
{summary}
Retrieved excerpts:
{context}"""


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
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{question}"),
    ])
    rag_chain = (
        {
            "context": retriever | RunnableLambda(format_docs),
            "question": RunnablePassthrough(),
            "summary": RunnableLambda(lambda _: summary or "Not available."),
        }
        | prompt | llm | StrOutputParser()
    )
    return rag_chain


def ask_question(rag_chain, question: str) -> str:
    log.info("Question: %s", question)
    answer = invoke_with_retry(rag_chain, question)
    log.debug("Answer: %s", answer)
    return answer