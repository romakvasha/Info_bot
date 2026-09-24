"""
Налаштування бота «Новини Польща».

Тут зібрано все, що можна міняти, не заглиблюючись у решту коду:
модель AI, кількість постів, джерела, теми й кольори.
"""

# ── AI ──────────────────────────────────────────────────────────────────
# "gemini" — безкоштовний тариф Google (потрібен секрет GEMINI_API_KEY)
# "claude" — платний API Anthropic (потрібен секрет ANTHROPIC_API_KEY)
AI_PROVIDER = "gemini"

# Моделі Gemini пробуються по черзі: якщо першої немає або вона
# недоступна на безкоштовному тарифі, бот сам перейде до наступної.
GEMINI_MODELS = [
    "gemini-flash-latest",       # остання версія Flash (оновлюється сама)
    "gemini-flash-lite-latest",  # легша версія з більшими лімітами
    "gemini-2.5-flash",          # запасний варіант
]

CLAUDE_MODEL = "claude-haiku-4-5"

# ── Публікації ──────────────────────────────────────────────────────────
POSTS_PER_RUN = 2           # максимум новин за один запуск
MAX_AGE_HOURS = 24          # старіші новини ігноруються
MAX_PER_FEED = 25           # скільки найсвіжіших новин брати з кожного джерела
MAX_CANDIDATES = 70         # скільки заголовків максимум віддавати AI на відбір
PAUSE_BETWEEN_POSTS = 20    # секунд між постами, щоб вони не йшли пачкою

CHANNEL_TITLE = "Новини Польща"  # напис на картинках і в підписі
ADD_CHANNEL_LINK = True          # додавати в кінці поста посилання на канал

# ── Джерела ─────────────────────────────────────────────────────────────
# Назва: адреса RSS. Якщо якесь джерело перестане працювати,
# бот просто пропустить його й напише про це в лозі.
RSS_FEEDS = {
    "RMF24": "https://www.rmf24.pl/fakty/polska/feed",
    "RMF24 Ekonomia": "https://www.rmf24.pl/ekonomia/feed",
    "Polsat News": "https://www.polsatnews.pl/rss/wszystkie.xml",
    "Bankier.pl": "https://www.bankier.pl/rss/wiadomosci.xml",
    "Notes from Poland": "https://notesfrompoland.com/feed/",
}

# Новини, в адресі яких є ці фрагменти, відкидаються одразу
SKIP_URL_PARTS = ["/sport", "polsatsport.pl", "/rozrywka", "/plotki"]

# ── Теми ────────────────────────────────────────────────────────────────
# Ключ (англійською) бачить тільки AI, решту — читачі.
TOPICS = {
    "legalization": {"label": "Легалізація", "emoji": "🪪", "hashtag": "#легалізація"},
    "work": {"label": "Робота", "emoji": "💼", "hashtag": "#робота"},
    "money": {"label": "Гроші й податки", "emoji": "💰", "hashtag": "#гроші"},
    "social": {"label": "Соцвиплати", "emoji": "👨‍👩‍👧", "hashtag": "#виплати"},
    "health": {"label": "Медицина", "emoji": "🏥", "hashtag": "#медицина"},
    "education": {"label": "Освіта", "emoji": "🎓", "hashtag": "#освіта"},
    "transport": {"label": "Транспорт і кордон", "emoji": "🚆", "hashtag": "#транспорт"},
    "safety": {"label": "Безпека", "emoji": "⚠️", "hashtag": "#безпека"},
    "politics": {"label": "Політика", "emoji": "🏛", "hashtag": "#політика"},
    "ukraine": {"label": "Україна і Польща", "emoji": "🇺🇦", "hashtag": "#україна"},
    "life": {"label": "Життя в Польщі", "emoji": "🇵🇱", "hashtag": "#польща"},
}
DEFAULT_TOPIC = "life"

# ── Картинка ────────────────────────────────────────────────────────────
COLOR_RED = (212, 33, 61)      # червоний польського прапора
COLOR_WHITE = (255, 255, 255)
COLOR_INK = (0, 0, 0)          # колір заголовка на білому тлі
