"""Tests for core/notes_generator.py -- the Groq call (_ask_llm) is mocked."""

import json

import pytest

from core import notes_generator as ng


def _notes(title, *headings):
    return json.dumps({
        "title": title,
        "sections": [{"heading": h, "bullets": [f"point about {h}"]} for h in headings],
    })


def test_no_content_raises():
    with pytest.raises(ValueError):
        ng.generate_notes("")


def test_short_transcript_makes_one_call_and_keeps_title(monkeypatch):
    calls = []

    def fake_ask(chunk, max_sections):
        calls.append((chunk, max_sections))
        return _notes("My Video", "Intro", "Key idea")

    monkeypatch.setattr(ng, "_ask_llm", fake_ask)
    monkeypatch.setattr(ng, "select_chunks", lambda content, max_chunks, size: ["one short chunk"])
    notes = ng.generate_notes("a short transcript")

    assert len(calls) == 1
    assert notes["title"] == "My Video"
    assert [s["heading"] for s in notes["sections"]] == ["Intro", "Key idea"]


def test_long_transcript_sections_stay_in_video_order(monkeypatch):
    monkeypatch.setattr(ng, "select_chunks", lambda content, max_chunks, size: ["chunk-A", "chunk-B", "chunk-C"])
    monkeypatch.setattr(ng, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))

    def fake_ask(chunk, max_sections):
        letter = chunk.split("-")[1]
        return _notes(f"Title from {letter}", f"{letter} section 1", f"{letter} section 2")

    monkeypatch.setattr(ng, "_ask_llm", fake_ask)
    notes = ng.generate_notes("a very long transcript")

    headings = [s["heading"] for s in notes["sections"]]
    # concatenated IN ORDER (not interleaved like the quiz) -- notes should read start to end
    assert headings == [
        "A section 1", "A section 2", "B section 1", "B section 2", "C section 1", "C section 2",
    ]
    assert notes["title"] == "Title from A"  # first successful chunk's title wins


def test_total_sections_capped_across_chunks(monkeypatch):
    monkeypatch.setattr(ng, "select_chunks", lambda content, max_chunks, size: ["chunk-A", "chunk-B", "chunk-C", "chunk-D"])
    monkeypatch.setattr(ng, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))
    monkeypatch.setattr(
        ng, "_ask_llm",
        lambda chunk, max_sections: _notes("T", *[f"{chunk}-s{i}" for i in range(max_sections)]),
    )
    notes = ng.generate_notes("text")
    assert len(notes["sections"]) <= ng.MAX_TOTAL_SECTIONS


def test_one_bad_chunk_does_not_fail_the_whole_notes(monkeypatch):
    monkeypatch.setattr(ng, "select_chunks", lambda content, max_chunks, size: ["chunk-A", "chunk-B"])
    monkeypatch.setattr(ng, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))

    def flaky_ask(chunk, max_sections):
        if "A" in chunk:
            return "not valid json"
        return _notes("Title", "Good section")

    monkeypatch.setattr(ng, "_ask_llm", flaky_ask)
    notes = ng.generate_notes("text")
    assert [s["heading"] for s in notes["sections"]] == ["Good section"]


def test_all_chunks_failing_raises(monkeypatch):
    monkeypatch.setattr(ng, "select_chunks", lambda content, max_chunks, size: ["chunk-A"])
    monkeypatch.setattr(ng, "_ask_llm", lambda chunk, max_sections: "not valid json")
    with pytest.raises(ValueError):
        ng.generate_notes("text")


def test_missing_title_falls_back_to_video_notes(monkeypatch):
    raw = json.dumps({"sections": [{"heading": "H", "bullets": ["b"]}]})
    monkeypatch.setattr(ng, "select_chunks", lambda content, max_chunks, size: ["chunk"])
    monkeypatch.setattr(ng, "_ask_llm", lambda chunk, max_sections: raw)
    notes = ng.generate_notes("text")
    assert notes["title"] == "Video Notes"


def test_build_notes_pdf_still_works():
    notes = {"title": "T", "sections": [{"heading": "H", "bullets": ["b1", "b2"]}]}
    pdf_bytes = ng.build_notes_pdf(notes, video_title="V")
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
