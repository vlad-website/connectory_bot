# Folder: handlers/commands.py
# -------------------------
import logging                         # ← 1. импортируем logging

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from db.user_queries import get_user, create_user, update_user_state

logger = logging.getLogger(__name__)   # ← 2. создаём логгер

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        logger.info("▶️ /start for %s", user_id)

        user = await get_user(user_id)          # ← здесь чаще всего падает
    except Exception:
        logger.exception("DB read failed")
        await update.message.reply_text("⚠️ Ошибка БД. Попробуйте позже.")
        return

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
        
    logger.info(f"✅ /start REPLIED for user {user_id}")

