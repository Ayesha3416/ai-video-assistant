"""Safe handling of files uploaded through the dashboard.

Why this exists: on a deployed server, users cannot type a path to a file on
their own computer -- the server cannot see it. They upload the file instead,
and this module stores it somewhere the pipeline can read.

Safety rules enforced here:
  * only known audio/video extensions are accepted
  * the original filename is never used on disk (a random name is), so a
    name like "../../app.py" cannot escape the uploads folder
  * size is checked against MAX_UPLOAD_MB
  * old uploads are deleted so the disk does not fill up
"""

from __future__ import annotations

import re
import time
import uuid
from pathlib import Path

from config import get_logger, settings
from config import paths

log = get_logger(__name__)

ALLOWED_EXTENSIONS = (
    ".mp4", ".mp3", ".wav", ".mkv", ".mov", ".avi", ".m4a", ".webm", ".flac",
)


class UploadError(Exception):
    """Raised with a message that is safe to show to the user."""


def _display_name(filename: str) -> str:
    """A filename that is safe to show in the UI / embed in HTML."""
    name = Path(filename).name  # drops any directory part
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
    return name[:80] or "upload"


def cleanup_old_uploads(max_age_hours: int | None = None) -> int:
    """Delete uploaded files older than the retention window. Returns count."""
    hours = settings.upload_retention_hours if max_age_hours is None else max_age_hours
    uploads_dir = Path(paths.UPLOADS_DIR)
    if not uploads_dir.exists():
        return 0

    cutoff = time.time() - hours * 3600
    removed = 0
    for f in uploads_dir.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError as e:
            log.warning("Could not remove old upload %s: %s", f, e)
    if removed:
        log.info("Removed %d old upload file(s).", removed)
    return removed


def save_uploaded_file(filename: str, data) -> tuple[str, str]:
    """Validate and store an uploaded file.

    Returns (path_on_disk, display_name). Raises UploadError with a
    user-friendly message if the file is not acceptable.
    """
    display = _display_name(filename)
    ext = Path(display).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise UploadError(
            f"'{ext or 'this'}' files are not supported. "
            f"Please upload one of: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    size = len(data)
    if size == 0:
        raise UploadError("That file is empty.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size > max_bytes:
        raise UploadError(
            f"That file is {size / 1_048_576:.0f} MB; the limit is "
            f"{settings.max_upload_mb} MB."
        )

    uploads_dir = Path(paths.UPLOADS_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    cleanup_old_uploads()

    dest = uploads_dir / f"{uuid.uuid4().hex}{ext}"
    dest.write_bytes(bytes(data))
    log.info("Saved upload %s (%d bytes) as %s", display, size, dest.name)
    return str(dest), display
