"""
Бот «Новини Польща»: збирає свіжі новини, відбирає й переписує їх через AI,
малює картинку й публікує в Telegram-канал.

    python main.py            — звичайний запуск
    python main.py --dry-run  — тест без публікації: картинки й тексти з'являться в папці preview/
"""

import argparse
import html
import logging
import os
import re
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import ai
import card
import config
import news
import rates
import storage
import telegram_api

log = logging.getLogger("bot")
WARSAW = ZoneInfo("Europe/Warsaw")
CAPTION_LIMIT = 1024  # ліміт Telegram для підпису під фото

# Помилки Telegram, які означають проблему з налаштуваннями, і підказки до них
SETUP_HINTS = {
    "unauthorized": "Перевір секрет TELEGRAM_BOT_TOKEN: схоже, токен бота неправильний.",
    "chat not found": "Перевір секрет TELEGRAM_CHANNEL: потрібна адреса публічного каналу з @, наприклад @novyny_polshcha.",
    "not a member": "Додай бота адміністратором каналу з правом публікувати повідомлення.",
    "inaccessible": "Додай бота адміністратором каналу з правом публікувати повідомлення.",
    "rights": "Дай ботові в адмінці каналу право публікувати повідомлення.",
    "kicked": "Бота видалили з каналу — додай його знову адміністратором.",
}


def setup_hint(exc: Exception) -> str | None:
    text = str(exc).lower()
    for marker, hint in SETUP_HINTS.items():
        if marker in text:
            return hint
    return None


def check_telegram(token: str, channel: str) -> bool:
    """Перевіряє токен і права бота в каналі, нічого не публікуючи."""
    try:
        bot = telegram_api.get_me(token)
        member = telegram_api.get_chat_member(token, channel, bot["id"])
    except telegram_api.TelegramError as exc:
        log.error("❌ Telegram: %s", exc)
        hint = setup_hint(exc)
        if hint:
            log.error("   💡 %s", hint)
        return False

    name, status = bot.get("username", "?"), member.get("status")
    if status == "creator" or (status == "administrator" and member.get("can_post_messages")):
        log.info("✓ Telegram: бот @%s може публікувати в %s", name, channel)
        return True
    log.error("❌ Telegram: бот @%s не може публікувати в %s (статус: %s)", name, channel, status)
    log.error("   💡 %s", SETUP_HINTS["rights" if status == "administrator" else "not a member"])
    return False


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def telegram_length(text: str) -> int:
    """Telegram рахує символи в UTF-16, тож емодзі можуть займати 2 позиції."""
    visible = html.unescape(re.sub(r"<[^>]+>", "", text))
    return len(visible.encode("utf-16-le")) // 2


def normalize_channel(value: str) -> str:
    value = re.sub(r"^(https?://)?t\.me/", "", value.strip())
    if value and not value.startswith("@") and not value.lstrip("-").isdigit():
        value = "@" + value
    return value


def build_caption(post: ai.Post, item: news.NewsItem, topic_key: str, channel: str) -> str:
    topic = config.TOPICS[topic_key]

    def assemble(summary: str) -> str:
        parts = [f"{topic['emoji']} <b>{esc(post.headline)}</b>", "", esc(summary)]
        if post.why:
            parts += ["", f"👉 {esc(post.why)}"]
        parts += ["", f'<a href="{html.escape(item.link, quote=True)}">Джерело: {esc(item.source)}</a>']
        footer = topic["hashtag"]
        if config.ADD_CHANNEL_LINK and channel.startswith("@"):
            footer += f' | <a href="https://t.me/{channel[1:]}">{esc(config.CHANNEL_TITLE)}</a>'
        parts += ["", footer]
        return "\n".join(parts)

    summary = post.summary
    caption = assemble(summary)
    while telegram_length(caption) > CAPTION_LIMIT and len(summary) > 80:
        summary = summary[:-60].rsplit(" ", 1)[0].rstrip(" ,.;:—-") + "…"
        caption = assemble(summary)
    return caption


