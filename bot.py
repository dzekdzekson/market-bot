import html

import logging
import os
import re
import sys
from flask import Flask
import threading

app = Flask('')

@app.route('/')
def home():
    return "OK"

def run_web():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_web, daemon=True).start()
from telethon import Button, TelegramClient, events

API_ID = 38374915
API_HASH = "c20886eb1e4bf991d58aad5da69685d"
BOT_TOKEN = "8034343571:AAGbcFMX3sS13HNAxh2AEvzXnaBuGB3ra9c"
target_channel = "@multimarket_uashop"
contact_url = "t.me"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("market_bot")
client = TelegramClient("official_bot_session", API_ID, API_HASH)

WHOLESALE_RE = re.compile(r"ОПТ|OPT", re.IGNORECASE)
DROP_RE = re.compile(r"(?:ДРОП|DROP)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)

waiting_for_ad: set[int] = set()


def make_post(source: str):
    """Подготавливает HTML-текст публикации; None означает пропуск оптового объявления."""
    lines = [line.strip() for line in source.splitlines() if not WHOLESALE_RE.search(line)]
    text = "\n".join(lines).strip()
    if not text:
        return None

    match = DROP_RE.search(text)
    price_line = None
    if match:
        usd = float(match.group(1).replace(",", "."))
        price_uah = int(round(usd * 41.5 * 1.25))
        price_line = f"<b>🔥 Ціна: {price_uah} грн</b>"

    formatted_lines = []
    for line in text.splitlines():
        if DROP_RE.search(line) and price_line:
            formatted_lines.append(price_line)
        else:
            formatted_lines.append(html.escape(line.replace("$", "")))

    safe_text = "\n".join(formatted_lines).strip()
    return (
        "🟢 <b>В наявності / Швидка відправка</b>\n\n"
        f"{safe_text}\n\n"
        "📦 <i>Для замовлення пишіть в Telegram (кнопка нижче)!</i>\n\n"
        "#multimarket"
    )


@client.on(events.NewMessage(pattern=r"^/start(?:@\w+)?$"))
async def start(event):
    text = (
        "<b>Добро пожаловать в MarketBot!</b>\n\n"
        "Здесь вы можете разместить свое объявление или связаться с администратором."
    )
    buttons = [
        [Button.inline("Разместить объявление", data=b"add_post")],
        [Button.url("Связаться с админом", url=contact_url)],
    ]
    await event.respond(text, parse_mode="html", buttons=buttons)


@client.on(events.CallbackQuery(data=b"add_post"))
async def add_post(event):
    waiting_for_ad.add(event.sender_id)
    await event.answer()
    await event.respond("Отправьте текст вашего объявления одним сообщением.")


@client.on(events.NewMessage)
async def collect_ad(event):
    if event.out or event.is_channel:
        return
    if event.sender_id not in waiting_for_ad:
        return
    if event.raw_text and event.raw_text.startswith("/"):
        return

    waiting_for_ad.discard(event.sender_id)
    post = make_post(event.raw_text or "")
    if post is None:
        await event.respond(
            "Объявление не опубликовано: пустой текст или только оптовые строки (ОПТ/OPT)."
        )
        return

    try:
        await client.send_message(
            target_channel,
            post,
            file=event.message.media,
            buttons=Button.url("🛒 Написати в Telegram", contact_url),
            parse_mode="html",
        )
    except Exception:
        logger.exception("Не удалось отправить публикацию в %s", target_channel)
        await event.respond("Не удалось опубликовать объявление. Проверьте права бота в канале.")
        return

    await event.respond("Объявление опубликовано в канале.")


async def main():
    await client.start(bot_token=BOT_TOKEN)
    logger.info("Бот запущен. Публикации отправляются в %s", target_channel)
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Остановка бота по запросу пользователя")
    except Exception:
        logger.exception("Ошибка запуска бота")
        sys.exit(1)
