import os
import subprocess
import uuid

import yt_dlp

from config import get_logger
from config.paths import FRAMES_DIR as _FRAMES_DIR

log = get_logger(__name__)

# str(...) because callers os.path.join() this with plain strings below.
# Directory creation itself is handled once by config.ensure_runtime_dirs()
# at bootstrap, same as every other runtime directory.
FRAMES_DIR = str(_FRAMES_DIR)


def _is_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


def _resolve_stream_url(source: str) -> str:
    """For YouTube URLs, resolve the direct, playable video stream URL via
    yt-dlp WITHOUT downloading the file — ffmpeg can then seek directly into
    that stream. For local files, the path is returned unchanged.

    This is resolved fresh on every call (not cached) since YouTube's direct
    stream URLs are signed and expire after a while.
    """
    if not _is_url(source):
        if not os.path.exists(source):
            raise FileNotFoundError(
                f"The original video file isn't available anymore at: {source}"
            )
        return source

    # Explicitly require a PROGRESSIVE format (both audio+video already
    # merged into one file, one single URL). Modern YouTube often only
    # offers separate video-only + audio-only streams at higher quality
    # (DASH/adaptive) — a bare "best" selector can resolve to one of those,
    # which has no single info["url"], only info["requested_formats"] with
    # two URLs needing an ffmpeg merge. We don't need audio for a frame grab
    # anyway, so we ask for progressive first, and fall back to video-only.
    ydl_opts = {
        "format": (
            "best[acodec!=none][vcodec!=none][ext=mp4]/"
            "best[acodec!=none][vcodec!=none]/"
            "bestvideo[ext=mp4]/bestvideo/best"
        ),
        "quiet": True,
        "no_color": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(source, download=False)
    except Exception as e:
        log.warning("yt-dlp extract_info failed for %r: %r", source, e)
        raise RuntimeError(
            "Couldn't reach that video to grab a frame from it. It may have "
            "been removed, made private, or there's a network issue."
        ) from e

    if info.get("url"):
        return info["url"]
    if info.get("requested_formats"):
        return info["requested_formats"][0]["url"]

    log.warning("No usable stream URL in yt-dlp info for %r: keys=%s", source, list(info.keys()))
    raise RuntimeError(
        "Couldn't find a playable video stream for that source."
    )


def extract_frame(source: str, timestamp_seconds: float) -> str:
    """Extract a single frame at timestamp_seconds from the video `source`
    (YouTube URL or local file path). Returns the path to the saved JPEG.

    Raises RuntimeError / FileNotFoundError with a user-friendly message on
    failure (source unreachable, no video track, bad timestamp, etc).
    """
    if timestamp_seconds < 0:
        raise ValueError("Timestamp can't be negative.")

    stream_url = _resolve_stream_url(source)

    out_path = os.path.join(FRAMES_DIR, f"frame_{uuid.uuid4().hex}.jpg")

    # -ss before -i: fast seek to the nearest keyframe, avoids downloading/
    # decoding everything before the target timestamp — important since we're
    # seeking into a remote stream, not a local file we already have on disk.
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp_seconds),
        "-i", stream_url,
        "-frames:v", "1",
        "-q:v", "2",
        out_path,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "Grabbing that frame took too long and timed out. Please try again."
        )

    if result.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        stderr_tail = (result.stderr or "")[-400:]
        raise RuntimeError(
            "Couldn't extract a frame at that timestamp — the source may not "
            f"have a video track, or the timestamp may be past the end of the video.\n{stderr_tail}"
        )

    return out_path