def save_preview(number: int | str, image: bytes, caption: str) -> None:
    os.makedirs("preview", exist_ok=True)
    with open(os.path.join("preview", f"post-{number}.jpg"), "wb") as f:
        f.write(image)
    with open(os.path.join("preview", f"post-{number}.txt"), "w", encoding="utf-8") as f:
        f.write(caption)
    log.info("   🧪 Збережено в preview/post-%s.jpg\n%s", number, caption)


def publish(token: str, channel: str, image: bytes, caption: str) -> None:
    try:
        telegram_api.send_photo(token, channel, image, caption)
    except telegram_api.TelegramError as exc:
        if "parse entities" not in str(exc):
            raise
        # запасний варіант: той самий текст без HTML-розмітки
        plain = html.unescape(re.sub(r"<[^>]+>", "", caption))
        telegram_api.send_photo(token, channel, image, plain, parse_mode=None)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    parser = argparse.ArgumentParser(description="Бот «Новини Польща»")
    parser.add_argument("--dry-run", action="store_true", help="нічого не публікувати, зберегти результат у preview/")
    args = parser.parse_args()

    dry_run = args.dry_run or os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    channel = normalize_channel(os.environ.get("TELEGRAM_CHANNEL", ""))

    mode = "тестовий запуск без публікації" if dry_run else "запуск"
    log.info("🤖 Новини Польща: %s, AI — %s", mode, config.AI_PROVIDER)
    for name in os.environ.get("NAMES_IN_VARIABLES", "").split():
        log.warning("⚠️  %s додано у Variables, а бот читає лише Secrets. Створи його у вкладці "
                    "Secrets (Settings → Secrets and variables → Actions), а з Variables видали.", name)

    # Telegram перевіряємо на самому початку, щоб не витрачати ліміт AI даремно
    telegram_ok = True
    if token and channel:
        telegram_ok = check_telegram(token, channel)
        if not telegram_ok and not dry_run:
            return 1
    elif dry_run:
        log.warning("⚠️  Не задано секрети TELEGRAM_BOT_TOKEN і/або TELEGRAM_CHANNEL, Telegram не перевірено.")
    else:
        log.error("❌ Не задано секрети TELEGRAM_BOT_TOKEN і/або TELEGRAM_CHANNEL.")
        return 1

    post_rates_if_due(dry_run, token, channel)
    code = run(dry_run, token, channel)
    if not telegram_ok:  # у тестовому запуску решту перевірили, але Telegram треба виправити
        log.error("❗ Telegram налаштовано неправильно, підказка — на початку лога.")
        return 1
    return code


def post_rates_if_due(dry_run: bool, token: str, channel: str) -> None:
    """Раз на день, у перший запуск після RATES_HOUR, публікує курс валют.
    У тестовому запуску курс показується в лозі завжди, щоб його можна було перевірити."""
    if not config.RATES_ENABLED:
        return
    now = datetime.now(WARSAW)
    state = storage.load()
    if state.get("rates_date") == now.date().isoformat():
        return  # сьогодні курс уже був
    if now.hour < config.RATES_HOUR and not dry_run:
        return

    try:
        data = rates.fetch()
    except rates.RatesError as exc:
        log.warning("⚠️  Курс валют: %s. Спробую наступного запуску.", exc)
        return
    link = ""
    if config.ADD_CHANNEL_LINK and channel.startswith("@"):
        link = f'<a href="https://t.me/{channel[1:]}">{esc(config.CHANNEL_TITLE)}</a>'
    caption = rates.build_caption(data, link)
    image = card.make_rates_card(data.rows, now)

    if dry_run:
        save_preview("rates", image, caption)
        return
    try:
        publish(token, channel, image, caption)
    except telegram_api.TelegramError as exc:
        log.error("❌ Курс валют не опубліковано: %s", exc)
        return
    state["rates_date"] = now.date().isoformat()
    storage.save(state)
    log.info("💱 Опубліковано курс валют\n")


