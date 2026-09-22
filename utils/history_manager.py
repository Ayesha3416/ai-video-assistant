import json
import os
from datetime import datetime
import pandas as pd

from config.paths import DATA_DIR, HISTORY_JSON

HISTORY_FILE = str(HISTORY_JSON)


def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _load() -> dict:
    _ensure_file()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def add_entry(user_email: str, title: str, source: str, summary: str, language: str = "english", category: str = "Other"):
    data = _load()
    data.setdefault(user_email, [])
    data[user_email].insert(0, {
        "title": title,
        "source": source,
        "language": language,
        "category": category,
        "summary_snippet": summary[:150] + ("..." if len(summary) > 150 else ""),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    data[user_email] = data[user_email][:50]
    _save(data)

def get_history(user_email: str) -> list:
    data = _load()
    return data.get(user_email, [])


def get_stats(user_email: str) -> dict:
    history = get_history(user_email)
    return {
        "total_analyzed": len(history),
        "last_activity": history[0]["timestamp"] if history else "No activity yet",
    }


def get_activity_dataframe(user_email: str) -> pd.DataFrame:
    history = get_history(user_email)
    if not history:
        return pd.DataFrame(columns=["date", "count"])

    dates = [item["timestamp"].split(" ")[0] for item in history]
    df = pd.DataFrame({"date": dates})
    counts = df.groupby("date").size().reset_index(name="count")
    counts = counts.sort_values("date")
    return counts


def get_language_dataframe(user_email: str) -> pd.DataFrame:
    history = get_history(user_email)
    if not history:
        return pd.DataFrame(columns=["language", "count"])

    langs = [item.get("language", "english") for item in history]
    df = pd.DataFrame({"language": langs})
    counts = df.groupby("language").size().reset_index(name="count")
    return counts

def get_category_dataframe(user_email: str) -> pd.DataFrame:
    history = get_history(user_email)
    if not history:
        return pd.DataFrame(columns=["category", "count"])

    cats = [item.get("category", "Other") for item in history]
    df = pd.DataFrame({"category": cats})
    counts = df.groupby("category").size().reset_index(name="count")
    return counts