# bot.py

import os
import logging
import traceback
from aiohttp import web

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN, WEBHOOK_URL, PORT
from db.init_db import init_db

# наши хендлеры
from handlers.commands import start, choose_lang
from handlers.messages import message_handler, callback_query_handler


# -------------------- ЛОГИРОВАНИЕ --------------------
os.environ["PYTHONUNBUFFERED"] = "1"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
    filename="bot.log",
    filemode="a",
)

logger = logging.getLogger("bot")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler = logging.FileHandler("bot.log", mode="a")
file_handler.setFormatter(formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


# -------------------- СОЗДАЁМ ПРИЛОЖЕНИЕ --------------------
application = ApplicationBuilder().token(BOT_TOKEN).build()


# -------------------- РЕГИСТРАЦИЯ ХЕНДЛЕРОВ --------------------

# 1) /start и выбор языка — группа 0 (выполняются первыми)
application.add_handler(CommandHandler("start", start), group=0)
application.add_handler(CallbackQueryHandler(choose_lang, pattern=r"^lang_"), group=0)

# 2) Все остальные callback — тоже в группе 0
# (кнопки перевода, смены языка через setlang_ru и т.п.)
application.add_handler(CallbackQueryHandler(callback_query_handler), group=0)

# 3) Обычные сообщения — группа 1
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler), group=1)


# -------------------- ВЕБХУК --------------------
async def handle_webhook(request):
    """Получаем POST от Telegram, парсим Update и отдаём PTB."""
    try:
        data = await request.json()
        logger.info("📨 RAW UPDATE: %s", data)

        update = Update.de_json(data, application.bot)

        summary = (
            f"id={update.update_id} "
            f"msg='{update.message.text if update.message else ''}' "
            f"callback='{update.callback_query.data if update.callback_query else ''}'"
        )
        logger.info("🔄 Parsed update: %s", summary)

        await application.process_update(update)
        return web.Response(text="ok")

    except Exception:
        logger.exception("❌ Webhook handler crashed:\n%s", traceback.format_exc())
        return web.Response(status=500, text="error")


async def on_startup(app):
    """Запуск приложения и установка вебхука."""
    await application.initialize()
    await init_db()
    await application.start()

    if WEBHOOK_URL:
        await application.bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook set: {WEBHOOK_URL}")


async def on_cleanup(app):
    """Остановка приложения."""
    await application.stop()


# -------------------- ВЕБ-СЕРВЕР --------------------
app = web.Application()
app.router.add_post(f"/{BOT_TOKEN}", handle_webhook)

app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)


# -------------------- ЗАПУСК --------------------
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", PORT))
    web.run_app(app, port=PORT)
