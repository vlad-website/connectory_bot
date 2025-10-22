# telegram_chat_bot/bot.py

import os
import logging
import traceback
from aiohttp import web
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from config import BOT_TOKEN, WEBHOOK_URL, PORT
from db.init_db import init_db
from handlers.commands import start, choose_lang, register_handlers as register_commands_handlers
from handlers.messages import message_handler

from telegram.ext import CallbackQueryHandler
from handlers.messages import callback_query_handler

application.add_handler(CallbackQueryHandler(callback_query_handler))


# -------------------- Настройка логирования --------------------
os.environ["PYTHONUNBUFFERED"] = "1"  # flush stdout

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

# -------------------- Создание приложения --------------------
application = ApplicationBuilder().token(BOT_TOKEN).build()

# -------------------- Регистрация хендлеров --------------------
# Команды и callback'и — group 0 (выполняются первыми)
application.add_handler(CommandHandler("start", start), group=0)
application.add_handler(CallbackQueryHandler(choose_lang, pattern=r"^lang_"), group=0)

# Если есть функция register_handlers для команд — добавляем её тоже в group=0
register_commands_handlers(application)

# Сообщения — group 1, только текст и не команды
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler), group=1)

# -------------------- Вебхук --------------------
async def handle_webhook(request):
    """
    Получаем POST от Telegram, парсим Update и передаём в PTB.
    """
    from telegram import Update

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
    await application.initialize()
    await init_db()  # подключение к БД и создание таблиц
    await application.start()
    if WEBHOOK_URL:
        await application.bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook set: {WEBHOOK_URL}")


async def on_cleanup(app):
    await application.stop()


# -------------------- Настройка веб-сервера --------------------
app = web.Application()
app.router.add_post(f"/{BOT_TOKEN}", handle_webhook)
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)

# -------------------- Запуск --------------------
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", PORT))
    web.run_app(app, port=PORT)