def run(dry_run: bool, token: str, channel: str) -> int:
    state = storage.load()
    today = storage.posted_today(state, WARSAW)
    limit = min(config.POSTS_PER_RUN, config.MAX_POSTS_PER_DAY - today)
    if limit <= 0:
        log.info("Сьогодні вже опубліковано %d постів — це денний максимум. До завтра!", today)
        return 0

    items = news.collect(
        config.RSS_FEEDS,
        storage.known_url_keys(state),
        storage.known_title_keys(state),
        config.MAX_AGE_HOURS,
        config.MAX_PER_FEED,
        config.SKIP_URL_PARTS,
    )
    if not items:
        log.info("Свіжих новин немає. До наступного запуску!")
        return 0

    candidates = news.pick_candidates(items, config.MAX_CANDIDATES)
    log.info("🔎 AI відбирає найважливіше з %d новин…", len(candidates))
    try:
        selected = ai.select_news(candidates, storage.recent_headlines(state), limit)
    except ai.AIUnavailable as exc:
        # тимчасовий збій: через годину буде новий запуск, тож не «червонимо» цей
        log.warning("⏸  AI зараз недоступний, спробую наступного запуску: %s", exc)
        return 0
    except ai.AIError as exc:
        log.error("❌ AI не зміг відібрати новини: %s", exc)
        return 1
    if not selected:
        log.info("AI не знайшов нічого вартого публікації. До наступного запуску!")
        return 0

    published = failed = 0
    for number, (item, topic) in enumerate(selected, start=1):
        log.info("\n📰 %d/%d [%s] %s", number, len(selected), item.source, item.title)
        text = news.fetch_article_text(item.link)
        if len(text) < 300:  # статтю не вдалося прочитати — працюємо з описом із RSS
            text = "\n".join(part for part in (item.title, item.summary, text) if part)
        try:
            post = ai.write_post(item, text)
        except ai.AIUnavailable as exc:
            # новину не позначаємо: наступного запуску AI зможе написати пост про неї
            log.warning("   ⏸  AI зараз недоступний, решту новин лишаю на наступний запуск: %s", exc)
            break
        except ai.AIError as exc:
            log.error("   ❌ AI не написав пост: %s", exc)
            failed += 1
            if not dry_run:  # позначаємо, щоб не пробувати ту саму новину знову й знову
                storage.remember(state, item.link, item.title, "failed", topic=topic)
                storage.save(state)
            continue

        if post is None:
            log.info("   ⏭  Замало інформації для поста, пропускаю")
            if not dry_run:
                storage.remember(state, item.link, item.title, "skipped", topic=topic)
                storage.save(state)
            continue

        caption = build_caption(post, item, topic, channel)
        image = card.make_card(post.headline, topic, datetime.now(WARSAW))

        if dry_run:
            save_preview(number, image, caption)
            published += 1
            continue

        try:
            publish(token, channel, image, caption)
        except telegram_api.TelegramError as exc:
            log.error("   ❌ Telegram: %s", exc)
            hint = setup_hint(exc)
            if hint:
                log.error("   💡 %s", hint)
                return 1  # проблема з налаштуваннями, далі пробувати немає сенсу
            failed += 1
            storage.remember(state, item.link, item.title, "failed", topic=topic)
            storage.save(state)
            continue

        storage.remember(state, item.link, item.title, "posted", post.headline, topic)
        storage.save(state)
        published += 1
        log.info("   ✅ Опубліковано: %s", post.headline)
        if number < len(selected):
            time.sleep(config.PAUSE_BETWEEN_POSTS)

    log.info("\nГотово: опубліковано %d, помилок %d.", published, failed)
    return 1 if failed and not published else 0


if __name__ == "__main__":
    sys.exit(main())
