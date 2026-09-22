import whisper
import os
import requests
from pydub import AudioSegment

from config import get_logger, settings

log = get_logger(__name__)

# Sarvam's sync STT-translate API rejects audio longer than 30s.
# We slice each chunk into 25s pieces (with a 5s safety margin) before sending.
SARVAM_PIECE_SECONDS = 25


WHISPER_MODEL = settings.whisper_model


SARVAM_API_KEY = settings.sarvam_api_key
SARVAM_STT_TRANSLATE_URL = "https://api.sarvam.ai/speech-to-text-translate"
SARVAM_MODEL = settings.sarvam_model


def _get_sarvam_model_name() -> str:
    return SARVAM_MODEL

_model = None


def load_model():

    global _model

    if _model is None:
        log.info("Loading Whisper model: %s ...", WHISPER_MODEL)
        _model = whisper.load_model(WHISPER_MODEL)
        log.info("Whisper model loaded.")
    return _model


def transcribe_chunk_whisper(chunk_path: str, model) -> str:
    if not os.path.exists(chunk_path):
        raise RuntimeError(f"Audio chunk not found: {chunk_path}")

    if os.path.getsize(chunk_path) == 0:
        raise RuntimeError(f"Audio chunk is empty: {chunk_path}")

    log.info("Transcribing: %s", chunk_path)

    result = model.transcribe(
        chunk_path,
        task="transcribe",
        fp16=False
    )

    return result["text"].strip()


def _send_to_sarvam(piece_path: str) -> str:
    headers = {"api-subscription-key": SARVAM_API_KEY}

    with open(piece_path, "rb") as f:
        files = {"file": (os.path.basename(piece_path), f, "audio/wav")}
        data = {"model": _get_sarvam_model_name(), "with_diarization": "false"}
        response = requests.post(
            SARVAM_STT_TRANSLATE_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=120,
        )

    if not response.ok:
        log.error("Sarvam returned %s. Response body: %s", response.status_code, response.text)
        response.raise_for_status()

    return response.json().get("transcript", "")


def transcribe_chunk_sarvam(chunk_path: str) -> str:
    """
    Sarvam sync API only accepts <=30s audio. We split this chunk into
    25-second pieces, send each separately, and join the transcripts.
    """
    if not SARVAM_API_KEY:
        raise RuntimeError("SARVAM_API_KEY is not set in environment / .env")

    audio = AudioSegment.from_wav(chunk_path)
    piece_ms = SARVAM_PIECE_SECONDS * 1000

    full_text = ""
    total_pieces = (len(audio) + piece_ms - 1) // piece_ms

    for i, start in enumerate(range(0, len(audio), piece_ms)):
        piece = audio[start: start + piece_ms]
        piece_path = f"{chunk_path}_sv_{i}.wav"
        piece.export(piece_path, format="wav")

        try:
            log.info("Sarvam piece %d/%d ...", i + 1, total_pieces)
            full_text += _send_to_sarvam(piece_path) + " "
        finally:
            if os.path.exists(piece_path):
                os.remove(piece_path)

    return full_text.strip()


def transcribe_chunk(chunk_path: str, language: str = "english") -> str:
    """
    Route one chunk to Whisper or Sarvam depending on language choice.
    - english  -> Whisper (local model)
    - hinglish -> Sarvam (translates to English while transcribing)
    """
    if language.lower() == "hinglish":
        return transcribe_chunk_sarvam(chunk_path)
    return transcribe_chunk_whisper(chunk_path)


def transcribe_hinglish(chunks: list) -> str:
    """Transcribe (and translate) every chunk via Sarvam, then join them."""
    transcripts = []

    for i, chunk in enumerate(chunks, start=1):
        log.info("Transcribing chunk %d/%d via Sarvam...", i, len(chunks))
        text = transcribe_chunk_sarvam(chunk)
        transcripts.append(text)

    return "\n".join(transcripts)


