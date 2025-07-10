from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
import logging, traceback
from db.user_queries import (
    get_user, create_user, update_user_state
)

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        logger.info("▶️ /start for %s", user_id)

        user = await get_user(user_id)
        logger.debug("get_user returned: %s (%s)", user, type(user))

        if user:
            nickname = (user.get("nickname")            # <- если это dict
                        if isinstance(user, dict) else
                        user["nickname"]) or "друг"
            await update.message.reply_text(
                f"👋 С возвращением, {nickname}!",
                reply_markup=ReplyKeyboardMarkup([["Начать"]], resize_keyboard=True)
            )
        else:
            await create_user(user_id)
            await update_user_state(user_id, "nickname")
            await update.message.reply_text(
                "👋 Привет! Введи свой ник:"
            )

        logger.info("✅ /start replied OK for %s", user_id)

    except Exception as e:
        # выводим в консоль немедленно
        print("💥 EXCEPTION in /start:", e, flush=True)
        print(traceback.format_exc(), flush=True)
        logger.exception("Exception in /start")
        await update.message.reply_text("⚠️ Ошибка. Попробуйте позже.")
