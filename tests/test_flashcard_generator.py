"""Tests for core/flashcard_generator.py -- the actual Groq call (_ask_llm) is mocked."""

import json

import pytest

from core import flashcard_generator as fg


def _cards_json(*fronts):
    return json.dumps([{"front": f, "back": f"answer for {f}"} for f in fronts])


def test_no_content_raises(monkeypatch):
    monkeypatch.setattr(fg, "_ask_llm", lambda chunk, n: _cards_json("Q"))
    with pytest.raises(ValueError):
        fg.generate_flashcards("", num_cards=5)


def test_short_transcript_makes_one_call(monkeypatch):
    calls = []

    def fake_ask(chunk, n):
        calls.append((chunk, n))
        return _cards_json("Q1", "Q2", "Q3")

    monkeypatch.setattr(fg, "_ask_llm", fake_ask)
    monkeypatch.setattr(fg, "select_chunks", lambda content, max_chunks, size: ["one short chunk"])
    cards = fg.generate_flashcards("a short transcript", num_cards=10)

    assert len(calls) == 1
    assert cards == [
        {"front": "Q1", "back": "answer for Q1"},
        {"front": "Q2", "back": "answer for Q2"},
        {"front": "Q3", "back": "answer for Q3"},
    ]


def test_long_transcript_covers_multiple_chunks(monkeypatch):
    monkeypatch.setattr(fg, "select_chunks", lambda content, max_chunks, size: ["chunk-A", "chunk-B", "chunk-C"])
    monkeypatch.setattr(fg, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))

    def fake_ask(chunk, n):
        letter = chunk.split("-")[1]
        return _cards_json(f"{letter}1", f"{letter}2")

    monkeypatch.setattr(fg, "_ask_llm", fake_ask)
    cards = fg.generate_flashcards("a very long transcript", num_cards=6)

    fronts = [c["front"] for c in cards]
    # interleaved -> not all of one chunk's cards before another's
    assert fronts[0] == "A1" and fronts[1] == "B1" and fronts[2] == "C1"
    assert len(fronts) == 6


def test_result_is_truncated_to_num_cards(monkeypatch):
    monkeypatch.setattr(fg, "select_chunks", lambda content, max_chunks, size: ["chunk"])
    monkeypatch.setattr(fg, "_ask_llm", lambda chunk, n: _cards_json(*[f"Q{i}" for i in range(20)]))
    cards = fg.generate_flashcards("text", num_cards=5)
    assert len(cards) == 5


def test_duplicate_cards_across_chunks_are_removed(monkeypatch):
    monkeypatch.setattr(fg, "select_chunks", lambda content, max_chunks, size: ["chunk-A", "chunk-B"])
    monkeypatch.setattr(fg, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))
    monkeypatch.setattr(fg, "_ask_llm", lambda chunk, n: _cards_json("Same question?", "Unique to chunk"))
    cards = fg.generate_flashcards("text", num_cards=10)
    fronts = [c["front"] for c in cards]
    assert fronts.count("Same question?") == 1


def test_one_bad_chunk_does_not_fail_the_whole_generation(monkeypatch):
    monkeypatch.setattr(fg, "select_chunks", lambda content, max_chunks, size: ["chunk-A", "chunk-B"])
    monkeypatch.setattr(fg, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))

    def flaky_ask(chunk, n):
        if "A" in chunk:
            return "not valid json"
        return _cards_json("Good question")

    monkeypatch.setattr(fg, "_ask_llm", flaky_ask)
    cards = fg.generate_flashcards("text", num_cards=5)
    assert cards == [{"front": "Good question", "back": "answer for Good question"}]


def test_all_chunks_failing_raises(monkeypatch):
    monkeypatch.setattr(fg, "select_chunks", lambda content, max_chunks, size: ["chunk-A"])
    monkeypatch.setattr(fg, "_ask_llm", lambda chunk, n: "not valid json")
    with pytest.raises(ValueError):
        fg.generate_flashcards("text", num_cards=5)
