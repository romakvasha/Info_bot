"""
Публікація в Telegram через Bot API (https://core.telegram.org/bots/api).
"""

import time

import requests

API = "https://api.telegram.org/bot{token}/{method}"


class TelegramError(Exception):
    pass


def _call(token: str, method: str, data: dict, files: dict | None = None) -> dict:
    for attempt in range(3):
        try:
            resp = requests.post(API.format(token=token, method=method), data=data, files=files, timeout=60)
            payload = resp.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == 2:
                # токен є в адресі запиту — прибираємо його з тексту помилки
                raise TelegramError(f"немає зв'язку з Telegram: {str(exc).replace(token, '***')}")
            time.sleep(5)
            continue
        if payload.get("ok"):
            return payload["result"]
        retry_after = (payload.get("parameters") or {}).get("retry_after")
        if payload.get("error_code") == 429 and retry_after and attempt < 2:
            time.sleep(int(retry_after) + 1)
            continue
        raise TelegramError(payload.get("description", "невідома помилка"))
    raise TelegramError("Telegram не відповів")


def send_photo(token: str, chat_id: str, photo: bytes, caption: str, parse_mode: str | None = "HTML") -> int:
    data = {"chat_id": chat_id, "caption": caption}
    if parse_mode:
        data["parse_mode"] = parse_mode
    result = _call(token, "sendPhoto", data=data, files={"photo": ("card.jpg", photo, "image/jpeg")})
    return result["message_id"]


def send_message(token: str, chat_id: str, text: str) -> int:
    result = _call(token, "sendMessage", data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
    return result["message_id"]
