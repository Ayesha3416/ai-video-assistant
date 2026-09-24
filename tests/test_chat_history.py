"""Tests for core/chat_history.py -- no Groq, no Chroma, no Streamlit needed."""

from core.chat_history import (
    MAX_CHARS_PER_MESSAGE,
    MAX_HISTORY_MESSAGES,
    clean_rewrite,
    format_history_for_prompt,
    history_pairs,
)


def u(text):
    return {"role": "user", "content": text, "time": "10:00 AM"}


def a(text):
    return {"role": "assistant", "content": text, "time": "10:00 AM"}


def test_empty_or_none_history():
    assert history_pairs(None) == []
    assert history_pairs([]) == []


def test_drops_the_question_currently_being_answered():
    hist = [u("Who is the speaker?"), a("Dr. Rao [0:05]."), u("What did he say next?")]
    pairs = history_pairs(hist, current_question="What did he say next?")
    assert pairs == [("user", "Who is the speaker?"), ("assistant", "Dr. Rao [0:05].")]


def test_keeps_last_user_message_if_it_is_not_the_current_question():
    hist = [u("Who is the speaker?"), a("Dr. Rao.")]
    pairs = history_pairs(hist, current_question="What did he say next?")
    assert pairs[-1] == ("assistant", "Dr. Rao.")


def test_skips_typed_entries_and_the_request_that_produced_them():
    hist = [
        u("What is RAG?"),
        a("Retrieval-augmented generation."),
        u("show me 2:30"),
        {"role": "assistant", "type": "image", "content": "", "time": "10:01 AM"},
        u("quiz"),
        {"role": "assistant", "type": "quiz_count_prompt", "content": "How many?"},
    ]
    assert history_pairs(hist) == [
        ("user", "What is RAG?"),
        ("assistant", "Retrieval-augmented generation."),
    ]


def test_skips_pasted_video_source_and_status_messages():
    hist = [
        u("https://www.youtube.com/watch?v=abc123"),
        a("Done! I've analyzed **Some Title**. Ask me anything about it."),
        u("What is the main idea?"),
        a("Sorry, I couldn't process that question: rate limit"),
        u('"C:\\videos\\lecture 1.mp4"'),
        a("Something went wrong analyzing that: boom"),
    ]
    assert history_pairs(hist) == [("user", "What is the main idea?")]


def test_windowing_and_never_starts_with_assistant():
    hist = []
    for i in range(10):
        hist.append(u(f"question {i}"))
        hist.append(a(f"answer {i}"))
    pairs = history_pairs(hist)
    assert len(pairs) <= MAX_HISTORY_MESSAGES
    assert pairs[0][0] == "user"
    assert pairs[-1] == ("assistant", "answer 9")


def test_window_that_would_start_on_assistant_is_trimmed():
    hist = [u("q1"), a("a1"), u("q2"), a("a2")]
    pairs = history_pairs(hist, max_messages=3)  # slice = a1, q2, a2 -> drop a1
    assert pairs == [("user", "q2"), ("assistant", "a2")]


def test_long_messages_are_truncated():
    pairs = history_pairs([u("q"), a("x" * 5000)])
    text = pairs[1][1]
    assert len(text) <= MAX_CHARS_PER_MESSAGE + 3
    assert text.endswith("...")


def test_tolerates_garbage_entries():
    hist = [None, "oops", {"role": "system", "content": "x"}, {"role": "user"}, u("hi there")]
    assert history_pairs(hist) == [("user", "hi there")]


def test_format_history_for_prompt():
    text = format_history_for_prompt([("user", "hi"), ("assistant", "hello")])
    assert text == "User: hi\nAssistant: hello"


def test_clean_rewrite_plain():
    assert clean_rewrite("What did Dr. Rao say after the intro?", "and after that?") == (
        "What did Dr. Rao say after the intro?"
    )


def test_clean_rewrite_strips_quotes_labels_and_extra_lines():
    raw = '\n  Rewritten question: "What did Dr. Rao say next?"\nExtra explanation line.'
    assert clean_rewrite(raw, "and next?") == "What did Dr. Rao say next?"


def test_clean_rewrite_falls_back_on_empty_or_huge():
    assert clean_rewrite("", "orig?") == "orig?"
    assert clean_rewrite(None, "orig?") == "orig?"
    assert clean_rewrite("   \n  ", "orig?") == "orig?"
    assert clean_rewrite("x" * 2000, "orig?") == "orig?"
