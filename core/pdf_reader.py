"""Extract plain text from an uploaded PDF.

Works only for PDFs that contain real text (most lecture notes, papers,
e-books). Scanned PDFs are just pictures of text; reading those needs OCR,
which this app does not do, so we tell the user clearly instead.
"""

from __future__ import annotations

import io
import re

from config import get_logger

log = get_logger(__name__)

# Roughly 75+ pages of dense text. Keeps analysis time and LLM cost bounded
# (every ~3000 characters costs one LLM call during summarizing).
MAX_PDF_CHARS = 200_000

# Fewer characters than this almost always means a scanned / image-only PDF.
MIN_PDF_CHARS = 200


class PdfError(ValueError):
    """Raised with a message that is safe to show to the user."""


def extract_pdf_text(data: bytes) -> tuple[str, bool]:
    """Return (text, was_truncated). Raises PdfError with a friendly message."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as e:
        log.warning("Could not open PDF: %r", e)
        raise PdfError("That file could not be opened as a PDF. It may be corrupted.")

    if reader.is_encrypted:
        try:
            ok = reader.decrypt("")
        except Exception:
            ok = 0
        if not ok:
            raise PdfError("That PDF is password-protected. Please upload an unlocked copy.")

    parts: list[str] = []
    total = 0
    truncated = False

    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception as e:  # one bad page should not kill the whole file
            log.warning("Skipping unreadable PDF page: %r", e)
            continue
        page_text = page_text.strip()
        if not page_text:
            continue
        parts.append(page_text)
        total += len(page_text)
        if total >= MAX_PDF_CHARS:
            truncated = True
            break

    text = "\n\n".join(parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if truncated:
        text = text[:MAX_PDF_CHARS]

    if len(text) < MIN_PDF_CHARS:
        raise PdfError(
            "I couldn't find readable text in that PDF. It may be a scanned "
            "document (images of pages). Please upload a PDF with selectable text."
        )

    return text, truncated
