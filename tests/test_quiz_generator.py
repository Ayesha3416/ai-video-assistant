"""Tests for core/quiz_generator.py -- the Groq call (_ask_llm) is mocked."""

import json

import pytest

from core import quiz_generator as qg


def _q(text, correct="B"):
    opts = ["A", "B", "C", "D"]
    return {"question": text, "options": opts, "correct_index": opts.index(correct)}


def test_no_content_raises(monkeypatch):
    with pytest.raises(ValueError):
        qg.generate_quiz("", num_questions=5)


def test_short_transcript_makes_one_call(monkeypatch):
    calls = []

    def fake_ask(chunk, n):
        calls.append((chunk, n))
        return json.dumps([_q("Q1"), _q("Q2")])

    monkeypatch.setattr(qg, "_ask_llm", fake_ask)
    monkeypatch.setattr(qg, "select_chunks", lambda content, max_chunks, size: ["one short chunk"])
    questions = qg.generate_quiz("a short transcript", num_questions=5)

    assert len(calls) == 1
    assert [q["question"] for q in questions] == ["Q1", "Q2"]


def test_long_transcript_covers_multiple_chunks(monkeypatch):
    monkeypatch.setattr(qg, "select_chunks", lambda content, max_chunks, size: ["chunk-A", "chunk-B", "chunk-C"])
    monkeypatch.setattr(qg, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))

    def fake_ask(chunk, n):
        letter = chunk.split("-")[1]
        return json.dumps([_q(f"{letter}1"), _q(f"{letter}2")])

    monkeypatch.setattr(qg, "_ask_llm", fake_ask)
    questions = qg.generate_quiz("a very long transcript", num_questions=6)

    fronts = [q["question"] for q in questions]
    assert fronts[0] == "A1" and fronts[1] == "B1" and fronts[2] == "C1"  # spread across chunks
    assert len(fronts) == 6


def test_result_is_truncated_to_num_questions(monkeypatch):
    monkeypatch.setattr(qg, "select_chunks", lambda content, max_chunks, size: ["chunk"])
    monkeypatch.setattr(qg, "_ask_llm", lambda chunk, n: json.dumps([_q(f"Q{i}") for i in range(20)]))
    questions = qg.generate_quiz("text", num_questions=5)
    assert len(questions) == 5


def test_duplicate_questions_across_chunks_are_removed(monkeypatch):
    monkeypatch.setattr(qg, "select_chunks", lambda content, max_chunks, size: ["chunk-A", "chunk-B"])
    monkeypatch.setattr(qg, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))
    monkeypatch.setattr(qg, "_ask_llm", lambda chunk, n: json.dumps([_q("  Same Question? "), _q("Unique")]))
    questions = qg.generate_quiz("text", num_questions=10)
    texts = [q["question"] for q in questions]
    assert texts.count("  Same Question? ") + texts.count("Same Question?") == 1


def test_one_bad_chunk_does_not_fail_the_whole_quiz(monkeypatch):
    monkeypatch.setattr(qg, "select_chunks", lambda content, max_chunks, size: ["chunk-A", "chunk-B"])
    monkeypatch.setattr(qg, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))

    def flaky_ask(chunk, n):
        if "A" in chunk:
            return "not valid json"
        return json.dumps([_q("Good question")])

    monkeypatch.setattr(qg, "_ask_llm", flaky_ask)
    questions = qg.generate_quiz("text", num_questions=5)
    assert [q["question"] for q in questions] == ["Good question"]


def test_all_chunks_failing_raises(monkeypatch):
    monkeypatch.setattr(qg, "select_chunks", lambda content, max_chunks, size: ["chunk-A"])
    monkeypatch.setattr(qg, "_ask_llm", lambda chunk, n: "not valid json")
    with pytest.raises(ValueError):
        qg.generate_quiz("text", num_questions=5)


def test_malformed_items_within_a_chunk_are_dropped(monkeypatch):
    monkeypatch.setattr(qg, "select_chunks", lambda content, max_chunks, size: ["chunk"])
    raw = json.dumps([_q("Good"), {"question": "missing options"}, {"question": "", "options": []}])
    monkeypatch.setattr(qg, "_ask_llm", lambda chunk, n: raw)
    questions = qg.generate_quiz("text", num_questions=5)
    assert [q["question"] for q in questions] == ["Good"]
