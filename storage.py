"""
Памʼять бота: які новини вже опубліковано або пропущено.

Зберігається у файлі data/posted.json. GitHub Actions після кожного
запуску комітить цей файл у репозиторій, тож памʼять не губиться.
"""

import json
import os
from datetime import datetime, timezone

from news import normalize_url, title_key

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "posted.json")
KEEP_LAST = 800  # скільки останніх записів тримати у файлі


def load() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"posted": []}
    with open(STATE_FILE, encoding="utf-8") as f:
        state = json.load(f)
    state.setdefault("posted", [])
    return state


def save(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    state["posted"] = state["posted"][-KEEP_LAST:]
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_FILE)


def known_url_keys(state: dict) -> set[str]:
    return {entry.get("key") or normalize_url(entry["url"]) for entry in state["posted"]}


def known_title_keys(state: dict) -> set[str]:
    return {title_key(entry.get("title", "")) for entry in state["posted"] if entry.get("title")}


def recent_headlines(state: dict, limit: int = 40) -> list[str]:
    """Останні опубліковані заголовки — щоб AI не повторював ту саму тему."""
    published = [e for e in state["posted"] if e.get("status") == "posted"]
    return [e.get("headline") or e.get("title", "") for e in published[-limit:]]


def remember(state: dict, url: str, title: str, status: str, headline: str = "", topic: str = "") -> None:
    """status: "posted" — опубліковано, "skipped" — замало інформації, "failed" — помилка."""
    state["posted"].append(
        {
            "url": url,
            "key": normalize_url(url),
            "title": title,
            "headline": headline,
            "topic": topic,
            "status": status,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
