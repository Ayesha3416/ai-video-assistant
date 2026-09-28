"""Tests for core/flashcard_utils.py -- pure logic, no LLM/DB."""

import pytest

from core.flashcard_utils import (
    card_key,
    cards_from_quiz_mistakes,
    chunk_text,
    dedupe_cards,
    interleave,
    parse_cards,
    select_chunks,
)


# ------------------------------------------------------------------ card_key ---
def test_card_key_stable_across_case_and_whitespace():
    a = card_key("What is  RAG?")
    b = card_key("  what is rag? ")
    assert a == b


def test_card_key_differs_for_different_questions():
    assert card_key("What is RAG?") != card_key("What is a vector store?")


def test_dedupe_cards_keeps_first_occurrence():
    cards = [
        {"front": "What is RAG?", "back": "Retrieval-augmented generation."},
        {"front": "what is rag?", "back": "A DIFFERENT (duplicate) answer."},
        {"front": "What is chunking?", "back": "Splitting text into pieces."},
    ]
    out = dedupe_cards(cards)
    assert len(out) == 2
    assert out[0]["back"] == "Retrieval-augmented generation."


# -------------------------------------------------------------- parse_cards ---
def test_parse_cards_plain_json():
    raw = '[{"front": "Q1", "back": "A1"}, {"front": "Q2", "back": "A2"}]'
    assert parse_cards(raw) == [{"front": "Q1", "back": "A1"}, {"front": "Q2", "back": "A2"}]


def test_parse_cards_strips_markdown_fence():
    raw = '```json\n[{"front": "Q1", "back": "A1"}]\n```'
    assert parse_cards(raw) == [{"front": "Q1", "back": "A1"}]


def test_parse_cards_unwraps_object_wrapper():
    raw = '{"flashcards": [{"front": "Q1", "back": "A1"}]}'
    assert parse_cards(raw) == [{"front": "Q1", "back": "A1"}]


def test_parse_cards_drops_malformed_items():
    raw = '[{"front": "Q1", "back": "A1"}, {"front": "no back"}, {"front": "", "back": "empty front"}, "garbage"]'
    assert parse_cards(raw) == [{"front": "Q1", "back": "A1"}]


def test_parse_cards_empty_array_is_fine():
    assert parse_cards("[]") == []


def test_parse_cards_invalid_json_raises():
    with pytest.raises(ValueError):
        parse_cards("not json at all")


def test_parse_cards_non_list_non_wrapper_raises():
    with pytest.raises(ValueError):
        parse_cards('{"unexpected": "shape"}')


def test_parse_cards_truncates_overlong_fields():
    raw = f'[{{"front": "{"x" * 1000}", "back": "{"y" * 2000}"}}]'
    cards = parse_cards(raw)
    assert len(cards[0]["front"]) == 400
    assert len(cards[0]["back"]) == 800


# --------------------------------------------------------------- chunk_text ---
def test_chunk_text_short_text_is_one_chunk():
    assert chunk_text("short text", size=100) == ["short text"]


def test_chunk_text_empty_is_no_chunks():
    assert chunk_text("", size=100) == []
    assert chunk_text(None, size=100) == []


def test_chunk_text_splits_at_whitespace_not_mid_word():
    text = "word " * 50  # 250 chars
    chunks = chunk_text(text, size=100)
    assert len(chunks) > 1
    for c in chunks:
        assert not c.endswith("wor")  # never cut mid-word
        assert c == c.strip()


def test_chunk_text_covers_the_whole_text():
    text = "abcdefgh " * 40
    chunks = chunk_text(text, size=50)
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


# -------------------------------------------------------------- select_chunks ---
def test_select_chunks_returns_all_when_fewer_than_max():
    text = "word " * 10
    assert select_chunks(text, max_chunks=4, size=1000) == chunk_text(text, size=1000)


def test_select_chunks_spreads_across_whole_text_not_just_the_start():
    text = "".join(f"chunk{i} " * 20 for i in range(10))  # many small chunks
    all_chunks = chunk_text(text, size=100)
    assert len(all_chunks) > 4
    picked = select_chunks(text, max_chunks=4, size=100)
    assert len(picked) == 4
    assert picked[0] == all_chunks[0]
    assert picked[-1] == all_chunks[-1]  # reaches the END, not just the first 4


def test_select_chunks_max_chunks_one():
    text = "word " * 100
    picked = select_chunks(text, max_chunks=1, size=50)
    assert len(picked) == 1


# ----------------------------------------------------------------- interleave ---
def test_interleave_round_robin():
    assert interleave([["a1", "a2"], ["b1", "b2", "b3"]]) == ["a1", "b1", "a2", "b2", "b3"]


def test_interleave_empty_lists():
    assert interleave([]) == []
    assert interleave([[], []]) == []


def test_interleave_single_list():
    assert interleave([["a", "b", "c"]]) == ["a", "b", "c"]


# --------------------------------------------------------- quiz -> flashcards ---
QUESTIONS = [
    {"question": "Capital of France?", "options": ["London", "Paris", "Rome", "Berlin"], "correct_index": 1},
    {"question": "2 + 2?", "options": ["3", "4", "5", "6"], "correct_index": 1},
    {"question": "Largest planet?", "options": ["Earth", "Mars", "Jupiter", "Venus"], "correct_index": 2},
]


def test_cards_from_quiz_mistakes_only_wrong_and_skipped():
    # Q1 correct, Q2 wrong, Q3 skipped
    cards = cards_from_quiz_mistakes(QUESTIONS, [1, 0, None])
    assert len(cards) == 2
    assert cards[0] == {"front": "2 + 2?", "back": "4"}
    assert cards[1] == {"front": "Largest planet?", "back": "Jupiter"}


def test_cards_from_quiz_mistakes_all_correct_gives_nothing():
    assert cards_from_quiz_mistakes(QUESTIONS, [1, 1, 2]) == []


def test_cards_from_quiz_mistakes_tolerates_short_answers_list():
    cards = cards_from_quiz_mistakes(QUESTIONS, [1])  # Q2, Q3 implicitly skipped
    assert len(cards) == 2


def test_cards_from_quiz_mistakes_tolerates_garbage_questions():
    bad = [None, {"question": "ok?"}, {"question": "q", "options": ["a"], "correct_index": 5}]
    assert cards_from_quiz_mistakes(bad, [0, 0, 0]) == []


def test_cards_from_quiz_mistakes_empty_input():
    assert cards_from_quiz_mistakes([], []) == []
    assert cards_from_quiz_mistakes(None, None) == []
