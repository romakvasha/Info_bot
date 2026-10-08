"""
Щоденний пост із курсом валют за даними Національного банку Польщі (NBP).

Офіційний середній курс (таблиця A) NBP публікує в робочі дні близько полудня,
тож о 14:00 свіжий курс уже є. У вихідні й свята беремо останню таблицю.
API безкоштовне й без ключа: https://api.nbp.pl
"""

import logging
from datetime import date

import requests

log = logging.getLogger(__name__)

NBP_URL = "https://api.nbp.pl/api/exchangerates/tables/A/last/2/?format=json"

# Код валюти: (прапор, назва українською, скільки одиниць показувати)
CURRENCIES = {
    "EUR": ("🇪🇺", "Євро", 1),
    "USD": ("🇺🇸", "Долар США", 1),
    "UAH": ("🇺🇦", "Гривня", 100),
    "GBP": ("🇬🇧", "Фунт стерлінгів", 1),
    "CHF": ("🇨🇭", "Швейцарський франк", 1),
}


class RatesError(Exception):
    pass


def fetch_tables() -> list[dict]:
    """Дві останні таблиці NBP: [попередня, остання]."""
    try:
        resp = requests.get(NBP_URL, headers={"Accept": "application/json"}, timeout=20)
        resp.raise_for_status()
        tables = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise RatesError(f"NBP не відповів: {exc}")
    if not isinstance(tables, list) or not tables:
        raise RatesError("NBP повернув порожню відповідь")
    return tables


def _arrow(new: float, old: float | None) -> str:
    if old is None or abs(new - old) < 0.00005:
        return "▫️"
    return "🔺" if new > old else "🔻"


def build_message(tables: list[dict], channel_link: str = "") -> str:
    latest = tables[-1]
    previous = tables[-2] if len(tables) > 1 else None
    now = {r["code"]: r["mid"] for r in latest["rates"]}
    before = {r["code"]: r["mid"] for r in previous["rates"]} if previous else {}

    day = date.fromisoformat(latest["effectiveDate"]).strftime("%d.%m.%Y")
    lines = ["💱 <b>Курс валют на сьогодні</b>", f"Офіційний курс NBP від {day}", ""]
    for code, (flag, name, units) in CURRENCIES.items():
        if code not in now:
            continue
        value = now[code] * units
        old = before.get(code)
        old_value = old * units if old is not None else None
        change = ""
        if old_value is not None and abs(value - old_value) >= 0.00005:
            change = f" ({value - old_value:+.4f})"
        label = f"{units} {code}" if units > 1 else code
        lines.append(f"{flag} {name}: <b>{label} = {value:.4f} zł</b> {_arrow(value, old_value)}{change}")

    lines += ["", "Курс у канторах і банках відрізняється від офіційного.", "", "#курс"]
    if channel_link:
        lines[-1] += f" | {channel_link}"
    return "\n".join(lines)
