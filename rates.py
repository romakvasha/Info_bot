"""
Щоденний курс валют: картинка з трьома курсами й короткий підпис.

- долар → злотий — офіційний курс Національного банку Польщі (NBP, таблиця A);
- долар → гривня і гривня → злотий — офіційний курс Національного банку України (НБУ).

NBP публікує курс у робочі дні близько полудня, НБУ — щодня (на вихідні діє
п'ятничний). Обидва API безкоштовні й без ключа: https://api.nbp.pl,
https://bank.gov.ua/ua/open-data/api-dev
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import requests

log = logging.getLogger(__name__)

NBP_USD_URL = "https://api.nbp.pl/api/exchangerates/rates/A/USD/last/2/?format=json"
NBU_URL = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"


class RatesError(Exception):
    pass


@dataclass
class Rate:
    title: str          # підпис над курсом на картці
    amount: str         # ліва частина: «1 $», «100 ₴»
    value: float
    previous: float | None
    currency: str       # «zł» або «₴»
    decimals: int
    source: str         # «NBP» або «НБУ»
    color: tuple[int, int, int]

    @property
    def change(self) -> float:
        if self.previous is None:
            return 0.0
        change = self.value - self.previous
        return 0.0 if abs(change) < 0.5 * 10 ** -self.decimals else change


@dataclass
class Rates:
    rows: list[Rate]
    pln_in_uah: float   # скільки гривень за 1 злотий (для підпису)
    nbp_date: date
    nbu_date: date


def number(value: float, decimals: int, sign: bool = False) -> str:
    """3.91324 → «3,9132» — з комою, як пишуть в Україні й Польщі."""
    text = f"{value:+.{decimals}f}" if sign else f"{value:.{decimals}f}"
    return text.replace(".", ",")


def _get_json(url: str, bank: str):
    try:
        resp = requests.get(url, headers={"Accept": "application/json"}, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise RatesError(f"{bank} не відповів: {exc}")


def fetch_nbp_usd() -> tuple[float, float | None, date]:
    """Курс долара NBP: (останній, попередній, дата останнього)."""
    data = _get_json(NBP_USD_URL, "NBP")
    try:
        items = data["rates"]
        latest = items[-1]
        previous = items[-2]["mid"] if len(items) > 1 else None
        return float(latest["mid"]), previous, date.fromisoformat(latest["effectiveDate"])
    except (KeyError, IndexError, TypeError, ValueError):
        raise RatesError("NBP повернув незрозумілу відповідь")


def _nbu_table(day: date | None = None) -> tuple[dict[str, float], date]:
    url = NBU_URL + (f"&date={day:%Y%m%d}" if day else "")
    data = _get_json(url, "НБУ")
    try:
        table = {item["cc"]: float(item["rate"]) for item in data}
        when = datetime.strptime(data[0]["exchangedate"], "%d.%m.%Y").date()
    except (KeyError, IndexError, TypeError, ValueError):
        raise RatesError("НБУ повернув незрозумілу відповідь")
    if "USD" not in table or "PLN" not in table:
        raise RatesError("у відповіді НБУ немає долара чи злотого")
    return table, when


def fetch() -> Rates:
    usd_pln, usd_pln_before, nbp_date = fetch_nbp_usd()
    nbu, nbu_date = _nbu_table()
    try:
        nbu_before, _ = _nbu_table(nbu_date - timedelta(days=1))
    except RatesError as exc:  # без попереднього дня просто не покажемо зміну
        log.warning("⚠️  НБУ: не вдалося взяти попередній курс (%s)", exc)
        nbu_before = {}

    def uah_100_in_pln(table: dict) -> float | None:
        return 100 / table["PLN"] if "PLN" in table else None

    rows = [
        Rate("Долар → злотий", "1 $", usd_pln, usd_pln_before, "zł", 4, "NBP", (212, 33, 61)),
        Rate("Долар → гривня", "1 $", nbu["USD"], nbu_before.get("USD"), "₴", 2, "НБУ", (0, 87, 183)),
        Rate("Гривня → злотий", "100 ₴", uah_100_in_pln(nbu), uah_100_in_pln(nbu_before), "zł", 2, "НБУ",
             (196, 120, 0)),
    ]
    return Rates(rows, nbu["PLN"], nbp_date, nbu_date)


def _arrow(rate: Rate) -> str:
    if rate.change == 0:
        return ""
    return f" {'🔺' if rate.change > 0 else '🔻'} {number(rate.change, rate.decimals, sign=True)}"


def build_caption(data: Rates, channel_link: str = "") -> str:
    usd_pln, usd_uah, uah_pln = data.rows
    lines = [
        "💱 <b>Курс валют на сьогодні</b>",
        "",
        f"🇺🇸→🇵🇱 1 долар = <b>{number(usd_pln.value, 4)} zł</b>{_arrow(usd_pln)}",
        f"🇺🇸→🇺🇦 1 долар = <b>{number(usd_uah.value, 2)} ₴</b>{_arrow(usd_uah)}",
        f"🇺🇦→🇵🇱 100 гривень = <b>{number(uah_pln.value, 2)} zł</b>{_arrow(uah_pln)}",
        f"🇵🇱→🇺🇦 1 злотий = <b>{number(data.pln_in_uah, 2)} ₴</b>",
        "",
        f"Офіційні курси: долар до злотого — NBP від {data.nbp_date:%d.%m.%Y}, "
        f"гривня — НБУ від {data.nbu_date:%d.%m.%Y}. У канторах і банках курс відрізняється.",
        "",
        "#курс",
    ]
    if channel_link:
        lines[-1] += f" | {channel_link}"
    return "\n".join(lines)
