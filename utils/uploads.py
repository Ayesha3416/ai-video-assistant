"""Validation for PDFs uploaded through the dashboard.

The PDF is read straight from memory and never written to disk, so there is
nothing to clean up and no filename can touch the filesystem. We still check:
  * the extension is .pdf
  * the file really starts with the PDF signature (not a renamed .exe etc.)
  * the size is within MAX_UPLOAD_MB
  * the filename is made safe to show on screen
"""

from __future__ import annotations

import re
from pathlib import Path

from config import settings

ALLOWED_EXTENSIONS = (".pdf",)


class UploadError(Exception):
    """Raised with a message that is safe to show to the user."""


def _display_name(filename: str) -> str:
    """A filename that is safe to show in the UI / embed in HTML."""
    name = Path(filename).name  # drops any directory part
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
    return name[:80] or "document.pdf"


def validate_pdf_upload(filename: str, data) -> str:
    """Check an uploaded file. Returns a safe display name, or raises UploadError."""
    display = _display_name(filename)

    if Path(display).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise UploadError("Only PDF files are supported. Please upload a .pdf file.")

    size = len(data)
    if size == 0:
        raise UploadError("That file is empty.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size > max_bytes:
        raise UploadError(
            f"That file is {size / 1_048_576:.0f} MB; the limit is "
            f"{settings.max_upload_mb} MB."
        )

    if bytes(data[:5]) != b"%PDF-":
        raise UploadError("That file doesn't look like a real PDF.")

    return display
