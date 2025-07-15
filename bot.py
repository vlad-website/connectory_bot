# telegram_chat_bot/

# -------------------------
# File: bot.py (main entry)
# -------------------------
import os, sys
import logging
import traceback   # добавлено

from aiohttp import web
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import BOT_TOKEN, WEBHOOK_URL, PORT
from db.init_db import init_db
from handlers.commands import start
from handlers.messages import message_handler

# гарантируем flush stdout
os.environ["PYTHONUNBUFFERED"] = "1"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,                    # всё видно
    filename="bot.log",
    filemode="a"
)

# Настройка логирования
logger = logging.getLogger("bot")  # создаем логгер с именем "bot"
logger.setLevel(logging.DEBUG)

# Формат для логов
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Логи в файл
file_handler = logging.FileHandler("bot.log", mode="a")
file_handler.setFormatter(formatter)

# Логи в консоль
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Подключаем хендлеры
logger.addHandler(file_handler)
logger.addHandler(console_handler)




logger = logging.getLogger(__name__)

application = ApplicationBuilder().token(BOT_TOKEN).build()
register_handlers(application)

PORT = int(os.environ.get("PORT", "10000"))


application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))


from handlers.commands import register_handlers
register_handlers(application)

async def handle_webhook(request):
    """
    Получаем POST от Telegram, парсим в Update и передаём в PTB‑Application.
    Логи:
      • RAW JSON
      • update_id, message text / callback data
      • traceback при любой ошибке
    """
    from telegram import Update

    try:
        data = await request.json()
        logger.info("📨 RAW UPDATE: %s", data)

        update = Update.de_json(data, application.bot)
        # Короткая сводка в лог
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
    await init_db()
    await application.start()
    if WEBHOOK_URL:
        await application.bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook set: {WEBHOOK_URL}")

async def on_cleanup(app):
    await application.stop()

app = web.Application()
app.router.add_post(f"/{BOT_TOKEN}", handle_webhook)
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)


if __name__ == "__main__":
    web.run_app(app, port=PORT)
