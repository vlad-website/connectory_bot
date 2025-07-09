# Folder: handlers/commands.py
# -------------------------
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from db.user_queries import get_user, create_user, update_user_state

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"🚀 /start received from {user_id}")
    
    user = await get_user(user_id)

    if user:
        nickname = user.get("nickname") or "друг"
        await update.message.reply_text(
            f"👋 С возвращением, {nickname}!",
            reply_markup=ReplyKeyboardMarkup([["Начать"]], resize_keyboard=True)
        )
    else:
        await create_user(user_id)
        await update_user_state(user_id, "nickname")
        await update.message.reply_text(
            "👋 Привет! Введи свой ник (имя, по которому тебя увидит собеседник):"
        )

