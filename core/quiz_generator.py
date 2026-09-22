import json
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from core.llm import get_llm, invoke_with_retry


QUIZ_SYSTEM_PROMPT = """You are a quiz-writing assistant. Based on the video transcript/summary given, \
write exactly {n} multiple-choice quiz questions that test understanding of the video's content.

Respond with ONLY a valid JSON array (no markdown fences, no extra text) where each item has this exact shape:
{{
  "question": "...",
  "options": ["...", "...", "...", "..."],
  "correct_index": 0
}}

Rules:
- Exactly 4 options per question, only one of them correct.
- correct_index is the 0-based index of the correct option within "options".
- Questions must be answerable from the given content only — do not invent facts.
- Do not repeat the same question twice.
- Output ONLY the JSON array, nothing else, no commentary before or after it."""


def _extract_json_array(raw: str) -> str:
    """Strips ``` / ```json fences in case the model adds them despite instructions."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return raw


def generate_quiz(content: str, num_questions: int) -> list:
    """content: transcript (preferred) or summary text to base the quiz on.
    Returns a list of dicts: {"question": str, "options": [str, str, str, str], "correct_index": int}.
    Raises ValueError if the model's output can't be parsed into that shape.
    """
    llm = get_llm(temperature=0.4)
    prompt = ChatPromptTemplate.from_messages([
        ("system", QUIZ_SYSTEM_PROMPT),
        ("human", "{text}"),
    ])
    chain = prompt | llm | StrOutputParser()

    # Cap input size the same way the other core modules do for long transcripts.
    raw = invoke_with_retry(chain, {"text": content[:6000], "n": num_questions})
    cleaned = _extract_json_array(raw)

    try:
        questions = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse the quiz response as JSON: {e}\nRaw response: {raw[:300]}")

    if not isinstance(questions, list) or not questions:
        raise ValueError("The quiz response was not a non-empty list of questions.")

    # Defensive normalization in case the model returns slightly malformed items.
    cleaned_questions = []
    for q in questions[:num_questions]:
        if not isinstance(q, dict):
            continue
        options = q.get("options")
        question_text = q.get("question")
        correct_index = q.get("correct_index")
        if (
            isinstance(question_text, str)
            and isinstance(options, list)
            and len(options) >= 2
            and isinstance(correct_index, int)
            and 0 <= correct_index < len(options)
        ):
            cleaned_questions.append({
                "question": question_text,
                "options": options,
                "correct_index": correct_index,
            })

    if not cleaned_questions:
        raise ValueError("The quiz response didn't contain any well-formed questions.")

    return cleaned_questions