"""Step 8: PDF upload validation and text extraction.

    pytest tests/test_uploads.py -v
"""

import io
from types import SimpleNamespace

import pytest

from utils import uploads
from utils.uploads import UploadError, validate_pdf_upload
from core.pdf_reader import PdfError, extract_pdf_text, MAX_PDF_CHARS


def _make_pdf(text: str, pages: int = 1) -> bytes:
    """Build a small real PDF with selectable text (needs reportlab or fpdf2)."""
    try:
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        for _ in range(pages):
            y = 800
            for line in text.split("\n"):
                c.drawString(40, y, line)
                y -= 14
            c.showPage()
        c.save()
        return buf.getvalue()
    except ImportError:
        from fpdf import FPDF

        pdf = FPDF()
        for _ in range(pages):
            pdf.add_page()
            pdf.set_font("Helvetica", size=11)
            for line in text.split("\n"):
                pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
        return bytes(pdf.output())


LONG_TEXT = "\n".join(
    f"Line {i}: Retrieval augmented generation combines search with a language model."
    for i in range(20)
)


# ------------------------------------------------------------ validation

def test_valid_pdf_passes_and_returns_safe_name():
    data = _make_pdf(LONG_TEXT)
    assert validate_pdf_upload("My Notes.PDF", data) == "My Notes.PDF"


def test_path_and_html_in_filename_are_neutralised():
    data = _make_pdf(LONG_TEXT)
    shown = validate_pdf_upload("../../<script>x</script>.pdf", data)
    assert "/" not in shown and "<" not in shown and ">" not in shown


@pytest.mark.parametrize("name", ["notes.txt", "video.mp4", "song.mp3", "run.py", "doc.docx"])
def test_non_pdf_extensions_rejected(name):
    with pytest.raises(UploadError):
        validate_pdf_upload(name, b"%PDF-1.4 whatever")


def test_renamed_non_pdf_rejected():
    with pytest.raises(UploadError):
        validate_pdf_upload("fake.pdf", b"MZ\x90\x00 not a pdf at all")


def test_empty_file_rejected():
    with pytest.raises(UploadError):
        validate_pdf_upload("a.pdf", b"")


def test_too_large_rejected(monkeypatch):
    monkeypatch.setattr(uploads, "settings", SimpleNamespace(max_upload_mb=0))
    with pytest.raises(UploadError):
        validate_pdf_upload("a.pdf", b"%PDF-1.4 x")


# ------------------------------------------------------------ extraction

def test_extracts_text_from_real_pdf():
    text, truncated = extract_pdf_text(_make_pdf(LONG_TEXT, pages=2))
    assert "Retrieval augmented generation" in text
    assert truncated is False


def test_garbage_bytes_give_friendly_error():
    with pytest.raises(PdfError):
        extract_pdf_text(b"%PDF-1.4 this is not really a pdf")


def test_image_only_pdf_is_reported_as_scanned():
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(width=200, height=200)  # a page with no text at all
    buf = io.BytesIO()
    w.write(buf)
    with pytest.raises(PdfError) as exc:
        extract_pdf_text(buf.getvalue())
    assert "scanned" in str(exc.value).lower()


def test_very_long_pdf_is_truncated():
    big = "\n".join(f"Sentence number {i} about neural networks and data." for i in range(40))
    text, truncated = extract_pdf_text(_make_pdf(big, pages=400))
    assert truncated is True
    assert len(text) <= MAX_PDF_CHARS
