# Update: handlers/messages.py
# -------------------------
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from db.user_queries import (
    get_user, update_user_nickname, update_user_gender,
    update_user_theme, update_user_state
)
from core.matchmaking import add_to_queue, find_match, get_partner, end_chat

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if not user:
        await update.message.reply_text("Пожалуйста, нажмите /start")
        return

    state = user['state']
    msg = update.message.text.strip()

    if state == "nickname":
        await update_user_nickname(user_id, msg)
        await update_user_state(user_id, "gender")
        await update.message.reply_text("Ты парень или девушка?", reply_markup=ReplyKeyboardMarkup([["Парень", "Девушка"]], resize_keyboard=True))

    elif state == "gender":
        if msg.lower() not in ["парень", "девушка"]:
            await update.message.reply_text("Пожалуйста, выбери: Парень или Девушка")
            return
        await update_user_gender(user_id, msg.lower())
        await update_user_state(user_id, "theme")
        await update.message.reply_text("О чём хочешь пообщаться? (например, кино, игры, спорт)", reply_markup=ReplyKeyboardRemove())

    elif state == "theme":
        await update_user_theme(user_id, msg.lower())
        await update.message.reply_text("🔍 Ищу собеседника...")
        partner_id = await find_match(user_id, msg.lower())

        if partner_id:
            partner = await get_user(partner_id)
            await update_user_state(user_id, "chatting")
            await update_user_state(partner_id, "chatting")

            await context.bot.send_message(chat_id=user_id, text=f"💬 Найден собеседник: {partner['nickname']}, начинай общение!")
            await context.bot.send_message(chat_id=partner_id, text=f"💬 Найден собеседник: {user['nickname']}, начинай общение!")
        else:
            await add_to_queue(user_id, msg.lower())

    elif state == "chatting":
        partner_id = await get_partner(user_id)
        if partner_id:
            await context.bot.send_message(chat_id=partner_id, text=msg)
        else:
            await update.message.reply_text("😕 Собеседник отключился. Нажмите /start, чтобы найти нового.")

    elif msg.lower() == "начать":
        await update_user_state(user_id, "theme")
        await update.message.reply_text("О чём хочешь поговорить?")

    else:
        await update.message.reply_text("Не понял. Попробуй ещё раз или нажми /start")
