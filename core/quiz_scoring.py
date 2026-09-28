"""Pure helpers for quiz attempts (Step 2 / issue I-02).

No database, no Streamlit -- so everything here is trivially unit-testable.
``utils/quiz_attempts.py`` does the persistence; ``ui/quiz_progress.py`` does
the rendering; both lean on these functions.

An *attempt dict* (what ``utils.quiz_attempts.get_attempts`` returns) looks like::

    {"id": 7, "video_title": "...", "num_questions": 10, "score": 8,
     "percent": 80.0, "timestamp": "2026-09-24 18:03", ...}
"""

from __future__ import annotations

import pandas as pd


def score_answers(questions, answers) -> int:
    """Number of questions answered correctly.

    ``answers[i]`` is the option index the user picked for ``questions[i]``, or
    ``None`` if they skipped it (a skipped question is simply not correct).
    Extra or missing answers are tolerated.
    """
    score = 0
    for i, q in enumerate(questions):
        if i >= len(answers):
            break
        picked = answers[i]
        if picked is not None and picked == q.get("correct_index"):
            score += 1
    return score


def percent(score: int, total: int) -> float:
    """``score / total`` as a percentage rounded to 1 decimal (0.0 if total<=0)."""
    if not total or total <= 0:
        return 0.0
    return round(100.0 * score / total, 1)


def summarize_attempts(attempts: list[dict]) -> dict:
    """Headline numbers for the stat cards. ``attempts`` is newest-first.

    The average gives every attempt equal weight (a 5-question quiz counts the
    same as a 20-question one), which is what "how am I doing" usually means.
    """
    if not attempts:
        return {
            "attempts": 0,
            "average_percent": 0.0,
            "best_percent": 0.0,
            "latest_percent": 0.0,
        }
    percents = [a["percent"] for a in attempts]
    return {
        "attempts": len(attempts),
        "average_percent": round(sum(percents) / len(percents), 1),
        "best_percent": max(percents),
        "latest_percent": attempts[0]["percent"],
    }


TREND_COLUMNS = ["attempt", "when", "percent", "video", "score", "out_of"]


def trend_dataframe(attempts: list[dict]) -> pd.DataFrame:
    """Chronological DataFrame for the score-trend line chart.

    ``attempts`` comes in newest-first (as the DB returns it); the frame is
    oldest-first with ``attempt`` numbered 1..n.
    """
    if not attempts:
        return pd.DataFrame(columns=TREND_COLUMNS)

    rows = []
    for n, a in enumerate(reversed(attempts), start=1):
        rows.append(
            {
                "attempt": n,
                "when": a.get("timestamp", ""),
                "percent": a["percent"],
                "video": a.get("video_title") or "Untitled video",
                "score": a.get("score", 0),
                "out_of": a.get("num_questions", 0),
            }
        )
    return pd.DataFrame(rows, columns=TREND_COLUMNS)
