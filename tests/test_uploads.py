"""Step 8: uploaded-file handling.

    pytest tests/test_uploads.py -v
"""

import os
import time

import pytest

from utils import uploads
from utils.uploads import UploadError, save_uploaded_file, cleanup_old_uploads


@pytest.fixture(autouse=True)
def _tmp_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads.paths, "UPLOADS_DIR", tmp_path / "uploads")
    return tmp_path / "uploads"


def test_valid_upload_is_saved_with_random_name(_tmp_uploads):
    path, shown = save_uploaded_file("My Lecture.MP4", b"fake video bytes")
    assert os.path.exists(path)
    assert path.endswith(".mp4")
    assert "Lecture" not in os.path.basename(path)  # original name never used on disk
    assert shown == "My Lecture.MP4"
    assert os.path.dirname(path) == str(_tmp_uploads)


def test_path_traversal_name_cannot_escape(_tmp_uploads):
    path, shown = save_uploaded_file("../../etc/evil.mp3", b"x")
    assert os.path.dirname(path) == str(_tmp_uploads)
    assert "/" not in shown and ".." not in shown.replace("...", "")


def test_bad_extension_rejected():
    with pytest.raises(UploadError):
        save_uploaded_file("script.py", b"print('hi')")


def test_empty_file_rejected():
    with pytest.raises(UploadError):
        save_uploaded_file("a.mp3", b"")


def test_too_large_rejected(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(
        uploads, "settings",
        SimpleNamespace(max_upload_mb=0, upload_retention_hours=24),
    )
    with pytest.raises(UploadError):
        save_uploaded_file("a.mp3", b"x")


def test_html_in_filename_is_neutralised():
    _, shown = save_uploaded_file("<script>alert(1)</script>.mp3", b"x")
    assert "<" not in shown and ">" not in shown


def test_cleanup_removes_only_old_files(_tmp_uploads):
    old_path, _ = save_uploaded_file("old.mp3", b"x")
    new_path, _ = save_uploaded_file("new.mp3", b"x")
    two_days_ago = time.time() - 48 * 3600
    os.utime(old_path, (two_days_ago, two_days_ago))
    assert cleanup_old_uploads(max_age_hours=24) >= 1
    assert not os.path.exists(old_path)
    assert os.path.exists(new_path)