def transcribe_all(chunks: list, language: str = "english", on_progress=None) -> str:
    def report(stage, msg):
        if on_progress:
            on_progress(stage, msg)

    if language == "english":
        report("loading_whisper", "Loading Whisper model (first run only)...")
        model = load_model()
        report("loading_whisper", "Whisper model ready.")

        transcripts = []
        for i, chunk in enumerate(chunks, start=1):
            report("transcribing", f"Transcribing chunk {i}/{len(chunks)}...")
            text = transcribe_chunk_whisper(chunk, model)
            transcripts.append(text)

        return "\n".join(transcripts)

    elif language == "hinglish":
        transcripts = []
        for i, chunk in enumerate(chunks, start=1):
            report("transcribing", f"Transcribing chunk {i}/{len(chunks)} via Sarvam...")
            text = transcribe_chunk_sarvam(chunk)
            transcripts.append(text)
        return "\n".join(transcripts)

    else:
        raise ValueError(f"Unsupported language: {language}")


def transcribe_chunk_whisper_with_segments(chunk_path: str, model) -> tuple[str, list]:
    """Same as transcribe_chunk_whisper, but also returns Whisper's per-segment
    timestamps (chunk-local seconds) instead of discarding them.
    """
    if not os.path.exists(chunk_path):
        raise RuntimeError(f"Audio chunk not found: {chunk_path}")

    if os.path.getsize(chunk_path) == 0:
        raise RuntimeError(f"Audio chunk is empty: {chunk_path}")

    log.info("Transcribing: %s", chunk_path)

    result = model.transcribe(
        chunk_path,
        task="transcribe",
        fp16=False
    )

    segments = [
        {
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
        }
        for seg in result.get("segments", [])
    ]

    return result["text"].strip(), segments


def transcribe_all_with_segments(
    chunks: list,
    language: str = "english",
    chunk_minutes: int = 10,
    on_progress=None,
) -> dict:
    """Additive alternative to transcribe_all().

    Returns {"text": <plain transcript, same format as transcribe_all()>,
             "segments": <list of {start, end, text} with ABSOLUTE video
             timestamps in seconds, English/Whisper only>}.

    IMPORTANT: chunk_minutes must match whatever chunk_minutes value was
    passed to audio_processor.chunk_audio() when the chunks were created —
    it's used to offset each chunk's local timestamps into absolute
    video-relative timestamps. The default (10) matches chunk_audio()'s
    own default, so if that wasn't overridden, this is already correct.

    Hinglish (Sarvam) has no known per-segment timing available from that
    API, so for language="hinglish" this returns the same plain text as
    transcribe_all() with an empty segments list — timestamp citation
    simply won't be available for those videos, exactly as agreed.
    """
    def report(stage, msg):
        if on_progress:
            on_progress(stage, msg)

    if language == "english":
        report("loading_whisper", "Loading Whisper model (first run only)...")
        model = load_model()
        report("loading_whisper", "Whisper model ready.")

        transcripts = []
        all_segments = []
        chunk_offset_seconds = 0

        for i, chunk in enumerate(chunks, start=1):
            report("transcribing", f"Transcribing chunk {i}/{len(chunks)}...")
            text, chunk_segments = transcribe_chunk_whisper_with_segments(chunk, model)
            transcripts.append(text)

            for seg in chunk_segments:
                all_segments.append(
                    {
                        "start": seg["start"] + chunk_offset_seconds,
                        "end": seg["end"] + chunk_offset_seconds,
                        "text": seg["text"],
                    }
                )

            chunk_offset_seconds += chunk_minutes * 60

        return {"text": "\n".join(transcripts), "segments": all_segments}

    elif language == "hinglish":
        # No reliable per-segment timing available from Sarvam — plain text only.
        text = transcribe_hinglish(chunks)
        return {"text": text, "segments": []}

    else:
        raise ValueError(f"Unsupported language: {language}")