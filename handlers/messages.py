# Folder: handlers/messages.py
# -------------------------
from telegram import Update
from telegram.ext import ContextTypes
from db.user_queries import get_user

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)

    if not user:
        await update.message.reply_text("/start, пожалуйста.")
        return

    await update.message.reply_text(f"Принято: {update.message.text}")

