import os
import shutil
import uuid
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from config import get_logger, settings
from config.paths import VECTOR_DB_DIR

log = get_logger(__name__)

# str(...) because callers os.path.join() this with plain strings below.
CHROMA_ROOT = str(VECTOR_DB_DIR)
COLLECTION_NAME = "meeting_transcript"
EMBEDDING_MODEL = settings.embedding_model


def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"}
    )


def _cleanup_old_stores():
    """Remove previous vector store folders so disk doesn't fill up over time."""
    if os.path.exists(CHROMA_ROOT):
        for name in os.listdir(CHROMA_ROOT):
            path = os.path.join(CHROMA_ROOT, name)
            try:
                shutil.rmtree(path)
            except Exception as e:
                log.warning("Could not remove old vector store %s: %s", path, e)


def build_vector_store(transcript: str) -> Chroma:
    log.info("Building vector store")

    os.makedirs(CHROMA_ROOT, exist_ok=True)
    _cleanup_old_stores()

    # Use a fresh, uniquely-named subdirectory every time to avoid
    # chromadb's internal client-path caching returning a stale connection.
    session_dir = os.path.join(CHROMA_ROOT, uuid.uuid4().hex)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    chunks = splitter.split_text(transcript)
    docs = [
        Document(page_content=chunk, metadata={'chunk_index': i})
        for i, chunk in enumerate(chunks)
    ]
    embeddings = get_embeddings()
    vector_store = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=session_dir
    )
    return vector_store


def _format_timestamp(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def build_vector_store_from_segments(segments: list, target_chunk_chars: int = 500) -> Chroma:
    """Additive alternative to build_vector_store(): builds retrievable chunks
    directly from Whisper's timestamped segments (see
    transcriber.transcribe_all_with_segments) instead of re-splitting a plain
    transcript string by character count. This lets every retrieved chunk
    carry its own real video timestamp in metadata['start'] /
    metadata['start_label'], which rag_engine.py uses to cite timestamps in
    answers.

    Consecutive segments are merged up to roughly target_chunk_chars so we
    don't end up with hundreds of tiny 2-3 second retrieval chunks (which
    hurts retrieval quality) — each merged chunk keeps the START time of its
    FIRST segment as its citation timestamp.

    Falls back to raising if segments is empty — callers should check for
    that and use build_vector_store(transcript) instead (this is exactly
    what rag_engine.build_rag_chain does for hinglish / no-segments videos).
    """
    if not segments:
        raise ValueError("build_vector_store_from_segments called with no segments")

    log.info("Building vector store from timestamped segments")

    os.makedirs(CHROMA_ROOT, exist_ok=True)
    _cleanup_old_stores()

    session_dir = os.path.join(CHROMA_ROOT, uuid.uuid4().hex)

    docs = []
    buf_text = []
    buf_start = None
    buf_len = 0

    def flush():
        if buf_text:
            docs.append(
                Document(
                    page_content=" ".join(buf_text).strip(),
                    metadata={
                        "start": buf_start,
                        "start_label": _format_timestamp(buf_start),
                    },
                )
            )

    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue
        if buf_start is None:
            buf_start = seg["start"]
        buf_text.append(text)
        buf_len += len(text)
        if buf_len >= target_chunk_chars:
            flush()
            buf_text, buf_start, buf_len = [], None, 0

    flush()

    if not docs:
        raise ValueError("No non-empty segments to build a vector store from")

    embeddings = get_embeddings()
    vector_store = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=session_dir,
    )
    return vector_store


def get_retriever(vector_store: Chroma, k: int = 4):
    return vector_store.as_retriever(
        search_type='similarity',
        search_kwargs={"k": k}
    )


if __name__ == "__main__":
    sample_transcript = (
        "Alright, so here we are, one of the elephants. The cool thing about "
        "these guys is that they have really, really, really long trunks. "
        "And that's cool. And that's pretty much all there is to say."
    )
    vs = build_vector_store(sample_transcript)
    print("Vector store built successfully.")
    retriever = get_retriever(vs, k=2)
    results = retriever.invoke("What did they say about elephants?")
    print(f"\nRetrieved {len(results)} chunks:")
    for r in results:
        print("-", r.page_content)