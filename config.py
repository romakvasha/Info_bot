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
    "gemini-3.8-flash",          # запасний варіант: її радить сам Google, бо gemini-2.5-flash
                                 # з вересня 2026 недоступна новим користувачам (HTTP 404)
]

CLAUDE_MODEL = "claude-haiku-4-5"

# ── Публікації ──────────────────────────────────────────────────────────
# Бот запускається щогодини. AI сам вирішує, скільки новин варті поста:
# коли нічого важливого — жодної, у насичені години — до POSTS_PER_RUN.
POSTS_PER_RUN = 6           # максимум новин за один запуск
MAX_POSTS_PER_DAY = 30      # запобіжник від спаму й від вичерпання безкоштовного ліміту Gemini
MAX_AGE_HOURS = 12          # старіші новини ігноруються (вистачає, щоб уранці підхопити нічні)
MAX_PER_FEED = 25           # скільки найсвіжіших новин брати з кожного джерела
MAX_CANDIDATES = 70         # скільки заголовків максимум віддавати AI на відбір
PAUSE_BETWEEN_POSTS = 20    # секунд між постами, щоб вони не йшли пачкою

CHANNEL_TITLE = "Новини Польща"  # напис на картинках і в підписі
ADD_CHANNEL_LINK = True          # додавати в кінці поста посилання на канал

# Картка з курсом валют (долар → злотий від NBP, долар → гривня й злотий → гривня від НБУ):
# раз на день, у перший запуск бота після цієї години (за Варшавою). Курси — у rates.py.
RATES_ENABLED = True
RATES_HOUR = 14

# ── Щоденний пост про легалізацію ───────────────────────────────────────
# Раз на день, у перший запуск після LEGAL_HOUR (за Варшавою), бот публікує пост про
# легалізацію: карта побиту, сталий побут, резидент ЄС, паспорт для іноземців, візи,
# статус UKR. Спершу шукає новину за останні LEGAL_MAX_AGE_HOURS у всіх джерелах.
# Якщо такої немає — публікує коротку інструкцію з офіційної сторінки (LEGAL_GUIDES),
# кожного дня наступну. Якщо пост про легалізацію сьогодні вже вийшов, нічого не робить.
LEGAL_ENABLED = True
LEGAL_HOUR = 11
LEGAL_MAX_AGE_HOURS = 72

# Джерела саме про іноземців: їхні новини завжди потрапляють до AI на відбір.
LEGAL_FEEDS = {
    "Ukrainian in Poland": "https://ukrainianinpoland.pl/feed/",
    "Наш вибір": "https://nashwybir.pl/feed/",
    "UdSC": "https://www.gov.pl/web/udsc/rss",
}

# З інших джерел до AI потрапляють лише новини, де є одне з цих слів (у заголовку чи описі)
LEGAL_KEYWORDS = [
    "cudzoziem", "pobyt", "legaliz", "wiza", "wizy", "wizę", "wizow", "paszport", "obywatelstw",
    "uchodźc", "migra", "imigra", "pesel", "zezwoleni", "udsc", "specustaw", "ochrony czasowej",
    "ochrona czasowa", "rezydent", "foreigner", "residence", "visa", "migrant", "permit",
    "легаліз", "побит", "віз", "паспорт", "іноземц", "мігра", "біженц", "громадянств", "дозвіл",
]

# Офіційні сторінки Управління у справах іноземців (UdSC) для інструкцій
LEGAL_GUIDE_SOURCE = "UdSC (gov.pl)"
LEGAL_GUIDES = {
    "https://www.gov.pl/web/udsc/zezwolenie-na-pobyt-czasowy": "Zezwolenie na pobyt czasowy",
    "https://www.gov.pl/web/udsc/zezwolenie-na-pobyt-staly": "Zezwolenie na pobyt stały",
    "https://www.gov.pl/web/udsc/zezwolenie-na-pobyt-rezydenta-dlugoterminowego-ue":
        "Zezwolenie na pobyt rezydenta długoterminowego UE",
    "https://www.gov.pl/web/udsc/karta-pobytu": "Karta pobytu",
    "https://www.gov.pl/web/udsc/polski-dokument-podrozy-dla-cudzoziemca": "Polski dokument podróży dla cudzoziemca",
    "https://www.gov.pl/web/udsc/polski-dokument-tozsamosci-cudzoziemca": "Polski dokument tożsamości cudzoziemca",
    "https://www.gov.pl/web/udsc/obywatele-ukrainy": "Obywatele Ukrainy",
}

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
