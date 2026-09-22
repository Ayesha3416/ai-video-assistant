import json
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from fpdf import FPDF

from core.llm import get_llm, invoke_with_retry


NOTES_SYSTEM_PROMPT = """You are an expert note-taker. Based on the video transcript/summary given, \
write clear, well-organized study notes covering everything important in the video.

Respond with ONLY a valid JSON object (no markdown fences, no extra text) with this exact shape:
{{
  "title": "A short descriptive title for these notes",
  "sections": [
    {{
      "heading": "Section heading",
      "bullets": ["Concise point 1", "Concise point 2"]
    }}
  ]
}}

Rules:
- Break the content into 3 to 8 logical sections with clear headings.
- Each section should have 2 to 6 concise bullet points — no long paragraphs.
- Cover the actual content of the video; do not invent facts.
- Output ONLY the JSON object, nothing else, no commentary before or after it."""


def _extract_json_object(raw: str) -> str:
    """Strips ``` / ```json fences in case the model adds them despite instructions."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return raw


def generate_notes(content: str) -> dict:
    """content: transcript (preferred) or summary text to base the notes on.
    Returns {"title": str, "sections": [{"heading": str, "bullets": [str, ...]}, ...]}.
    Raises ValueError if the model's output can't be parsed into that shape.
    """
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", NOTES_SYSTEM_PROMPT),
        ("human", "{text}"),
    ])
    chain = prompt | llm | StrOutputParser()

    raw = invoke_with_retry(chain, {"text": content[:8000]})
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

    return {
        "title": notes.get("title") if isinstance(notes.get("title"), str) else "Video Notes",
        "sections": cleaned_sections,
    }


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