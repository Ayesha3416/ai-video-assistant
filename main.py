from config import bootstrap, get_logger

bootstrap()

from core.extractor import (
    extract_action_items,
    extract_key_decisions,
    extract_questions,
    classify_category,
)
from utils.audio_processor import process_input
from core.transcriber import transcribe_all_with_segments
from core.summarizer import summarize, generate_title
from core.rag_engine import build_rag_chain, ask_question

log = get_logger(__name__)


def run_pipeline(source: str, language: str = "english", on_progress=None) -> dict:
    def report(stage: str, message: str):
        log.info("[%s] %s", stage, message)
        if on_progress:
            on_progress(stage, message)

    report("downloading", "Preparing audio source...")
    chunks = process_input(source, on_progress=report)

    report("loading_whisper", "Loading transcription model...")
    transcript_data = transcribe_all_with_segments(chunks, language, on_progress=report)
    transcript = transcript_data["text"]
    segments = transcript_data["segments"]  # [] for hinglish — no per-sentence timing available
    report("transcribing", f"Transcription complete ({len(transcript)} characters).")

    report("summarizing", "Generating title...")
    title = generate_title(transcript)

    report("summarizing", "Summarizing transcript...")
    summary = summarize(transcript)

    report("extracting", "Extracting action items...")
    action_item = extract_action_items(transcript)

    report("extracting", "Extracting key decisions...")
    decisions = extract_key_decisions(transcript)

    report("extracting", "Extracting open questions...")
    questions = extract_questions(transcript)

    report("extracting", "Classifying video category...")
    category = classify_category(transcript)

    report("building_rag", "Building searchable knowledge base...")
    rag_chain = build_rag_chain(transcript, summary, segments)

    report("completed", "Analysis complete.")

    return {
        "title": title,
        "transcript": transcript,
        "segments": segments,
        "summary": summary,
        "action_items": action_item,
        "key_decisions": decisions,
        "open_questions": questions,
        "rag_chain": rag_chain,
        "category": category,
        "source": source,
    }


if __name__ == "__main__":
    # CLI entry point
    source = input("Enter YouTube URL or local file path: ").strip()
    language = input("Language (english/hinglish): ").strip() or "english"
    result = run_pipeline(source, language)

    print("\n" + "=" * 60)
    print(f"Title: {result['title']}")
    print(f"\nSummary:\n{result['summary']}")
    print(f"\nAction Items:\n{result['action_items']}")
    print(f"\nKey Decisions:\n{result['key_decisions']}")
    print(f"\nOpen Questions:\n{result['open_questions']}")
    print("=" * 60)

    # Phase 2 — Chat with your meeting via RAG
    print("\nChat with your meeting (type 'exit' to quit)\n")
    rag_chain = result["rag_chain"]
    while True:
        question = input("You: ").strip()
        if question.lower() in ["exit", "quit", "q"]:
            print("Goodbye!")
            break
        if not question:
            continue
        answer = ask_question(rag_chain, question)
        print(f"\nAssistant: {answer}\n")
