"""
Робота з AI. Підтримує два провайдери — Gemini і Claude,
перемикаються в config.py одним рядком (AI_PROVIDER).
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import requests

import config
import prompts
from news import NewsItem

log = logging.getLogger(__name__)
WARSAW = ZoneInfo("Europe/Warsaw")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CLAUDE_URL = "https://api.anthropic.com/v1/messages"


RETRY_PAUSE = 30  # секунд паузи, якщо зайняті всі моделі одразу


class AIError(Exception):
    """Помилка AI, яку немає сенсу повторювати тією ж моделлю."""


class AIUnavailable(AIError):
    """AI тимчасово недоступний (перевантаження, вичерпано ліміт): спробуємо наступного запуску."""


class _TryLater(Exception):
    """Тимчасова помилка (перевантаження, ліміт за хвилину): варто спробувати ще раз."""


class _DailyLimit(Exception):
    """Денний ліміт моделі вичерпано: сьогодні її вже не пробуємо."""


@dataclass
class Post:
    headline: str
    summary: str
    why: str


# ── Gemini ──────────────────────────────────────────────────────────────

def _gemini_once(model: str, key: str, system: str, prompt: str) -> str:
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    try:
        resp = requests.post(GEMINI_URL.format(model=model), headers={"x-goog-api-key": key},
                             json=body, timeout=180)
    except requests.RequestException as exc:
        raise _TryLater(f"немає зв'язку: {type(exc).__name__}")

    if resp.status_code == 429 and "limit: 0" in resp.text:
        raise AIError("модель недоступна на безкоштовному тарифі")
    if resp.status_code == 429 and "PerDay" in resp.text:
        raise _DailyLimit("вичерпано денний ліміт запитів")
    if resp.status_code in (429, 500, 502, 503, 504):
        raise _TryLater(f"HTTP {resp.status_code}")
    if resp.status_code != 200:
        raise AIError(f"HTTP {resp.status_code}: {resp.text[:400]}")

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise AIError(f"порожня відповідь ({data.get('promptFeedback')})")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        raise AIError(f"відповідь без тексту (finishReason={candidates[0].get('finishReason')})")
    return text


def _ask_gemini(system: str, prompt: str) -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:  # без ключа інші моделі теж не спрацюють, тож одразу кажемо про це
        raise AIError("не задано секрет GEMINI_API_KEY")
    # Якщо модель зайнята, одразу пробуємо наступну, а не чекаємо.
    # Пауза — лише коли зайняті всі, тоді проходимо список ще раз.
    models, problems, temporary = list(config.GEMINI_MODELS), [], False
    for round_no in range(2):
        if round_no and models:
            log.warning("   Усі моделі Gemini зайняті, чекаю %d с…", RETRY_PAUSE)
            time.sleep(RETRY_PAUSE)
        for model in list(models):
            try:
                return _gemini_once(model, key, system, prompt)
            except _TryLater as exc:
                temporary = True
                problems.append(f"{model}: {exc}")
                log.warning("   Gemini %s зайнятий (%s), пробую наступну модель", model, exc)
            except _DailyLimit as exc:
                temporary = True
                models.remove(model)
                problems.append(f"{model}: {exc}")
                log.warning("   Gemini %s: %s", model, exc)
            except AIError as exc:
                models.remove(model)
                problems.append(f"{model}: {exc}")
                log.warning("   Gemini %s не підійшов: %s", model, exc)
    error = AIUnavailable if temporary else AIError
    raise error("жодна модель Gemini не відповіла:\n  " + "\n  ".join(problems[-6:]))


# ── Claude ──────────────────────────────────────────────────────────────

def _ask_claude(system: str, prompt: str) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise AIError("не задано секрет ANTHROPIC_API_KEY")
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    body = {
        "model": config.CLAUDE_MODEL,
        "max_tokens": 2000,
        "system": system,
        "messages": [{"role": "user", "content": prompt + "\n\nВідповідай лише JSON, без пояснень."}],
    }
    for attempt in range(3):
        try:
            resp = requests.post(CLAUDE_URL, headers=headers, json=body, timeout=120)
        except requests.RequestException as exc:
            problem = f"немає зв'язку: {type(exc).__name__}"
        else:
            if resp.status_code == 200:
                content = resp.json().get("content", [])
                return "".join(block.get("text", "") for block in content if block.get("type") == "text")
            if resp.status_code not in (429, 500, 502, 503, 529):
                raise AIError(f"Claude HTTP {resp.status_code}: {resp.text[:400]}")
            problem = f"HTTP {resp.status_code}"
        if attempt < 2:
            wait = 20 * (attempt + 1)
            log.warning("   Claude зайнятий (%s), чекаю %d с…", problem, wait)
            time.sleep(wait)
    raise AIUnavailable(f"Claude не відповів після кількох спроб ({problem})")


# ── Спільне ─────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict | list:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"[\[{].*[\]}]", cleaned, re.S)
        try:
            data = json.loads(match.group(0)) if match else None
        except json.JSONDecodeError:
            data = None
    if not isinstance(data, (dict, list)):
        raise AIError(f"AI повернув не JSON: {text[:200]}")
    return data


def ask_json(system: str, prompt: str) -> dict | list:
    if config.AI_PROVIDER == "claude":
        return _parse_json(_ask_claude(system, prompt))
    return _parse_json(_ask_gemini(system, prompt))


def _clean(value) -> str:
    text = str(value or "").replace("**", "").strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \"«»")


def select_news(items: list[NewsItem], recent: list[str], limit: int) -> list[tuple[NewsItem, str]]:
    """Повертає список (новина, тема), від найважливішої."""
    lines = []
    for item in items:
        when = item.published.astimezone(WARSAW).strftime("%d.%m %H:%M")
        line = f"[{item.id}] {item.title} ({item.source}, {when})"
        if item.summary:
            line += f"\n    {item.summary[:280]}"
        lines.append(line)

    prompt = prompts.SELECT_PROMPT.format(
        limit=limit,
        topics=", ".join(config.TOPICS),
        recent="\n".join(f"- {title}" for title in recent) or "(поки нічого)",
        listing="\n".join(lines),
    )
    data = ask_json(prompts.SELECT_SYSTEM, prompt)

    # легші моделі інколи повертають одразу список замість {"selected": [...]}
    entries = data.get("selected") if isinstance(data, dict) else data

    by_id = {item.id: item for item in items}
    chosen, used = [], set()
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        try:
            number = int(entry.get("id"))
        except (TypeError, ValueError):
            continue
        if number not in by_id or number in used:
            continue
        topic = entry.get("topic") if entry.get("topic") in config.TOPICS else config.DEFAULT_TOPIC
        chosen.append((by_id[number], topic))
        used.add(number)
        if len(chosen) >= limit:
            break
    return chosen


def write_post(item: NewsItem, article_text: str) -> Post | None:
    """Пише пост. Повертає None, якщо в статті замало інформації."""
    prompt = prompts.WRITE_PROMPT.format(source=item.source, title=item.title, text=article_text)
    data = ask_json(prompts.WRITE_SYSTEM, prompt)
    if isinstance(data, list):  # відповідь загорнута в список — беремо перший об'єкт
        data = next((entry for entry in data if isinstance(entry, dict)), {})
    if data.get("enough_info") is False:
        return None
    post = Post(
        headline=_clean(data.get("headline"))[:120],
        summary=_clean(data.get("summary")),
        why=_clean(data.get("why_it_matters")),
    )
    if len(post.headline) < 10 or len(post.summary) < 40:
        return None
    return post
