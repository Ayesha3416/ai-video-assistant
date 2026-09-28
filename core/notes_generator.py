"""Generate study notes from a video transcript (fix: whole-video coverage).

Before this fix, generate_notes only ever looked at content[:8000] -- on a
long video that's just the first several minutes. This version splits the
transcript into evenly-spaced chunks (same helper Step 3's flashcards use),
asks for a handful of sections per chunk, and concatenates them IN VIDEO
ORDER (unlike the quiz, notes should read start-to-end, not be shuffled).

Public signature is unchanged (generate_notes(content) -> dict,
build_notes_pdf(notes, video_title) -> bytes), so no caller needs to change.
"""

import json
import math
import re
import time

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from fpdf import FPDF

from config import get_logger
from core.flashcard_utils import select_chunks
from core.llm import get_llm, invoke_with_retry

log = get_logger(__name__)

#: At most this many LLM calls per set of notes (keeps latency and rate limits sane).
MAX_CHUNKS = 4
CHUNK_CHARS = 4000
#: Total sections across the whole video, spread evenly over the chunks used.
MAX_TOTAL_SECTIONS = 12

NOTES_SYSTEM_PROMPT = """You are an expert note-taker. Based on the video transcript/summary excerpt \
given, write clear, well-organized study notes covering everything important in THIS EXCERPT.

Respond with ONLY a valid JSON object (no markdown fences, no extra text) with this exact shape:
{{
  "title": "A short descriptive title for the whole video (your best guess from this excerpt)",
  "sections": [
    {{
      "heading": "Section heading",
      "bullets": ["Concise point 1", "Concise point 2"]
    }}
  ]
}}

Rules:
- Break this excerpt into at most {max_sections} logical section(s) with clear headings.
- Each section should have 2 to 6 concise bullet points — no long paragraphs.
- Cover the actual content of this excerpt; do not invent facts.
- Output ONLY the JSON object, nothing else, no commentary before or after it."""


def _extract_json_object(raw: str) -> str:
    """Strips ``` / ```json fences in case the model adds them despite instructions."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return raw


def _ask_llm(chunk: str, max_sections: int) -> str:
    """One LLM call for one transcript chunk. Isolated so tests can replace it."""
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", NOTES_SYSTEM_PROMPT),
        ("human", "{text}"),
    ])
    chain = prompt | llm | StrOutputParser()
    return invoke_with_retry(chain, {"text": chunk, "max_sections": max_sections})


def _parse_chunk_notes(raw: str) -> dict:
    """Parse one chunk's raw LLM reply, or raise ValueError."""
    cleaned = _extract_json_object(raw)
    try:
        notes = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse the notes response as JSON: {e}\nRaw response: {raw[:300]}")

    if not isinstance(notes, dict) or "sections" not in notes:
        raise ValueError("The notes response was not in the expected format.")

    cleaned_sections = []
    for section in notes.get("sections", []):
        if not isinstance(section, dict):
            continue
        heading = section.get("heading")
        bullets = section.get("bullets")
        if isinstance(heading, str) and isinstance(bullets, list):
            clean_bullets = [b for b in bullets if isinstance(b, str) and b.strip()]
            if clean_bullets:
                cleaned_sections.append({"heading": heading, "bullets": clean_bullets})

    if not cleaned_sections:
        raise ValueError("The notes response didn't contain any well-formed sections.")

    title = notes.get("title") if isinstance(notes.get("title"), str) else None
    return {"title": title, "sections": cleaned_sections}


def generate_notes(content: str) -> dict:
    """content: transcript (preferred) or summary text to base the notes on.
    Returns {"title": str, "sections": [{"heading": str, "bullets": [str, ...]}, ...]}.
    Raises ValueError if no usable section could be generated at all.
    """
    chunks = select_chunks(content, max_chunks=MAX_CHUNKS, size=CHUNK_CHARS)
    if not chunks:
        raise ValueError("There is no transcript or summary to make notes from.")

    sections_per_chunk = max(1, math.ceil(MAX_TOTAL_SECTIONS / len(chunks)))
    title = None
    all_sections = []
    failures = 0

    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(0.8)  # light pacing between chunk calls to avoid tripping Groq's rate limit
        try:
            partial = _parse_chunk_notes(_ask_llm(chunk, sections_per_chunk))
        except ValueError as exc:
            failures += 1
            log.warning("Notes: skipping chunk %d/%d (%s)", i + 1, len(chunks), exc)
            continue
        if title is None and partial["title"]:
            title = partial["title"]
        all_sections.extend(partial["sections"])  # kept in video order, not interleaved

    if not all_sections:
        raise ValueError(
            "Couldn't generate notes for this video"
            + (" (the model's replies could not be read)." if failures else ".")
        )

    log.info("Generated %d note section(s) from %d chunk(s)", len(all_sections), len(chunks))
    return {"title": title or "Video Notes", "sections": all_sections[:MAX_TOTAL_SECTIONS]}


def _sanitize_text(text: str) -> str:
    """fpdf's built-in core fonts only support Latin-1, so replace anything
    outside that range (emoji, smart quotes, non-Latin scripts) instead of
    letting PDF generation crash on it."""
    return text.encode("latin-1", "replace").decode("latin-1")


def build_notes_pdf(notes: dict, video_title: str = "") -> bytes:
    """Renders the structured notes dict (from generate_notes) into a PDF
    and returns the raw PDF bytes, ready to hand straight to
    st.download_button(data=..., mime="application/pdf")."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    title = notes.get("title") or video_title or "Video Notes"
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 10, _sanitize_text(title))
    pdf.ln(2)

    if video_title and video_title != title:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 6, _sanitize_text(f"From: {video_title}"))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

    for section in notes.get("sections", []):
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 8, _sanitize_text(section.get("heading", "")))
        pdf.ln(1)

        pdf.set_font("Helvetica", "", 11)
        for bullet in section.get("bullets", []):
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 6, _sanitize_text(f"-  {bullet}"))
        pdf.ln(3)

    return bytes(pdf.output(dest="S"))
