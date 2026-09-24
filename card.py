"""
Картинка до поста: біла частина із заголовком і червона смуга внизу,
як на польському прапорі. У смузі — тема, дата й назва каналу.

Якщо в папці backgrounds/ лежить фото з назвою теми (наприклад,
work.jpg), воно стане фоном верхньої частини, а заголовок — білим.

Запусти `python card.py`, щоб побачити приклади в папці preview/.
"""

import io
import os
from datetime import datetime
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont, ImageOps

import config

W, H = 1280, 720
BAND_H = 190          # висота червоної смуги
TOP_H = H - BAND_H    # висота верхньої частини
MARGIN = 72           # відступ зліва й справа
PAD_Y = 56            # мінімальний відступ заголовка зверху й знизу

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
BG_DIR = os.path.join(HERE, "backgrounds")

HEADLINE_FONT = "DejaVuSansCondensed-Bold.ttf"
LABEL_FONT = "DejaVuSans-Bold.ttf"
TEXT_FONT = "DejaVuSans.ttf"

MONTHS = ["січня", "лютого", "березня", "квітня", "травня", "червня",
          "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]


@lru_cache(maxsize=64)
def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _units(text: str) -> list[str]:
    """Слова для переносу. Короткі слова («у», «з», «на») чіпляються до наступного,
    щоб не висіти в кінці рядка."""
    words, units, carry = text.split(), [], ""
    for word in words:
        joined = f"{carry} {word}".strip()
        carry = ""
        if len(word) <= 2 and word.isalpha():
            carry = joined
        else:
            units.append(joined)
    if carry:
        units.append(carry)
    return units


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines, current = [], ""
    for word in _units(text):
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        while draw.textlength(word, font=font) > max_width:  # дуже довге слово
            cut = len(word) - 1
            while cut > 1 and draw.textlength(word[:cut] + "-", font=font) > max_width:
                cut -= 1
            lines.append(word[:cut] + "-")
            word = word[cut:]
        current = word
    if current:
        lines.append(current)
    return lines


def _fit_headline(draw, text: str, max_width: int, max_height: int, max_lines: int = 4):
    for size in range(92, 42, -2):
        font = _font(HEADLINE_FONT, size)
        lines = _wrap(draw, text, font, max_width)
        line_h = round(size * 1.12)
        if len(lines) <= max_lines and line_h * len(lines) <= max_height:
            return font, lines, line_h
    # не влізло навіть найменшим шрифтом — обрізаємо з трикрапкою
    font = _font(HEADLINE_FONT, 44)
    lines = _wrap(draw, text, font, max_width)[:max_lines]
    last = lines[-1]
    while last and draw.textlength(last + "…", font=font) > max_width:
        last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
    lines[-1] = last.rstrip(" ,.;:—-") + "…"
    return font, lines, round(44 * 1.12)


def _background(topic_key: str) -> Image.Image | None:
    for ext in ("jpg", "jpeg", "png", "webp"):
        path = os.path.join(BG_DIR, f"{topic_key}.{ext}")
        if os.path.exists(path):
            photo = ImageOps.fit(Image.open(path).convert("RGB"), (W, TOP_H),
                                 method=Image.Resampling.LANCZOS)
            # затемнення, сильніше донизу, щоб білий текст читався
            shade = Image.linear_gradient("L").resize((W, TOP_H)).point(lambda v: 80 + v * 100 // 255)
            return Image.composite(Image.new("RGB", (W, TOP_H), (0, 0, 0)), photo, shade)
    return None


def ukrainian_date(moment: datetime) -> str:
    return f"{moment.day} {MONTHS[moment.month - 1]} {moment.year}"


def make_card(headline: str, topic_key: str, moment: datetime) -> bytes:
    topic = config.TOPICS.get(topic_key) or config.TOPICS[config.DEFAULT_TOPIC]
    image = Image.new("RGB", (W, H), config.COLOR_WHITE)
    ink = config.COLOR_INK

    photo = _background(topic_key)
    if photo is not None:
        image.paste(photo, (0, 0))
        ink = config.COLOR_WHITE

    draw = ImageDraw.Draw(image)
    draw.rectangle([0, TOP_H, W, H], fill=config.COLOR_RED)

    # Заголовок: рахуємо реальні межі тексту й ставимо блок по центру верхньої частини
    font, lines, line_h = _fit_headline(draw, headline, W - 2 * MARGIN, TOP_H - 2 * PAD_Y)
    boxes = [draw.textbbox((MARGIN, i * line_h), line, font=font, anchor="ls") for i, line in enumerate(lines)]
    block_top, block_bottom = min(b[1] for b in boxes), max(b[3] for b in boxes)
    shift = (TOP_H - (block_bottom - block_top)) // 2 - block_top
    for i, line in enumerate(lines):
        draw.text((MARGIN, i * line_h + shift), line, font=font, fill=ink, anchor="ls")

    # Червона смуга: тема й дата зліва, назва каналу справа
    center = TOP_H + BAND_H // 2
    label_font, date_font = _font(LABEL_FONT, 38), _font(TEXT_FONT, 27)
    draw.text((MARGIN, center - 4), topic["label"], font=label_font, fill=config.COLOR_WHITE, anchor="ls")
    draw.text((MARGIN, center + 40), ukrainian_date(moment), font=date_font, fill=(255, 222, 228), anchor="ls")
    draw.text((W - MARGIN, center + 14), config.CHANNEL_TITLE, font=label_font,
              fill=config.COLOR_WHITE, anchor="rs")

    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=92, optimize=True)
    return buffer.getvalue()


if __name__ == "__main__":
    os.makedirs("preview", exist_ok=True)
    samples = [
        ("Уряд змінює правила легалізації: що чекає на іноземців з 1 січня", "legalization"),
        ("Мінімальна зарплата зросте", "work"),
        ("ZUS нагадує: до кінця місяця треба подати документи на виплату 800+ для дітей іноземців", "social"),
    ]
    for number, (text, topic) in enumerate(samples, start=1):
        path = os.path.join("preview", f"demo-{number}.jpg")
        with open(path, "wb") as f:
            f.write(make_card(text, topic, datetime.now()))
        print("Збережено", path)
