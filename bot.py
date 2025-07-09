# telegram_chat_bot/

# -------------------------
# File: bot.py (main entry)
# -------------------------
import os
import logging
from aiohttp import web
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import BOT_TOKEN, WEBHOOK_URL, PORT
from db.init_db import init_db
from handlers.commands import start
from handlers.messages import message_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="bot.log",
    filemode="a"
)
logger = logging.getLogger(__name__)

application = ApplicationBuilder().token(BOT_TOKEN).build()

PORT = int(os.environ.get("PORT", "10000"))


application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

async def handle_webhook(request):
    from telegram import Update
    try:
        data = await request.json()
        logger.info(f"📩 Webhook received raw: {data}")
        
        update = Update.de_json(data, application.bot)
        logger.info(f"🔄 Parsed update: {update}")
        
        await application.process_update(update)
        return web.Response(text="ok")
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
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
app.router.add_post("/webhook", handle_webhook)
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)

if __name__ == "__main__":
    web.run_app(app, port=PORT)
