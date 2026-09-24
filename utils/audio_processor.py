import yt_dlp
from pydub import AudioSegment
import os

from config import get_logger
from config.paths import DOWNLOADS_DIR as _DOWNLOADS_DIR

log = get_logger(__name__)

# str(...) because callers os.path.join() this with plain strings below.
# Directory creation itself is handled once by config.ensure_runtime_dirs()
# at bootstrap, same as every other runtime directory. Spelling ("downloades")
# is intentional -- see config/paths.py.
DOWNLOAD_DIR = str(_DOWNLOADS_DIR)

def download_youtube_audio(url: str) -> str:
    log.info("Downloading YouTube audio...")

    output_path = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "quiet": False,
        "no_color": True,   # <-- prevents ANSI color codes from leaking into logs/errors
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info["id"]
    except Exception as e:
        raise RuntimeError(
            "Failed to download audio from YouTube. This can happen due to a "
            "network hiccup or if the video is unavailable/restricted. "
            "Please check the link and try again."
        )

    wav_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.wav")

    if not os.path.exists(wav_path):
        raise RuntimeError(
            "YouTube audio download failed. WAV file was not created."
        )

    if os.path.getsize(wav_path) == 0:
        raise RuntimeError(
            "YouTube audio file is empty. Please try another video."
        )

    log.info("Audio downloaded successfully: %s (%d bytes)", wav_path, os.path.getsize(wav_path))

    return wav_path

def convert_to_wav(input_path: str) -> str:
    """Convert any audio/video file to WAV format using pydub."""
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000) #16khz
    audio.export(output_path, format="wav")
    return output_path



def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list:
    audio = AudioSegment.from_wav(wav_path)

    if len(audio) == 0:
        raise RuntimeError(
            "The downloaded audio is empty. Please try another YouTube video."
        )

    log.info("Audio duration: %.2f seconds", len(audio) / 1000)

    chunk_ms = chunk_minutes * 60 * 1000
    chunks = []

    for i, start in enumerate(range(0, len(audio), chunk_ms)):
        chunk = audio[start:start + chunk_ms]

        if len(chunk) == 0:
            continue

        chunk_path = f"{wav_path}_chunk_{i}.wav"
        chunk.export(chunk_path, format="wav")

        if os.path.getsize(chunk_path) == 0:
            continue

        chunks.append(chunk_path)

    if not chunks:
        raise RuntimeError(
            "No valid audio chunks were created from the video."
        )

    log.info("Audio ready — %d valid chunk(s) created.", len(chunks))

    # The full downloaded/converted audio isn't needed once it's been split
    # into chunks -- only the chunks get transcribed. Deleting it here (not
    # on a timer) avoids downloades/ growing by one full audio file per
    # analysis forever. Chunk files themselves are deleted by the caller
    # (main.py) right after transcription uses them.
    try:
        os.remove(wav_path)
    except OSError as e:
        log.warning("Could not remove source audio %s after chunking: %s", wav_path, e)

    return chunks

def process_input(source: str, on_progress=None) -> list:
    def report(stage, msg):
        if on_progress:
            on_progress(stage, msg)

    if source.startswith("http://") or source.startswith("https://"):
        report("downloading", "Downloading audio from YouTube...")
        wav_path = download_youtube_audio(source)
    else:
        report("downloading", "Loading local file...")
        wav_path = convert_to_wav(source)

    report("processing_audio", "Splitting audio into chunks...")
    chunks = chunk_audio(wav_path)
    report("processing_audio", f"Audio ready — {len(chunks)} chunk(s) created.")
    return chunks