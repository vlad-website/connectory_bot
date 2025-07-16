from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.keyboards import kb_after_sub, kb_searching, kb_chat
from i18n import tr

import logging

from db.user_queries import (
    get_user, update_user_nickname, update_user_gender,
    update_user_theme, update_user_sub, update_user_state
)
from core.topics import TOPICS
from core.matchmaking import add_to_queue, is_in_chat, remove_from_queue
from core.chat_control import end_dialog

logger = logging.getLogger(__name__)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug("💬 MSG: %s", update.message.text)
    user_id = update.effective_user.id
    text = update.message.text.strip()

    user = await get_user(user_id)
    if not user:
        await update.message.reply_text("Пожалуйста, отправьте /start.")
        return

    state = user["state"]
    logger.debug("STATE=%s TEXT=%s", state, text)

    # ---------- Кнопка «Начать» ----------
    if text == await tr(user, "btn_start"):
        await update_user_state(user_id, "theme")
        keyboard = [[t] for t in TOPICS.keys()]
        await update.message.reply_text(
            await tr(user, "pick_theme"),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # ---------- ШАГ 1: Никнейм ----------
    if state == "nickname":
        await update_user_nickname(user_id, text)
        await update_user_state(user_id, "gender")

        await update.message.reply_text(
            await tr(user, "choose_gender"),
            reply_markup=ReplyKeyboardMarkup(
                [[await tr(user, "male")], [await tr(user, "female")], [await tr(user, "any_gender")]],
                resize_keyboard=True
            )
        )
        return

    # ---------- ШАГ 2: Пол ----------
    elif state == "gender":
        valid_genders = [await tr(user, "male"), await tr(user, "female"), await tr(user, "any_gender")]
        if text not in valid_genders:
            await update.message.reply_text(
                await tr(user, "wrong_gender"),
                reply_markup=ReplyKeyboardMarkup([[g] for g in valid_genders], resize_keyboard=True)
            )
            return

        await update_user_gender(user_id, text)
        await update_user_state(user_id, "theme")

        keyboard = [[t] for t in TOPICS.keys()]
        await update.message.reply_text(
            await tr(user, "pick_theme"),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # ---------- ШАГ 3: Тема ----------
    elif state == "theme":
        if text not in TOPICS:
            await update.message.reply_text(await tr(user, "wrong_theme"))
            return

        await update_user_theme(user_id, text)
        await update_user_state(user_id, "sub")

        subtopics = TOPICS[text] + [await tr(user, "any_sub")]
        keyboard = [[s] for s in subtopics]
        await update.message.reply_text(
            await tr(user, "choose_sub"),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # ---------- ШАГ 4: Подтема ----------
    elif state == "sub":
        theme = user["theme"]
        valid_subs = TOPICS.get(theme, []) + [await tr(user, "any_sub")]
        if text not in valid_subs:
            await update.message.reply_text(await tr(user, "wrong_sub"))
            return

        await update_user_sub(user_id, text)
        await update_user_state(user_id, "menu")
        await update.message.reply_text(
            f"{await tr(user, 'pick_theme')}: {theme}\n{await tr(user, 'pick_sub')}: {text}",
            reply_markup=kb_after_sub(user)
        )
        return

    # ---------- Меню ----------
    elif state == "menu":
        if text == await tr(user, "btn_search"):
            await update_user_state(user_id, "searching")
            await update.message.reply_text(await tr(user, "searching"), reply_markup=kb_searching(user))
            await add_to_queue(user_id, user["theme"], user["sub"], context)
            return

        if text == await tr(user, "btn_change_sub"):
            await update_user_state(user_id, "sub")
            subtopics = TOPICS[user["theme"]] + [await tr(user, "any_sub")]
            await update.message.reply_text(
                await tr(user, "choose_sub"),
                reply_markup=ReplyKeyboardMarkup([[s] for s in subtopics], resize_keyboard=True)
            )
            return

        if text == await tr(user, "btn_main_menu"):
            await update_user_state(user_id, "theme")
            keyboard = [[t] for t in TOPICS.keys()]
            await update.message.reply_text(
                await tr(user, "pick_theme"),
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return

    # ---------- Поиск ----------
    elif state == "searching":
        if text == await tr(user, "btn_stop"):
            await remove_from_queue(user_id)
            await update_user_state(user_id, "menu")
            await update.message.reply_text(await tr(user, "search_stopped"), reply_markup=kb_after_sub(user))
            return

        if text == await tr(user, "btn_change_sub"):
            await remove_from_queue(user_id)
            await update_user_state(user_id, "sub")
            subtopics = TOPICS[user["theme"]] + [await tr(user, "any_sub")]
            await update.message.reply_text(
                await tr(user, "pick_sub"),
                reply_markup=ReplyKeyboardMarkup([[s] for s in subtopics], resize_keyboard=True)
            )
            return

        if text == await tr(user, "btn_main_menu"):
            await remove_from_queue(user_id)
            await update_user_state(user_id, "theme")
            keyboard = [[t] for t in TOPICS.keys()]
            await update.message.reply_text(
                await tr(user, "pick_theme"),
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return

        if text == await tr(user, "btn_support"):
            await update.message.reply_text("🙏 Спасибо за поддержку!\n(Здесь будет ссылка на донат)",
                                            reply_markup=kb_searching(user))
            return

        await update.message.reply_text(await tr(user, "default_searching"))
        return

    # ---------- Чат ----------
    elif await is_in_chat(user_id):
        if text == "❌ Завершить диалог":
            await end_dialog(user_id, context)
            return

        if text == "🔍 Новый собеседник":
            await end_dialog(user_id, context, silent=True)
            await update_user_state(user_id, "menu")
            await update.message.reply_text(
                await tr(user, "main_menu"),
                reply_markup=kb_after_sub(user)
            )
            return

        companion_id = user.get("companion_id")
        if companion_id:
            await context.bot.send_message(companion_id, text=text)
        return

    # ---------- Фолбэк ----------
    await update.message.reply_text(await tr(user, "error_fallback"))
