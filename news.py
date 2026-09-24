"""
Збір новин: читає RSS-стрічки, відкидає старе й дублікати,
а для вибраних новин завантажує повний текст статті.
"""

import calendar
import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit

import feedparser
import requests

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NovynyPolshchaBot/1.0; RSS reader)",
    "Accept-Language": "pl-PL,pl;q=0.9,uk;q=0.8,en;q=0.7",
}
TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "at_")


@dataclass
class NewsItem:
    id: int
    title: str
    link: str
    source: str
    summary: str
    published: datetime


def clean_text(value: str) -> str:
    """Прибирає HTML-теги й зайві пробіли."""
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_url(url: str) -> str:
    """Ключ для порівняння посилань: без http/https, www і трекінгових міток."""
    parts = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(TRACKING_PREFIXES)
    ]
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/")
    return host + path + ("?" + urlencode(query) if query else "")


def title_key(title: str) -> str:
    """Ключ для порівняння заголовків: лише літери й цифри в нижньому регістрі."""
    return re.sub(r"\W+", " ", title.lower()).strip()


def _published(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        value = entry.get(field)
        if value:
            return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc)
    return None


def _fetch_feed(url: str) -> list:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        raise ValueError(f"не вдалося розібрати RSS ({feed.bozo_exception})")
    return feed.entries


def collect(feeds: dict, known_urls: set, known_titles: set,
            max_age_hours: int, per_feed: int, skip_parts: list) -> list[NewsItem]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    seen_urls, seen_titles = set(known_urls), set(known_titles)
    items: list[NewsItem] = []

    for source, url in feeds.items():
        try:
            entries = _fetch_feed(url)
        except Exception as exc:  # одне зламане джерело не повинно зупиняти бота
            log.warning("⚠️  %s: джерело недоступне (%s)", source, exc)
            continue

        taken = 0
        for entry in entries:
            link = (entry.get("link") or "").strip()
            title = clean_text(entry.get("title", ""))
            if not link or not title or any(part in link for part in skip_parts):
                continue
            published = _published(entry) or now
            if published < cutoff:
                continue
            url_key, t_key = normalize_url(link), title_key(title)
            if url_key in seen_urls or t_key in seen_titles:
                continue
            seen_urls.add(url_key)
            seen_titles.add(t_key)
            summary = clean_text(entry.get("summary") or entry.get("description") or "")
            items.append(NewsItem(0, title, link, source, summary[:600], min(published, now)))
            taken += 1
            if taken >= per_feed:
                break
        log.info("✓ %s: свіжих новин — %d", source, taken)

    items.sort(key=lambda item: item.published, reverse=True)
    for number, item in enumerate(items, start=1):
        item.id = number
    return items


def _simple_extract(page: str) -> str:
    """Запасний варіант, якщо trafilatura не встановлена: беремо абзаци <p>."""
    page = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", page)
    paragraphs = [clean_text(p) for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", page)]
    return "\n".join(p for p in paragraphs if len(p) > 40)


def fetch_article_text(url: str, limit: int = 6000) -> str:
    """Повертає текст статті або порожній рядок, якщо сторінка недоступна."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.info("   текст статті недоступний (%s), беру опис із RSS", exc)
        return ""
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    page = resp.text
    try:
        import trafilatura

        text = trafilatura.extract(page, include_comments=False, include_tables=False,
                                   favor_precision=True) or ""
    except ImportError:
        text = _simple_extract(page)
    return text.strip()[:limit]
